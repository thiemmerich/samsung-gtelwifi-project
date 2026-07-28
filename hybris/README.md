# hybris/ — libhybris GPU userspace for gtelwifi (Mali-400, classic bare-metal model)

Goal: run the stock **Android 4.4.4 (API 19) Mali-400 `libGLES_mali.so` r4p1** blob on our
Alpine/musl userspace, talking to the in-kernel Mali driver at `/dev/mali0` (already working —
see `../CLAUDE.md`). This is the last step of "THE ULTIMATE HACK".

## Model: CLASSIC bare-metal (NOT Halium/container)
Modern libhybris usage (Chimera, Ubuntu Touch) runs Android in an LXC container and builds
libhybris with `--enable-stub-linker` + Wayland + Android-11 headers. **We do the opposite** —
the old Sailfish/Mer / ODROID-KitKat approach:
- **No Android container.** libhybris's own bundled bionic linker (`hybris/common/jb` for KitKat)
  `dlopen`s the vendor blobs directly.
- Blobs are staged on disk (from `~/pmos-odin/gpu/blobs/` + the rest in `system.raw`) at a path on
  `HYBRIS_LD_LIBRARY_PATH`, e.g. `/vendor/lib:/system/lib:/system/vendor/lib`.
- EGL backend = **fbdev** → gralloc.sc8830 `post()` → sprdfb `/dev/fb0`. No Wayland, no hwcomposer.

## Packages (drafts here → copied into pmaports `temp/` by setup-pmaports.sh, TODO)
- `android-headers/` — Android userspace headers for **API 19 / KitKat**. libhybris derives the
  target Android version (→ which linker dir) from these. **OPEN:** pin the source —
  candidate (a) `mer-hybris/android-headers` at a 4.4/JB-era ref; (b) generate with libhybris
  `utils/extract-headers.sh <AOSP-4.4-tree> 19`. Chimera's uses Halium-11 (too new for us).
- `libhybris/` — the compat layer + EGL/GLES wrappers, classic flags (see its APKBUILD).

## Build / test flow (needs the tablet up)
1. `pmbootstrap build android-headers && pmbootstrap build libhybris` (armv7/musl, under qemu).
2. Stage the blobs + set env on-device (script TBD): `HYBRIS_LD_LIBRARY_PATH`, `EGL_PLATFORM=fbdev`.
3. Smoke test in order: `test_hardware` (loads a HAL) → `test_egl` (eglInitialize/ChooseConfig —
   classic first-hurdle: an `eglChooseConfig` assert) → `test_glesv2` → `glmark2-es2`.

## Status
Skeletons only — flags/structure correct for the classic model; the two OPEN items above must be
resolved before a real build. Not yet wired into pmaports.
