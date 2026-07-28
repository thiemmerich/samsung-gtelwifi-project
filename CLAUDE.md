# CLAUDE.md — Samsung Galaxy Tab E (SM-T560 / gtelwifi) → postmarketOS

Master reference for this hobby project. Detailed narrative lives in `quest/*.md`;
this file is the quick-orient + the reproducible recipe. **Read this first.**

## What this is
Bring a modern-ish Linux to a 2015 **Samsung Galaxy Tab E 9.6 (SM-T560, `gtelwifi`,
Spreadtrum SC7730, armv7)** by gluing the postmarketOS reverse-engineered **downstream
3.10 kernel** (working display + BCM4343 WiFi) to a lightweight userspace. NOT a
Raspberry-Pi-OS port (Broadcom kernel can't move) — it's kernel-glue + a Debian-family
rootfs. End goal: **Devuan (no systemd) + LXDE**, Windows-like feel. See `quest/ROADMAP.md`.

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
