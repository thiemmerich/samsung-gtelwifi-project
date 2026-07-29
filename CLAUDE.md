# CLAUDE.md — Samsung Galaxy Tab E (SM-T560 / gtelwifi) → postmarketOS

Master reference for this hobby project. Detailed narrative lives in `quest/*.md`;
this file is the quick-orient + the reproducible recipe. **Read this first.**

## What this is
Bring a modern-ish Linux to a 2015 **Samsung Galaxy Tab E 9.6 (SM-T560, `gtelwifi`,
Spreadtrum SC7730, armv7)** by gluing the postmarketOS reverse-engineered **downstream
3.10 kernel** (working display + BCM4343 WiFi) to a lightweight userspace. NOT a
Raspberry-Pi-OS port (Broadcom kernel can't move) — it's kernel-glue + a Debian-family
rootfs. End goal: **Devuan (no systemd) + LXDE**, Windows-like feel. See `quest/ROADMAP.md`.

## STATUS (2026-07-29) — 🧵 TLS-BRIDGE RECON: multithreading blocker diagnosed + plan 🧵
Goal: replace the `stub_pthread.py` hack (nulls bionic mutex funcs → single-thread-only) with a real
fix, so multithreaded GL works → enables a GPU-composited desktop (Path B). Deep recon (gdb backtrace):

**The crash (stub removed):** `ldr r3,[r0,#0x20]` with `r0=0` inside bionic `libc.so`'s pthread region
(`pthread_mutex_init`@0xe6d0…`_lock`@0xe8f4) — a **null bionic-TLS deref**. `lr==pc`, both in libc →
it's **bionic libc calling itself** (intra-library direct `bl`, which bypasses libhybris hooks).

**Root cause:** our libhybris port has **no bionic TLS setup** (no `__set_tls`/`TLS_SLOT` anywhere) and
the bundled linker (`common/jb/linker.c:1607`) **skips libc.so's constructors** (which would init that
TLS). But it still loads+binds bionic libc.so. Symbol resolution (`linker.c:1376`) checks hooks FIRST,
so the blob's own pthread calls hit our (working, musl-backed) hooks — but **46 of the blob's 118 libc
imports are unhooked** and bind to bionic libc.so; one of those bionic funcs makes an internal (direct,
unhookable) call into bionic pthread → null TLS → crash.

**Strategy 1 (blanket-hook remaining libc/libm → musl) ATTEMPTED — does NOT work cleanly:**
`patch6_libc_hooks.py` added 36 `HOOK_DIRECT_NO_DEBUG` entries (15 libc syscall wrappers + 21 libm).
Result: it *moved* the crash PAST the bionic-pthread null-TLS deref (progress → confirms bionic libc is
in the loop) but introduced a NEW early crash: `pc=0` (call through a null pointer) during startup,
BEFORE the blob loads, and it regresses even the stubbed baseline (verified in fresh processes, not
GPU-state corruption). All 36 symbols DO exist in musl (checked `nm -D`), so it's not a null-symbol
hook — blanket hooking perturbs the load/init path (libGLES_trace.so starts loading; suspected
uninitialised GLES dispatch). Reverted; baseline works again (22.8 fps). patch6 kept local, NOT
committed (regresses).

**Original crash, fully characterised (gdb, stubless):** faults at bionic libc.so `+0xe7c4`
(`ldr r3,[r0,#0x20]`, r0=0, i.e. null bionic TLS) inside `pthread_mutex_init`(0xe6d0)/`_lock`(0xe8f4)
region. Reached through MANY intra-libc frames (stack is all `0xb6c6xxxx`/`0xb6c7xxxx`/`0xb6c8xxxx` =
bionic libc), so there is NO single external caller to hook surgically — bionic libc genuinely needs a
valid TLS internally. r1=0x14, r3=exe addr. gdb can't unwind bionic (no CFI) and doesn't see the
jb.so-loaded Android libs in `info sharedlibrary`.

**CONCLUSION — the real fix is Strategy 2: actually set up minimal bionic per-thread TLS** (allocate a
bionic-layout TLS block, populate the slots bionic reads via the thread register, coexisting with
musl's use of TPIDRURO). This is what mature libhybris does (its linker's `__set_tls`), which our port
omitted. It's the genuine TPIDRURO-coexistence work — multi-session, the hardest piece of the quest.
Blanket-eliminating bionic libc (strategy 1) is not viable because bionic libc.so is loaded and its
internal pthread/TLS use is reached through too many paths. NEXT: study upstream libhybris bionic-TLS
setup + implement a minimal version in `common/jb/linker.c`/`hooks.c`. Meanwhile the stub keeps
single-threaded GPU working (Path A remains viable now).
Recon tooling: `gpu-tls/` diffs, `gpu_cube.c` async-signal-safe crash reporter (PC/LR+maps), `/tmp/g.gdb`.

## STATUS (2026-07-29) — 🧊 REAL 3D ON MALI: `GL_RENDERER=Mali-400 MP`, ~22–28 fps 🧊
A self-contained lit, depth-buffered, spinning 6-colour cube (`gpu-demos/gpu_cube.c`) runs a full
3D pipeline — perspective projection, GL_DEPTH_TEST, per-fragment diffuse+specular lighting — on the
hardware GPU (the driver reports `GL_RENDERER=Mali-400 MP`). **21.8 fps with vsync, 27.9 fps without**
(`HYBRIS_FB_NOVSYNC=1`) at 800×1280. Rung 4 (a real GLES2 app on the GPU) DONE.

Build: `g++` against the libhybris `.so`s (see the compile line captured in git history / gpu_cube.c
header). Run with the same env as the tests (`EGL_PLATFORM=fbdev`, `HYBRIS_LD_LIBRARY_PATH`, the
`LD_LIBRARY_PATH` list). Uses `eglGetDisplay(EGL_DEFAULT_DISPLAY)` + NULL-window fullscreen fbdev +
`EGL_DEPTH_SIZE 16`; the 8888→565 downconvert handles the panel.

**fps ceiling is the software downconvert (memory-latency-bound: uncached GPU-buffer read + 2 MB/frame
write to /dev/fb0), NOT the GPU or the convert arithmetic** (32-bit-word load vs byte loads made no
difference; vsync costs ~6 fps). The real speed unlock is the hardware DISPC-overlay/GSP-blit path
(zero CPU pixel-touch) — same big lift as the Wayland-compositor work, deferred. NEON would only shave
the arithmetic, not the memory stalls.

## STATUS (2026-07-29) — 🌈 FULL-COLOR GPU RENDERING VALIDATED 🌈
Correct-color, full-screen, artifact-free Mali-400 GLES2 — validated with a color-cycling,
gradient-shaded, drifting diamond (per-pixel shading + all 3 channels + transforms + animation all
confirmed). This closes the last GPU bug: **wrong colors** (green rendered as gold).

**Root cause (took the whole session):** the sprdfb panel path is HARDWIRED 16bpp RGB565
(`line_length` locked at 1600 — `FBIOPUT_VSCREENINFO bpp=32` is accepted but stride stays 1600 →
half-screen). The Mali fbdev blob ALWAYS renders 32bpp RGBA8888 for this path (ignores 565 EGL
configs AND a forced 565 gralloc buffer format). The proprietary `fb_post` does a dumb `memcpy`
with **no format conversion**. So Mali's 8888 bytes were being scanned out as 565 → `[00,FF,00,FF]`
green read as `0xFF00` = gold; blue dropped entirely; geometry half-width (hidden by flat fills).

**THE FIX — `hybris/musl-port/patch5_downconvert.py`:** render into a LINEAR, CPU-readable,
offscreen RGBA8888 buffer (`GRALLOC_USAGE_HW_RENDER|HW_TEXTURE|SW_READ_OFTEN`, format
`RGBA_8888`, NOT `HW_FB`), then do our OWN 8888→565 downconvert in `FbDevNativeWindow::queueBuffer`
(replacing `hybris_gralloc_fbdev_post`): `hybris_gralloc_lock()` the buffer, pack
`((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)` straight into an `mmap` of `/dev/fb0` (16bpp, stride 1600).
Rebuild+install `eglplatform_fbdev.so` to `/usr/local/lib/libhybris/`. ~1M px/frame CPU pass — a
few ms, fine. Also `patch4_vsync.py`: `FBIO_WAITFORVSYNC` gate before post (sprdfb honours it even
though it refuses fbdev panning) to cut tearing.

**Dead ends (don't repeat):** (1) forcing a 565 EGLConfig — blob ignores it (565 configs DO exist:
indices 0,1,2,17 = R5G6B5A0 buf16). (2) forcing gralloc buffer format `RGB_565` at alloc — ignored.
(3) pinning fb to 32bpp ABGR8888 (`hook_32bpp.py`) — sprdfb keeps 1600 stride → half-screen.
**CRITICAL measurement gotcha:** raw `/dev/fb0` dumps are MISLEADING (the DISPC scans a separate
ION overlay; fb0's legacy smem ≠ what's on the panel). Trust your eyes or `glReadPixels`, not fb0
byte dumps. Tools: `set_test_color.py`, `dump_fb.py`, `pick_565_config.py`, `validate_show.py`.

## STATUS (2026-07-29) — 🏆🏆 CLEAN GPU TRIANGLE — QUEST COMPLETE 🏆🏆
CRISP, ARTIFACT-FREE Mali-400 GLES2 render full-screen on the panel. Final fix: force the fbdev
window buffer to a LINEAR scanout allocation (`GRALLOC_USAGE_HW_FB` only, not Mali's tiled
HW_RENDER buffer) — killed the tile-writeback grid. See `hybris/musl-port/fix_fbdev_linear.md`.
Full chain: /dev/mali0 (ported kernel driver) → libhybris musl port → fbdev EGL → 16bpp-pinned +
linear fb → clean triangle. From "can it run Raspbian?" to a proprietary GPU rendering under musl.

## STATUS (2026-07-29) — 🏆 MALI-400 GPU RENDERS GLES2 via libhybris/musl 🏆
THE ULTIMATE HACK WORKS: proprietary Mali-400 driver runs on postmarketOS/musl through our
first-of-its-kind libhybris musl port — `test_glesv2` draws a spinning triangle (1740+ frames) to
the panel via `/dev/mali0`. Full winning recipe in "THE ULTIMATE HACK" section below (search
"SOLVED / GPU RENDERS"). Polish remaining: fb format match (tiled→RGB565), proper TLS bridge vs the
pthread-stub hack. Prior wins below still hold ↓

## STATUS (2026-07-28) — LXQt DESKTOP + TOUCH + WiFi + KEYBOARD WORK 🎉
- Full **LXQt desktop** (pmOS `ui=lxqt`, tablet build) runs on the panel, **driven by the
  touchscreen**; battery/power-manager read fine. Software-rendered X on sprdfb (no GPU) — pokey but usable.
- It lives on **userdata** (mmcblk0p26, 5.4 GB): the lxqt rootfs (1.9 GB) is too big for the
  1.5 GB SYSTEM partition, so we `dd`'d it onto userdata over SSH and boot from there.
- Console image still on SYSTEM (mmcblk0p23) as fallback.
- **WiFi works** (BCM4343, connected to LAN). Fix was a polkit rule: no elogind session →
  polkit denied NM control → `/etc/polkit-1/rules.d/49-nm-netdev.rules` grants netdev group NM control.
- **On-screen keyboard works**: `svkbd-mobile-intl` (`apk add svkbd`, 0.4.2). Autostarts via
  `~/.config/autostart/svkbd.desktop`. Pure Xlib → XTEST; NO GTK/gdk-pixbuf/memfd, tested typing into apps.
  - ⚠️ **onboard (GTK3) is BROKEN on this kernel** and can't be fixed at userspace: gdk-pixbuf's SVG
    icon load calls `memfd_create()` (Linux ≥3.17); our 3.10 kernel lacks the syscall → `Gtk:ERROR`.
    Any GTK3 app that loads an SVG icon dies the same way. Qt/LXQt/Xlib apps are unaffected.
    Real fix = backport `memfd_create` to the kernel (bundle with the BT/GPU kernel work).

## 🔥 THE ULTIMATE HACK (next mission, user's call): Mali-400 GPU via libhybris
Confirmed 2026-07-28: rendering is **100% CPU**. Xorg uses the `fbdev` driver, `/dev/dri` does
NOT exist (no DRM/KMS), fb is `sprdfb`, no Mali driver in-kernel. But the SC7730 has a physical
**Mali-400 MP2** GPU sitting idle. Goal: drive it → hardware GL/EGL.

**Why it's hard (and the ONLY viable path):** Mali-400 has no open driver (Mesa `lima` needs a
mainline DRM kernel we don't have — and we CAN'T leave the 3.10 downstream kernel; it's the only
one with working display+WiFi). The GPU only ever ran via Samsung's **Android Bionic blobs**
(`libGLES_mali.so`, `libEGL`, `gralloc`, built for Android's libc + fbdev HAL). Our userspace is
Alpine **musl + X11** → different ABI, blobs can't load natively.

**The known technique = libhybris** (created by Mer/Sailfish, used by Halium/Ubuntu-Touch for
exactly this): ships a patched Android linker so a glibc/musl process can `dlopen` Bionic-linked
`.so` blobs, plus EGL/GLESv2 shims that forward to the vendor Mali libs.

### ✅ RECON DONE (2026-07-28) — feasibility = GO. Exact spec extracted from stock firmware:
Stock `system.img` unpacked from `old-firmware/SAMFW.../AP_*.tar.md5` (AOSP sparse; use
`scripts/unsparse.py` → raw ext4, then `debugfs`). Working copy + extracted blobs live in
**`~/pmos-odin/gpu/`** (local only — the blobs are PROPRIETARY ARM/Samsung, must NEVER be committed
to the public repo). Facts:
- **Platform `sc8830` (SC7730SE), Android 4.4.4 KitKat / API 19, device `gtelwifi`.** (classic hybris era)
- **GPU = Mali-400 MP, hw core rev 0x0101 (r1p1).** Userspace DDK **`r4p1-01rel0`**. VARIANT=
  `mali400-r1p1-gles11-gles20-linux-android-kitkat-dma_buf-rgb_is_xrgb-egl_wait_sync`.
- **Blobs in hand** (`~/pmos-odin/gpu/blobs/`): `egl/libGLES_mali.so` (THE driver, opens `/dev/mali0`),
  `egl/libGLES_android.so`, `egl/egl.cfg` (`0 1 mali`), `libEGL.so`, `libGLESv2.so`, `libGLESv1_CM.so`,
  `hw/gralloc.sc8830.so` (fbdev gralloc), `hw/hwcomposer.sc8830.so`. All ARM EABI5, interp `/system/bin/linker`.
- **Dependency closure (hybris must satisfy — ALL present in system.img):** libc libdl libm
  libstdc++ liblog libcutils libutils libbinder libui libhardware libion libsync + libEGL/GLESv1_CM/v2.
- **Buffer path = `dma_buf`; kernel already has `ION`(drivers/gpu/ion/sprd) + `SPRD_IOMMU` + GSP.** ✔
- **THE GAP:** pmsourcedump kernel tree was STRIPPED of the Mali driver (0 `mali_*` files, no
  `CONFIG_MALI` in `gtelwifi-dt_hw07_defconfig`). Must obtain **Mali Utgard r4p1 kernel driver**.

### Attack plan (multi-session, HIGH risk on hybris step; everything else de-risked)
1. ✅ **Recon blobs + version** — DONE (above).
2. ✅ **Mali kernel driver FOUND** (2026-07-28): `codeworkx/android_kernel_samsung_gtelwifi`
   branch **`cm-11.0`**, `drivers/gpu/mali/` (166 files, full Utgard: common/linux/platform/regs/
   include). Build-info: `API_VERSION=600 TARGET_PLATFORM=sc8830 MALI_PLATFORM=sc8830 USING_UMP=(empty→dma_buf)`
   — a **factory match** to our stock r4p1 dma_buf blob (same device, same Android 4.4). Has the
   **sc8830 platform glue** (`platform/sc8830/mali_platform.c`+`base.h`). Kconfig symbols:
   `CONFIG_MALI400` (tristate) + `CONFIG_MALI_PLATFORM_SC8830` (default y) [+ MALI450/DEBUG/DVFS opts].
   **PORT PLAN:** copy `drivers/gpu/mali/` into our pmsourcedump tree → add to `drivers/gpu/Makefile`
   (`obj-$(CONFIG_MALI400) += mali/`) + `drivers/gpu/Kconfig` (`source "drivers/gpu/mali/Kconfig"`) →
   set `CONFIG_MALI400=y` + `CONFIG_MALI_PLATFORM_SC8830=y` in config.
   ✅ **PORT VERIFIED CLEAN (2026-07-28):** driver source staged at `~/pmos-odin/gpu/codeworkx-mali/`
   (commit `60871e9801b0`, 148 files). Every sprd symbol the `platform/sc8830/mali_platform.c` glue
   needs ALREADY resolves in our tree: `SPRD_MALI_PHYS` (`mach/__hardware-sc8830.h`),
   `REG_PMU_APB_PD_GPU_TOP_CFG` (board-spx15.c), `REG_GPU_APB_APB_CLK_CTRL` (`__sc8830_clock_tree.h`),
   `REG_AON_APB_APB_EB0`, `sci_glb_read/set`. No missing SoC symbols → mechanical drop-in.
   INTEGRATION MECHANISM (fits our build): vendor `mali/` as a tarball → APKBUILD `source=` → extract
   into `drivers/gpu/mali/` in prepare() → small patch for the Makefile/Kconfig/config hooks.
3. ✅ **Kernel port DONE + COMPILED (2026-07-28)** — `linux-samsung-gtelwifi-3.10.17-r8.apk`
   built with Mali built-in (`LD drivers/gpu/mali/built-in.o`; apk +71KB vs r7). Zero source
   changes needed. ✅ **CAPTURED into `patches/0002-mali-gpu-driver.patch` +
   `vendor/mali-utgard-sc8830-r4p1.tar.gz` + setup-pmaports.sh copy step (2026-07-28).**
   **The pmaports changes (pmaports/ is GITIGNORED — reproduced by 0002 + setup):**
   - `mali-utgard-sc8830-r4p1.tar.gz` (the `mali/` dir, 242KB) dropped in the aport dir + added to
     APKBUILD `source=` & `sha512sums` (sha512 `de6bb31b...`).
   - APKBUILD `prepare()`: BEFORE `. downstreamkernel_prepare` (critical ordering — see below),
     `cp -r "$srcdir"/mali drivers/gpu/mali` + sed hooks: `obj-y ... + mali/` in
     `drivers/gpu/Makefile`, `source "drivers/gpu/mali/Kconfig"` after the video line in `drivers/Kconfig`.
   - `config-samsung-gtelwifi.armv7`: 14 `CONFIG_MALI*` lines (codeworkx values) + re-checksummed
     (sha512 `939b9569...`). `pkgrel` 7→8.
   - ⚠️ **GOTCHA (cost a build):** the mali hooks MUST run BEFORE `downstreamkernel_prepare`
     (which does `yes ""|make oldconfig`). If mali/Kconfig isn't sourced yet, oldconfig drops
     `CONFIG_MALI400=y` as unknown → build's silentoldconfig sees MALI400 as (NEW) → prompts →
     aborts (stdin redirected). Also: editing the config file requires re-`sha512sum` it in APKBUILD.
   - NOTE: memfd_create backport + BT deferred to a later build (user chose Mali-only first).
   ✅✅ **CONFIRMED ON-DEVICE (2026-07-28):** flashed boot.img ONLY (odin4, `pmos-kernel.tar.md5`;
   kernel→KERNEL/p20, userdata lxqt rootfs untouched — safe because config has only 1 trivial `=m`
   module, everything incl. WiFi/USB-gadget/Mali is `=y`). Booted `3.10.17 #9-postmarketOS`, and
   **`/dev/mali0` EXISTS** (`crw------- root root 10, 58`) → the Utgard driver probed, mapped
   `SPRD_MALI_PHYS`, registered its node. THE KERNEL HALF OF THE HACK WORKS.
   Flash-only-kernel recipe: `sudo cp <chroot_rootfs>/boot/boot.img ~/pmos-odin/boot.img` →
   `tar -H ustar -cf pmos-kernel.tar boot.img; md5sum -t pmos-kernel.tar >> pmos-kernel.tar;
   mv ...md5` → `sudo odin4 -a pmos-kernel.tar.md5`.
   NEXT: step 4 — libhybris (the last boss).
4. **libhybris for Alpine armv7/musl** — the last boss. ✅ **RECON DONE (2026-07-28):**
   - **Feasibility GO (with caveats):** libhybris is NOT glibc-bound; pmOS shipped it on musl
     2017→late-2024 (dropped for lack of use-cases, not because it broke); musl fixes are upstream.
     Best modern musl reference: **`JamiKettunen/chimera-libhybris`** (Chimera Linux = musl, bare-metal
     hybris, NOT the LXC/Halium style). Precedent for Mali+hybris+fbdev: ODROID KitKat, sunxi Mali-400.
     - **musl packaging template to mine:** `JamiKettunen/cports -b hybris` (Chimera's libhybris
       cports recipe — flags/deps/staging on musl). CAVEAT: Chimera targets Halium/Android 9+, so its
       libhybris version is likely too new for our KitKat blobs → reinforces "use older/jb-path libhybris".
   - ⚠️⚠️ **TWO libhybris MODELS — we are the CLASSIC one, not Chimera's.** Chimera/modern-Halium =
     Android-in-LXC-container + `--enable-stub-linker` + `--enable-wayland` + Android-11 headers
     (`Halium/android-headers`). WE = **classic bare-metal** (old Sailfish/Mer, ODROID-KitKat): NO
     container, libhybris uses its **real bundled bionic linker** to `dlopen` our vendor blobs directly,
     pointed at a staged `/system/lib`. So our flags are ~opposite: **NO stub-linker, NO wayland**;
     `--enable-arch=arm --with-default-egl-platform=fbdev --enable-mali-quirks` + API-19 android-headers
     + `--with-default-hybris-ld-library-path=<staged /vendor/lib:/system/lib>`. Chimera's cbuild template
     (`0.1.0_git20241107`, commit `9f61f26c`, libhybris master; deps automake/slibtool/pkgconf) is a
     STRUCTURAL reference only. Aport skeletons drafted in repo `hybris/` (see that dir's README).
   ### 🔨 libhybris BUILD IN PROGRESS (2026-07-28) — big breakthroughs
   - **Approach = NATIVE build ON the tablet** (armv7 Alpine, gcc+internet), NOT cross-compile — fast
     iteration, direct access to /dev/mali0 + blobs. BUT: **3.10 kernel lacks `getrandom()`** (≥3.17)
     → `git clone` fails on-device (`unable to get random bytes`). So: **prep source on the HOST**
     (working git), `scp` to tablet, compile there. (⇒ add `getrandom()` to the P1 kernel backport
     list alongside `memfd_create`.)
   - **android-headers SOLVED:** `pfalcon/android-platform-headers` has `android-4.4_r1` (exact KitKat!).
     Assembled with libhybris `utils/extract-headers.sh --version 4.4.4` → `~/pmos-odin/gpu/android-headers-4.4`
     (had to manually add the `EGL/GLES*/KHR` headers from `frameworks/native/opengl/include` — the
     script misses them). `android-version.h`=4.4.4. (mer-hybris/android-headers is 404-gone; Halium
     only goes back to 5.1.)
   - **🎯 BREAKTHROUGH — pmOS's removed libhybris aport lives on in forks:**
     `Linux-On-Sdm6Series/pmaports@halium9:hybris/libhybris/` (also pombredanne/, rajpratik71/). It pins
     libhybris commit **`1b6090ad6e420fe2139685e0af54fd94edb7d049`** (1.0_git20200504) + ships
     **`0001-Make-libhybris-compile-with-musl.patch`** (the complete musl port — fpos_t/pthread_cond/
     LFS64/cdefs, adds `musl_compat.h`) + **`0002-Implement-X11-EGL-platform...patch`** (X11 EGL platform
     — for rendering GL into LXQt/X11 later!). Both saved to **`hybris/musl-port/`** in this repo.
     Depends on `bsd-compat-headers`. → We build 1b6090ad + 0001 (skip hand-porting master's jb path,
     which hit endless glibc-isms). 0002 is the future path for X11 desktop GL (bring up on fbdev first).
   - **BUILD RECIPE (works, configures clean):** host: `curl .../archive/1b6090ad.tar.gz` → `patch -p1 <
     0001` → scp to tablet → `apk add bsd-compat-headers` → `./autogen.sh` → `./configure --enable-arch=arm
     --with-default-egl-platform=fbdev --enable-mali-quirks --with-android-headers=/home/user/android-headers-4.4
     --with-default-hybris-ld-library-path=/vendor/lib:/system/lib:/system/vendor/lib --enable-property-cache
     --enable-experimental` → `make`. (configure confirmed: arch=arm, Android 4.4.4, fbdev, real linker.)
   - ✅✅ **libhybris BUILT on musl (2026-07-28)** — `libhybris-common.so`, `libEGL.so.1`,
     `libGLESv2.so.2`, **`eglplatform_fbdev.so`** all compiled on-device. FIRST known musl build of the
     KitKat/`jb` path. **Complete fix list on top of commit 1b6090ad + 0001:**
     1. GCC-15 promotes warnings→errors, so 0001's `#else`(musl) branches (written for GCC 9) fail. In
        `hybris/common/hooks.c`: `_hybris_hook_fgetpos`/`fsetpos` musl branch passed `bionic_fpos_t*`
        (a `long long`) to musl's opaque-`fpos_t` funcs → rewrote to `ftello`/`fseeko` (bionic fpos IS a
        file offset); `_hybris_hook__gnu_strerror_r` → musl `strerror_r` is XSI (int) so
        `strerror_r(...); return buf;`.
     2. `libsync` needs `linux/sync.h`+`linux/sw_sync.h` (Android sync UAPI, dropped from modern
        linux-headers) → provided minimal UAPI headers (saved `hybris/musl-port/linux-{sync,sw_sync}.h`;
        install to `/usr/include/linux/`).
     3. `apk add bsd-compat-headers libx11-dev libxext-dev` (Android `EGL/eglplatform.h` falls to its
        X11 branch on generic Unix).
     4. Optional tests `test_glesv3` (needs EGL_OPENGL_ES3_BIT — Mali-400 is GLES2-only) + `test_camera`
        (needs wayland) fail to build → drop `tests` from top Makefile SUBDIRS (line 361) for install, or
        ignore (the libs + `test_egl`/`test_glesv2`/`test_egl_configs` in tests/.libs/ ARE built).
     - ⚠️ The pmOS rootfs already has **mesa `libEGL.so`/`libGLESv2.so`** in /usr/lib — do NOT clobber
       system-wide yet; for testing run `test_egl` with `LD_LIBRARY_PATH` = build `.libs` dirs + the
       staged blob dir, and put `eglplatform_fbdev.so` where libhybris looks (pkglibdir /usr/lib/libhybris/).
   - ✅✅✅ **THE MALI GPU DRIVER RUNS ON musl/pmOS (2026-07-28) — ULTIMATE HACK PROVEN.**
     Staged blobs at `/system/lib` (extracted /system/lib from system.raw via `debugfs rdump`, scp'd,
     `sudo tar xzf -C /`). Ran `test_egl_configs` → **`EGL Version 1.4` + Mali blob extensions**
     (`EGL_KHR_get_all_proc_addresses EGL_ANDROID_presentation_time`). So libhybris's bundled bionic
     linker loaded `libGLES_mali.so`, opened `/dev/mali0`, and `eglGetDisplay`+`eglInitialize`
     SUCCEEDED — the proprietary Mali-400 userspace driver is live on our musl userspace.
     **RUNTIME ENV recipe:** `sudo chmod 666 /dev/mali0 /dev/fb0`;
     `HYBRIS_LD_LIBRARY_PATH=/system/lib:/vendor/lib`;
     `LD_LIBRARY_PATH=<build>/{egl,glesv2,common,hardware,properties,libsync,egl/platforms/fbdev}/.libs`;
     `EGL_PLATFORM=fbdev`; run `tests/.libs/test_egl_configs`. (Runs as user after the chmod.)
   - 🔬 **RUNTIME DEBUG PROGRESS (2026-07-28, session 2):** The `EGL_NOT_INITIALIZED` was a
     side-effect of gralloc loading the WRONG module. Root fixes applied so far (all improved things):
     1. **Stage `/system/build.prop`** (extract `/build.prop` from system.raw). It has
        `ro.board.platform=sc8830` → the HAL now loads the CORRECT **`gralloc.sc8830.so`** (not
        `gralloc.default.so`). `sudo chmod 666 /dev/ion /dev/mali0 /dev/fb0`.
     2. **Hooked `__android_log_print/_vprint/_write/_assert`** in hooks.c (routed to stderr) — the
        blobs' logging was falling through to bionic `liblog` → bionic mutex → crash. NOW WE SEE THE
        BLOB'S OWN LOG: `[droid:libEGL] loaded libGLES_mali.so`, `[droid:[Gralloc]] sprdfb 800x1280
        bpp=32` — **gralloc FULLY initializes the sprdfb framebuffer** (even sets 32bpp RGBA!).
     3. Hooked fortify `__*_chk` + C++ `_Znwj/_ZdlPv` (new/delete→malloc/free). (Both hook patches
        saved: `hybris/musl-port/patch_androidlog.py`, `patch2_hooks.py` — idempotent, re-appliable.)
   - ⚠️ **REMAINING (the wall): bionic-libc COEXISTENCE.** Crash persists at bionic
     `pthread_mutex_init` (PC `0xb6c9a7c4`, deref `0x20`), reached via `gralloc.sc8830 → bionic libc`.
     Cause: the blobs call bionic libc functions libhybris doesn't hook; with bionic `libc.so` loaded
     they run bionic code that touches **bionic TLS/`pthread_internal_t`** which is null on our thread
     → deref 0x20. (Removing bionic libc instead → null-dispatch crash in libEGL: hooks incomplete.)
   - **➡️ NEXT-SESSION STRATEGY (root fix, not whack-a-mole):** the deref-0x20 = the thread's bionic
     TLS slot (`TLS_SLOT_THREAD_ID` → pthread_internal_t) is unset. **Investigate libhybris's bionic
     main-thread TLS setup** (jb linker `__libc_init_tls`/`__init_tls`/`init_tls`/`__set_tls`); if the
     musl port didn't wire up the main thread's bionic TLS, fixing THAT once resolves ALL these
     bionic-TLS crashes at once — far better than hooking each function. Tool: rebuild libhybris with
     `--enable-trace --enable-debug` + `HYBRIS_TRACE=1` to log the exact call sequence. Static gap
     list (unhooked blob imports) in this session's notes: ion_*, hw_get_module, sem_*, sync_wait,
     android_atomic_*, __aeabi_*, close/dup/ioctl/clock_gettime, etc.
   - 🧭 **SESSION 2b (2026-07-28 late) — diagnosis attempts + narrowing:**
     - Built libhybris with `--enable-debug --enable-trace` (clean rebuild). BUT `HYBRIS_LINKER_DEBUG=3`
       + `HYBRIS_TRACE=1` produced NO extra output → the jb linker's `TRACE_TYPE(LOOKUP,...)` is gated
       by a compile-time `#if LINKER_DEBUG` that `--enable-debug` does NOT set. **To get symbol-resolution
       logging, add `-DLINKER_DEBUG` (and check `linker_debug.h`) to the build**, OR use a targeted gdb.
     - Stack-scan caller-ID was UNRELIABLE: the "gralloc return addresses" I chased (0x32b3 etc.) are
       PAST gralloc's `.text` (ends 0x2afc) → they're gralloc *data*, not code. Don't trust raw stack
       scans; use `.text` bounds (`objdump -h`, ARM objdump only works ON the tablet, not host x86).
     - **Prime remaining suspect = `ion_*`** (gralloc's unhooked imports: ion_open/ion_alloc/ion_free/
       ion_share/ion_sync_fd/ion_close/ion_invalidate_fd). Crash happens RIGHT AFTER gralloc prints the
       fb info — i.e., when it allocates the framebuffer/graphics buffer via ION. These fall through to
       bionic libc.so's ion helpers → bionic internal state → pthread crash. Other still-unhooked:
       `clock_gettime close dup ioctl atol glFinish __aeabi_l2f __aeabi_uldivmod`.
   - ✅ **ROOT CAUSE CONFIRMED (2026-07-28 session 2c):** the crash is the **ARM bionic↔musl TLS
     collision**, NOT a single missing hook. Evidence: gralloc's `pthread_mutex_init/lock/unlock`
     imports ARE hooked (→ musl), yet the crash PC is inside *bionic* `libc.so` `pthread_mutex_init`
     (+0xf4, deref null+0x20). So an **unhooked bionic libc function** (reached via import→bionic
     because not hooked) calls bionic's OWN pthread *internally* (intra-.so, bypassing the hook).
     Bionic pthread reads `TPIDRURO` (the ARM user thread register) for TLS — but musl owns that
     register, so bionic gets musl's TCB, reads a null `pthread_internal_t` at TLS_SLOT_THREAD_ID,
     derefs +0x20 → SIGSEGV. libhybris only makes bionic TLS valid on threads IT wraps; its
     `_hybris_hook_pthread_create` just forwards to musl (no bionic-TLS setup), and our main thread is
     pure musl. gdb caller-ID is BLOCKED (bionic libc.so stripped, no CFI; even
     `HYBRIS_ENABLE_LINKER_DEBUG_MAP=1` can't symbolize/unwind it).
   - 🏆🏆🏆 **SOLVED / GPU RENDERS (2026-07-29) — THE ULTIMATE HACK WORKS.** `test_glesv2` renders
     1740+ frames (spinning triangle) on the Mali-400 via libhybris/musl; `test_egl` completes
     (context+surface+render loop+teardown, rc=0); `test_egl_configs` = 25 configs. GPU-rendered
     pixels confirmed ON THE PANEL (garbled/tiled — Mali outputs tiled-RGBA vs sprdfb linear-RGB565;
     a format-match polish item, NOT a failure). **THE COMPLETE WINNING RECIPE (all pieces required):**
     1. Kernel Mali driver → `/dev/mali0` (patches/0002 + vendored tarball). ✅
     2. libhybris `1b6090ad` + `0001` musl patch + GCC-15 fixes (ftello/fseeko fpos, XSI strerror_r)
        + `linux-{sync,sw_sync}.h`. Build: `apk add bsd-compat-headers libx11-dev libxext-dev`.
     3. Hooks added to `hybris/common/hooks.c`: `patch_androidlog.py` (__android_log_* → stderr),
        `patch2_hooks.py` (fortify __*_chk + C++ new/delete → musl).
     4. `hybris/musl-port/fix_consumer_usage.py`: in `egl/platforms/common/nativewindowbase.cpp` move
        `NATIVE_WINDOW_CONSUMER_USAGE_BITS` OUT of `#if ANDROID_VERSION_MAJOR>=6` (Mali KitKat blob
        queries it → else BAD_VALUE → surface-create fails). getUsage() returns 0x602 (HW_RENDER|TEXTURE).
     5. ⚠️ **THE TLS-COLLISION BYPASS (`hybris/musl-port/stub_pthread.py`):** binary-patch bionic
        `/system/lib/libc.so` — stub `pthread_mutex_init/lock/unlock/trylock/destroy` to ARM
        `mov r0,#0; bx lr`. Neutralizes the bionic-internal pthread calls that crash on the musl main
        thread's TLS. CRUDE (no-op mutexes → only safe for ~single-threaded bring-up); the *proper* fix
        is a bionic main-thread TLS bridge. Offsets from `readelf -sW` (ARM, not thumb).
     6. ⚠️ **INSTALL-PATH GOTCHA (cost hours):** libhybris dlopens the EGL platform from its compiled-in
        pkglibdir = **`/usr/local/lib/libhybris/`** (prefix defaulted to /usr/local). Edits to the
        build-dir platform libs DO NOTHING until you `sudo cp` them over `/usr/local/lib/
        libhybris-eglplatformcommon.so.1.0.0` + `/usr/local/lib/libhybris/eglplatform_fbdev.so` (or
        `make install`). `strace -e openat` to see which .so actually loads.
     7. Stage `/system` + `/system/build.prop` (ro.board.platform=sc8830 → gralloc.sc8830); `sudo chmod
        666 /dev/{mali0,ion,fb0}`.
     8. Runtime env: `HYBRIS_LD_LIBRARY_PATH=/system/lib:/vendor/lib`; `LD_LIBRARY_PATH=<build>/{egl,
        glesv2,common,hardware,properties,libsync,egl/platforms/fbdev}/.libs`; `EGL_PLATFORM=fbdev`.
   - ✅ **CLEAN TRIANGLE ACHIEVED (2026-07-29).** The checkerboard/garbling was NOT a kernel/fb format
     bug — it was `test_glesv2` using `create_hwcomposer_window()` (wrong platform!). Fix: use the fbdev
     window like `test_egl` does — pass **`NULL`** to `eglCreateWindowSurface` → the fbdev platform builds
     a full-screen `FbDevNativeWindow` (`fbdevws_CreateWindow`). Patched test_glesv2 (bypass
     create_hwcomposer_window, surface arg → NULL) + `sudo dd if=/dev/zero of=/dev/fb0` to clear stale fb
     + **reboot to reset the X/fb fighting**. Result: crisp solid triangle on white, GPU-rendered. The
     concentric rings = the spinning/scaling triangle composited across frames (single-buffered, no
     page-flip). CONFIRMED clean GPU render on the panel. 🔺
     - TIP for a clean render: stop the X server first (`sudo rc-service tinydm stop` or kill X) so the
       GPU test owns /dev/fb0 exclusively (no LXQt desktop underneath fighting the framebuffer).
   - 🔬 **CLEAN-IMAGE INVESTIGATION (2026-07-29, deep dive — the garbling is a kernel display-format
     issue, NOT the GPU).** Symptom: half-height image + black/white checkerboard = fb is effectively
     16bpp-stride (line_length=1600) while `gralloc.sc8830` forces 32bpp (RGBA) render → Mali writes
     3200 B/row into a 1600-stride scanout → overflow + color garble. Findings in `drivers/video/sprdfb`:
     - `sprdfb_main.c:56` `#define SPRDFB_IN_DATA_TYPE SPRD_IN_DATA_TYPE_ABGR888` → `:646` switch sets
       `dev->bpp=32` → `:214` `fix.line_length = panel->width*bpp/8` = 800*4 = **3200 at INIT** (should
       be right!). No other `dev->bpp=16` override exists.
     - `sprdfb_dispc.c:1260` (`#ifdef BIT_PER_PIXEL_SURPPORT`): DISPC input format from
       `var.bits_per_pixel` (32→ABGR + rb-switch; else RGB565). `:1253` `DISPC_OSD_PITCH = var.xres`
       (pixels). `BIT_PER_PIXEL_SURPPORT` IS defined (sprdfb.h:31) → runtime bpp change allowed.
     - Runtime showed `line_length=1600` + `var.bpp=32` (inconsistent). BUT my `fbprobe` (PUT16/PUT32)
       CORRUPTED the live fb — `set_par` can't restore 3200, only a reboot re-inits. So runtime readings
       after fbprobe are unreliable. `gralloc` also force-sets `var.bpp=32` (persists; overrode my PUT16).
     - **NEXT-SESSION PLAN (dedicated):** (1) fresh reboot, read `/dev/fb0` `line_length`+`bpp` BEFORE
       any gralloc (is init really 3200?). (2) instrument sprdfb (printk `dev->bpp`, `fix.line_length`,
       DISPC format reg at probe + on set_par) → rebuild → flash → read dmesg. (3) ensure the WHOLE path
       is consistently 32bpp/3200 end-to-end (or force 16bpp). `fbprobe.c` (in `hybris/musl-port/`? no —
       `~/pmos-odin/gpu/fbprobe.c`) is the ioctl probe tool. Also try double-buffering + stopping X.
     - ⚠️ Don't run `fbprobe` PUT16/PUT32 before a real render — it leaves the fb in a bad state until reboot.
   - 🔬 **STRIDE FIXED, TILING REMAINS (2026-07-29).** The 16bpp ioctl-pin (patch3) FIXED the
     half-screen — render now fills the full panel (confirmed bpp=16 stride=1600). But a solid-color
     test reveals a **regular black/white GRID** over solid fills (triangle geometry visible underneath).
     Root: **Mali-400 is a TILE-based renderer** writing its framebuffer output in a tiled/swizzled
     layout, while sprdfb scans out LINEARLY → solid regions become a periodic grid. On real Android the
     DISPC/GSP de-tiled Mali buffers during scanout; our direct /dev/fb0 path scans linear → sees raw
     tiles. **NEXT (deep):** force Mali linear framebuffer output (gralloc usage / a Mali env / the
     `rgb_is_xrgb` variant), OR enable the sprdfb DISPC tiled-scanout mode (kernel), OR blit-detile in the
     fbdev `post()`. To make the solid test even RUN: its `phase` uniform gets optimized out when the
     shader is solid → relaxed the `phase_loc<0` check in test_glesv2.cpp (else early-return→black).
   - **REMAINING POLISH (not blockers):** (a) double-buffering / page-flip for a single crisp frame
     (fb only had room for 1 buffer → single-buffered ripple); (b) window fills ~60% of panel (aspect);
     (c) replace the pthread-stub hack with a real bionic-TLS bridge (for multithreaded GL apps);
     (d) harmless `ion_client` close error at teardown; (e) then glmark2-es2, GL compositor, X GLAMOR.
   - **➡️ (historical) next moves that led to the solution — kept for reference:**
     0. **Find the unhooked bionic fn via NON-gdb means:** it's called right after gralloc prints fb
        info. Statically find which loaded Android lib (libutils/libcutils/libmemoryheapion/sprd libs
        that gralloc NEEDs) exports a fn gralloc calls next, that internally uses pthread. Then hook it
        or replace that lib with libhybris's own.  (ltrace won't see intra-.so calls.)
     1. **Hook `ion_*`** with musl-side impls (thin ioctl wrappers on `/dev/ion`; need the legacy ion
        UAPI + Spreadtrum heap ids). Most likely to unblock — gralloc buffer alloc is exactly here.
     2. **gdb break on bionic `pthread_mutex_init`** (`break *(libc_base+0xe6d0)`; gdb disables ASLR so
        libc_base is stable) → at hit, read `$lr` (bionic caller) → resolve via `readelf -sW` libc.so.
     3. **Add `-DLINKER_DEBUG`** to CPPFLAGS + rebuild → get the definitive hook-vs-bionic symbol list.
     4. **Root fix:** wire libhybris's bionic main-thread TLS (jb linker `__libc_init_tls`, commented out)
        so bionic funcs stop deref-ing null TLS — fixes ALL these at once (hardest, cleanest).
   - **RUNTIME ENV (updated):** `sudo chmod 666 /dev/mali0 /dev/ion /dev/fb0`; `/system/build.prop`
     staged; `HYBRIS_LD_LIBRARY_PATH=/system/lib:/vendor/lib`; `LD_LIBRARY_PATH=<build>/{egl,glesv2,
     common,hardware,properties,libsync,egl/platforms/fbdev}/.libs`; `EGL_PLATFORM=fbdev`. Diagnostics:
     `strace -f`, `gdb -batch -ex run -ex "info proc mappings"` (blobs have no symbols; map PC→lib by
     range; resolve bionic offsets via `readelf -sW` on libc.so extracted from system.raw).
   - **STILL TODO after that:** wire GL into the LXQt/X11 desktop via patch `0002` (X11 EGL platform,
     needs xcb-drihybris + a bit more) OR keep fbdev for fullscreen GL apps. Package the whole thing as
     the `hybris/libhybris` + `hybris/android-headers` aports (drafts in `hybris/`, add the musl-port
     patch set from `hybris/musl-port/`).
   - **Backend = fbdev** (NOT hwcomposer): `hybris/egl/platforms/fbdev` `FbDevNativeWindow` calls the
     gralloc HAL `post()` → framebuffer. Matches our `gralloc.sc8830` (fbdev) + sprdfb `/dev/fb0`.
   - **configure flags:** `--enable-arch=arm --with-default-egl-platform=fbdev --enable-mali-quirks`
     `--with-android-headers=<API19> --with-default-hybris-ld-library-path=<staged /system/lib>`;
     NO `--enable-wayland`, NO `--enable-mesa`.
   - ⚠️ **BIGGEST STRATEGIC CALL — version-match libhybris to KitKat.** Our blobs = Android 4.4.4 /
     API 19, one of the OLDEST targets. libhybris master `hybris/common/` = {jb, mm, n, o, q, stub} —
     **no dedicated "kk"**; 4.4 rides the **`jb`** (Jelly Bean 4.1-4.3) linker path. Master is tuned for
     Android 7-13. → Evaluate an OLDER libhybris (mer-hybris 4.x-era, ~2016-2018) or the pmOS aport that
     targeted 4.x devices, vs bleeding-edge master, to cut bring-up pain. TEST the jb path first.
   - **Deps to gather:** android-headers for API19/4.4 (`mer-hybris/android-headers`, or extract from
     AOSP 4.4); the Android /system lib closure ✅ HAVE (`~/pmos-odin/gpu/blobs/` + rest in system.raw);
     version-matched libhybris source → package as an Alpine cross aport (armv7/musl).
   - **Staging:** put extracted `/system/lib{,/egl,/hw}` at the hybris ld path (e.g. `/usr/lib/droid`),
     set `EGL_PLATFORM=fbdev`; libhybris loads the bionic linker + blobs, opens `/dev/mali0`.
   - **Known first hurdle:** `test_egl`/`eglChooseConfig` assertion (classic hybris bring-up bug).
   - **Next-session order:** pick libhybris version → get API19 headers → write cross aport w/ flags
     above → stage /system + env → build → run `test_hardware`/`test_egl`/`test_glesv2` → `glmark2-es2`.
5. **Wire EGL** — hybris hwcomposer/fbdev backend → `gralloc.sc8830` → sprdfb `/dev/fb0` (mind
   `rgb_is_xrgb` vs our RGB565). Get hybris `test_egl`/`test_glesv2` rendering.
6. **Prove it** — `glmark2-es2` on the GPU; then optional GL-accelerated compositor.
Fallback if hybris won't bind on musl: document the wall, stay on software render (fully usable today).

### ⚠️⚠️ BIGGEST GOTCHA (learned the hard way): the bootloader IGNORES the boot.img cmdline
`/proc/cmdline` is the Spreadtrum bootloader's OWN hardcoded string (`mem=... init=/init
androidboot.bootloader=... console=null`). Our boot.img `pmos_root_uuid=` / `pmos.debug-shell`
/ etc. are **never passed**. Consequences:
- **Root is selected ONLY by the ext4 LABEL `pmOS_root`** (the initramfs scans for it). UUID
  pairing and cmdline edits have ZERO effect. Flashing a different boot.img changes nothing but the kernel/initrd blob.
- So **exactly ONE partition may be labeled `pmOS_root`.** With two rootfs (SYSTEM=console,
  userdata=lxqt) both labeled pmOS_root, it booted the first (SYSTEM). Fix: relabel the others:
  `sudo tune2fs -L pmOS_console /dev/mmcblk0p23` → only userdata is pmOS_root → boots lxqt.
- To switch which rootfs boots: just move the `pmOS_root` label (tune2fs -L), no reflash needed.

## STATUS (earlier 2026-07-28) — BOOTS + SSH + DISPLAY all WORK ✅✅✅
- Kernel `3.10.17 #N-postmarketOS` runs; `/` (pmOS_root) mounted rw; services up;
  **`ssh user@172.16.42.1` works**; **the console renders on the panel** (login prompt visible).
- Display was NOT a color/geometry bug: `# CONFIG_FRAMEBUFFER_CONSOLE is not set` (only a
  dummy vtcon existed) → nothing drew to the framebuffer, so the boot splash sat frozen. A raw
  red fill of /dev/fb0 proved the panel is perfect. Fix: enable `CONFIG_FRAMEBUFFER_CONSOLE=y`
  + `CONFIG_FONT_8x16=y` (in patch 0001) → readable console. (Same class as the seccomp fix.)
- **Remaining:** on-device input (tablet has NO keyboard — use SSH now, or a USB-OTG keyboard,
  or the eventual on-screen keyboard). Then per ROADMAP: hw inventory → Devuan (no systemd) → LXDE.

## 📋 TO-DO (prioritized — user's call 2026-07-28)
**P0 — 🔥 HACK THE GPU (Mali-400 via libhybris).** The mission. Full attack plan in the
"THE ULTIMATE HACK" section above. Everything else is secondary to this.

**P1 — Next kernel rebuild (ONE build, several payloads).** Enables the items below:
- `CONFIG_MALI400` + Mali kernel driver → `/dev/mali` (feeds the GPU hack).
- **`memfd_create` backport** → unlocks a *proper, good-looking* keyboard.
- Bluetooth stack: `CONFIG_BT` + `BT_HIDP` + `BT_HCIUART` + `BT_HCIUART_BCM`.
All go into `patches/0001-*.patch` + kernel `pkgrel` bump. Rebuild once, reap all three.

**P2 — Replace the ugly keyboard.** svkbd-mobile-intl works but is trashy (suckless gray).
Want a polished touch keyboard. GATED ON the `memfd_create` backport (P1): once the syscall
exists, **onboard** (GTK3, the nice pmOS tablet OSK) stops crashing → make it the default,
keep svkbd as fallback. (Also re-check maliit-keyboard, Qt-based, as an alternative.)

**P3 — Fix sound.** PulseAudio is installed but not producing audio. Investigate: is the
ASoC/sprd codec driver enabled in-kernel? does `aplay -l` list a card? PA sink state,
`/dev/snd/*` nodes, alsa-utils. May need a kernel audio-driver enable (fold into P1 rebuild if so).

**P4 — Bluetooth bring-up.** After P1 kernel enables BT: Broadcom BCM43xx over-UART firmware
load (`hciattach`/`btattach` + brcm patchram), then pair a wireless mouse/keyboard.

**P5 — Landscape rotation — ⛔ BLOCKED on current stack (investigated 2026-07-28).** Panel is
native portrait 800x1280; user wants 1280x800 landscape. ALL accessible paths fail:
(a) `xrandr --output default --rotate right` → *"output default cannot use rotation"* —
`xf86-video-fbdev` doesn't implement RandR rotation. (b) `xf86-video-fbturbo` (the software-rotate
driver) is NOT packaged in Alpine (only fbdev/vesa/dummy + HW drivers). (c) `/sys/class/graphics/
fb0/rotate` accepts a value but sprdfb IGNORES it (virtual_size/stride unchanged → no real rotation).
(d) libhybris/GPU won't help — hybris EGL is fbdev-based too, no DRM/KMS rotation. REAL options if
ever wanted: port `xf86-video-fbturbo` to modern Xorg ABI (aport, uncertain — 2013 driver), OR
implement rotation in the sprdfb kernel driver via the GSP 2D engine (CONFIG_VIDEO_GSP_SPRD, kernel
dev). Both are real sub-projects. DEFERRED. (staged xrandr script `~/pmos-odin/rotate/` is moot — fbdev rejects it.)

## The device (facts that matter)
- SM-T560 = **Spreadtrum** `gtelwifi` (NOT the Qualcomm SM-T560NU/`gtelwifiue`). armv7, panel 800x1280, WiFi-only (no modem).
- Partitions (from PIT): **SYSTEM = `/dev/mmcblk0p23`** (our rootfs), **KERNEL = p20** (Android
  `boot.img` lives here — flash filename is `boot.img`), **BOOT = p1** (SPL/bootloader — flash
  filename `spl.img`, DO NOT TOUCH), RECOVERY = p21.
- **Bootloader is never touched → download mode is ALWAYS reachable** (Vol Down+Home+Power → Vol Up).
  A failed flash shows "Firmware upgrade encountered an issue / Kies" — that's *not* a brick; reflash.
- **Recovery net:** stock firmware in `old-firmware/` (samfw ZTO, gitignored). Restore with:
  `sudo ~/.local/bin/odin4 -b <BL>.tar.md5 -a <AP>.tar.md5 -s <CSC>.tar.md5` (full absolute paths!).

## Repo layout
```
CLAUDE.md            ← this file
quest/               ← ROADMAP.md, PHASE0.md, PHASE1.md (full narrative + decisions)
patches/0001-*.patch ← ALL our pmaports changes (abuild rename, schema fix, CONFIG_SECCOMP, cmdline)
scripts/             ← setup-pmaports.sh, mksparse.py (Samsung sparse writer — REQUIRED for odin4)
vendor/SOURCES.md    ← irreplaceable kernel + wifi-blob sources mirrored to the repo's Release
pmaports/            ← pmOS clone, BUILD INPUT, gitignored. Branch quest-gtelwifi @ a1ceca353 + patches
old-firmware/        ← stock SM-T560 recovery firmware, gitignored (large, not ours)
```
Local (not in repo): `~/pmos-odin/` = working images/tars, `tablet_key` (SSH login key),
`keys/` (SSH host keys), `pamfix/` (PAM base-* files). Don't commit private keys.

## Toolchain (host = Linux Mint 22.3 / Ubuntu 24.04 base, x86_64)
- **pmbootstrap 3.11.1** (git install; PyPI is dead) → `~/.local/bin/pmbootstrap`.
  Config `~/.config/pmbootstrap_v3.cfg`: `device=samsung-gtelwifi`, `ui=console`,
  `service_manager=openrc` (**NO systemd** — the 3.10 kernel needs ≥4.x for systemd),
  `aports=<repo>/pmaports`. (It was hand-written; `pmbootstrap init` can't run headless.)
- **odin4** → `~/.local/bin/odin4` (Samsung's OFFICIAL Linux Odin v1.2.1, from github Adrilaw/OdinV4).
  **THE flasher for this device.** Needs `sudo`. `sudo odin4 -l` = non-destructive detect.
- **heimdall** = **DEAD END** — fails every large write at exactly 5%
  (`Failed to confirm end of file transfer sequence`) across all versions/cables/ports.
  `pmbootstrap flasher ...` uses heimdall, so **it does NOT work here.** Never flash with heimdall.

## ⚠️ CRITICAL GOTCHAS (the non-obvious stuff that cost hours)
1. **Flash only with odin4**, never `pmbootstrap flasher` / heimdall.
2. **system.img must be Samsung-style sparse** — build it with `scripts/mksparse.py`
   (RAW+DONT_CARE only, 32/16 headers, padded to full 384000-block partition). Plain raw
   images and `img2simg` default output are both REJECTED (`Fail request receive -1`).
3. **Use `install --split`** (bare ext4 boot+root images). The combined image is a whole-disk
   image with an MBR (`55aa`) that odin4 rejects.
4. **Kernel needs `CONFIG_SECCOMP=y`** (in patch 0001). Without it, OpenSSH 10's mandatory
   seccomp sandbox fails (`prctl(PR_SET_SECCOMP): Invalid argument`) and kills every SSH
   connection before the banner. Samsung shipped it off despite `HAVE_ARCH_SECCOMP_FILTER=y`.
5. **Two edge-snapshot bugs to patch into the rootfs offline (debugfs):**
   - `/etc/pam.d/` is MISSING `base-auth/account/password/session` (sshd includes them). Create
     them (see `pamfix/`; all `pam_*` modules exist). Needed for `UsePAM yes` auth.
   - `/etc/fstab` has a `/boot` line for a partition we don't flash → remove it.
6. **boot.img ↔ root.img must be a matched pair:** `boot.img` bakes `pmos_root_uuid=` on its
   cmdline; it MUST equal the root.img ext4 UUID. `install` regenerates both together — always
   flash boot+system from the SAME install run.
7. **pmbootstrap quirks:** edge base pkgs 404 → `pmbootstrap update` (+ delete stale
   `cache_apk_armv7/APKINDEX*` if needed). `losetup ... failed` / stale loops → `pmbootstrap
   shutdown` then retry. To force a device-pkg rebuild after editing its files, bump `pkgrel`
   AND update sha512 (can't run `pmbootstrap checksum` headless — `sha512sum` the file + sed the APKBUILD).
8. **USB net interface renames every boot** (random gadget MAC). NetworkManager tries DHCP,
   fails, drops it → always `nmcli device set <iface> managed no` first.

## RECONNECT to the tablet (already flashed & running)
```sh
IFACE=$(ls /sys/class/net | grep '^enx' | head -1)          # gadget name changes each boot
sudo nmcli device set "$IFACE" managed no
sudo ip link set "$IFACE" up && sudo ip addr add 172.16.42.2/24 dev "$IFACE"
ssh -i ~/pmos-odin/tablet_key user@172.16.42.1               # key login; pw = set at last install
```
Tablet is **`172.16.42.1` — SSH to `.1`, NOT `.2`** (`.2` is your PC). First connect prompts to
accept the ED25519 host key → type `yes`. Success = `Welcome to postmarketOS! o/` and a
`samsung-gtelwifi:~$` shell. If `$IFACE` is empty, the USB gadget hasn't enumerated yet — wait ~20s.

## BUILD → FLASH a new image (the full working loop)
```sh
# 0. (one-time per change) edit pmaports/ under scripts/setup or directly; bump pkgrel + re-checksum.
pmbootstrap shutdown                       # clear stale loops (avoids losetup error)
pmbootstrap -y install --split             # builds kernel (if changed) + boot.img + bare root.img
# rootfs offline fixes + repackage (done from the host with debugfs + mksparse.py):
#   - cp samsung-gtelwifi-root.img root.img ; drop /boot from fstab ; add pam base-* ; inject keys
#   - python3 scripts/mksparse.py root.img system.img          # Samsung sparse
#   - cp <chroot_rootfs>/boot/boot.img boot.img                # matched pair!
#   - tar -H ustar -cf pmos.tar boot.img system.img ; md5sum -t pmos.tar >> pmos.tar ; mv .md5
# flash (tablet in download mode):
sudo ~/.local/bin/odin4 -a /home/prolog/pmos-odin/pmos.tar.md5
```
Images live in `~/.local/var/pmbootstrap/chroot_native/home/pmos/rootfs/samsung-gtelwifi-{boot,root}.img`
and the boot.img in `~/.local/var/pmbootstrap/chroot_rootfs_samsung-gtelwifi/boot/boot.img`.

## PAM base-* files (needed in the rootfs; from `pamfix/`)
- base-auth:     `auth [success=1 default=ignore] pam_unix.so nullok` / `auth requisite pam_deny.so` / `auth required pam_permit.so`
- base-account:  `account [success=1 new_authtok_reqd=done default=ignore] pam_unix.so` / `account requisite pam_deny.so` / `account required pam_permit.so`
- base-password: `password [success=1 default=ignore] pam_unix.so obscure sha512` / `password requisite pam_deny.so` / `password required pam_permit.so`
- base-session:  `session required pam_limits.so` / `session required pam_env.so` / `session required pam_unix.so`

## Remaining work
Display, SSH, touch, WiFi, keyboard all DONE (see STATUS). Open fronts:
1. **Next kernel rebuild** (one build, three payloads): (a) **Bluetooth** — `CONFIG_BT` +
   `BT_HIDP` + `BT_HCIUART` + `BT_HCIUART_BCM` for wireless mouse/kbd; (b) **`memfd_create`
   backport** (fixes GTK3 apps incl. onboard); (c) **Mali-400 kernel driver** (`CONFIG_MALI400`)
   for the GPU hack. All go in patch 0001 + kernel `pkgrel` bump.
2. **THE ULTIMATE HACK: Mali-400 GPU via libhybris** — see the dedicated section up top.
3. **elogind session** — tinydm autologin doesn't create an elogind session (empty
   XDG_RUNTIME_DIR, dconf/polkit gaps). The WiFi polkit rule papers over it; a proper
   `pam_elogind` in the autologin PAM stack is the real fix.

## History / details
`quest/PHASE0.md` (build), `quest/PHASE1.md` (flash + SSH saga), `quest/ROADMAP.md` (plan + decisions),
`vendor/SOURCES.md` (mirrored sources). GitHub: thiemmerich/samsung-gtelwifi-project.
