# Samsung Galaxy Tab E 2015 (gtelwifi)

[🇺🇸 English](README.md) · [🇧🇷 Português (Brasil)](README.pt-br.md)

A hobby quest to bring a modern-ish Linux desktop to a 2015 **Samsung Galaxy Tab E
9.6 (SM-T560, `gtelwifi`, Spreadtrum SC7730)** by **gluing the postmarketOS
reverse-engineered downstream kernel** (working display + WiFi) to a **Devuan
userspace with an LXDE desktop**.

> Not a "port of Raspberry Pi OS" — that's impossible (Broadcom-specific kernel).
> Instead: keep the pmOS 3.10 kernel that already drives this hardware, and put a
> Debian-family (Devuan, no systemd) userspace on top of it.

See **[quest/ROADMAP.md](quest/ROADMAP.md)** for the full plan, decisions, and phase checklist.

## Repo layout

```
samsung-gtelwifi-project/
├── quest/        # our roadmap, notes, capability sheet, logs
├── patches/      # our diffs to the gtelwifi kernel/device packages
├── scripts/      # setup / build / flash helpers
├── vendor/       # provenance + checksums for the mirrored irreplaceable sources
└── pmaports/     # pmOS clone — BUILD INPUT, gitignored (recreate via script)
```

The `pmaports/` tree is upstream postmarketOS and is **not** committed here — it is
reproducible. Recreate it with:

```sh
./scripts/setup-pmaports.sh
```

That clones pmaports and checks out our known-good pre-archival commit `a1ceca353`
(where `gtelwifi` still lives in `device/downstream/`) on a `quest-gtelwifi` branch.

## Status — a working, GPU-rendering tablet 🎉

What started as "can this 2015 tablet even boot Linux?" is now a **booting LXQt desktop, driven by
touch, on WiFi, with the proprietary Mali-400 GPU rendering OpenGL ES 2.0 under musl** — plus a
precisely-mapped path to a fully GPU-composited desktop. Full technical log & reproducible recipe:
**[CLAUDE.md](CLAUDE.md)**.

### What works now
- ✅ **Built & flashed** — `samsung-gtelwifi.img` built with pmbootstrap and flashed (Odin/heimdall);
  boots the pmOS reverse-engineered **3.10 kernel** with working display + BCM4343 WiFi.
- ✅ **LXQt desktop** on the panel, driven by the **touchscreen**; battery/power read correctly.
- ✅ **WiFi** (BCM4343 / `brcmfmac`).
- ✅ **On-screen keyboard** — `onboard` (GTK), docked at the bottom, auto-starts with the session.
- ✅ **No more screen-blanking deaths** — the screensaver (which this panel couldn't wake from) is
  permanently disabled.
- 🏆 **Mali-400 GPU renders OpenGL ES 2.0** — the headline hack, below.

### 🏆 The GPU hack (the hard one)
The desktop chrome is CPU/software-rendered, but we got the **proprietary Android Mali-400 GPU blob
(`libGLES_mali.so`, KitKat / DDK r4p1) running on postmarketOS/musl** — believed to be the first
KitKat-era libhybris port to musl. Every layer solved end-to-end:
- Ported the **Mali kernel driver** → `/dev/mali0` (`patches/0002-mali-gpu-driver.patch`).
- **libhybris musl port** — the bundled bionic linker dlopens the Android blobs; a hooks table
  bridges their libc/pthread calls to musl.
- Worked around the **bionic↔musl thread-register (TLS) collision** with a pthread stub
  (single-threaded, enough to render).
- Fixed the display pipeline: **16bpp RGB565 stride pin**, **linear scanout buffer** (killed the Mali
  tile-writeback grid), and a software **RGBA8888→RGB565 downconvert** (correct colors).
- **Result:** crisp, correct-color GLES2 — validated by a lit, depth-buffered, spinning 3D cube
  (`gpu-demos/gpu_cube.c`) at **~22–28 fps**, with the driver reporting `GL_RENDERER=Mali-400 MP`.

All patch scripts and the step-by-step recipe live in `hybris/musl-port/` and **[CLAUDE.md](CLAUDE.md)**.

### In progress / next
- 🔊 **Sound** — the Spreadtrum codec is present (ALSA `card0 sprdphone`, `sprd-codec` HiFi/Voice/FM);
  the DAPM playback route (DAC→speaker/HP) isn't fully engaging yet. A focused codec-driver deep-dive
  is queued (no vendor `mixer_paths.xml` / DAPM debugfs, so it's a from-scratch bring-up).
- 🔵 **Bluetooth** — BCM4343 combo BT (rfkill unblocked); needs `hciattach` + a firmware `.hcd`.
- 🌈 **The dream — a fully GPU-composited desktop.** Gated on a real **bionic-TLS bridge** (to replace
  the single-threaded pthread stub) → then a libhybris-EGL Wayland compositor. The blocker is
  diagnosed and the implementation planned in **[hybris/musl-port/TLS_BRIDGE_PLAN.md](hybris/musl-port/TLS_BRIDGE_PLAN.md)**;
  deferred until the daily-usable pieces (sound, Bluetooth) are done.

> Note: the end-goal userspace is still **Devuan + LXDE**; current bring-up runs **postmarketOS
> (Alpine/musl) + LXQt**, which is where all the hardware wins above were proven.

See also [quest/ROADMAP.md](quest/ROADMAP.md), [quest/PHASE0.md](quest/PHASE0.md),
[quest/PHASE1.md](quest/PHASE1.md).

## Phase 0 findings (what it took to revive the port)

The port was archived for being **unmaintained, not broken**. Reviving it from commit
`a1ceca353` was mostly fixing drift between June's pin and July's tooling:

- **pmbootstrap** now installs from git (all PyPI releases were yanked). Its interactive
  `init` (no TTY under automation) was bypassed with a hand-written
  `~/.config/pmbootstrap_v3.cfg` + work dir.
- Forced `service_manager = openrc` — **no systemd** (systemd needs a ≥4.x kernel; ours is 3.10).
- **The kernel builds clean on GCC 15.2.0** — the feared "GCC 15 vs a 2015 kernel" wall
  never appeared; the existing gcc7/8/10 patches sufficed. *(Blocker 1 cleared.)*
- Two one-line fixes, kept as reproducible patches (auto-applied by `scripts/setup-pmaports.sh`):
  - **`patches/0001`** — current `abuild` forbids commas in source filenames
    (`fix-dtb_qcom,msm-id.patch` → `fix-dtb_qcom-msm-id.patch`).
  - **`patches/0002`** — `deviceinfo_schema.toml` `header_version` needed `datatype = "integer"`
    next to its `integer_interval` (now enforced).
- The WiFi firmware package (`firmware-samsung-gtelwifi`, under `device/testing/`) must be
  **built separately** before `pmbootstrap install`.
- **Edge drift**: base packages rotate fast (e.g. `postmarketos-base` 65→66-r0). On 404s:
  `pmbootstrap update`, and clear stale `cache_apk_armv7/APKINDEX*` if they persist.

Result: a flashable `samsung-gtelwifi.img` — console UI, OpenRC, the 3.10 kernel + BCM4343 firmware.
