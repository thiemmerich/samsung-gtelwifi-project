# Vendored sources (disaster-recovery mirror)

The build depends on a few **device-specific, irreplaceable** upstream sources that could
disappear (an old single-commit mirror, old Android vendor repos). We mirror them as assets
on the **`vendor-sources`** GitHub Release of this repo, each verified byte-for-byte against
the sha512sum already declared in the pmaports APKBUILDs.

Release: <https://github.com/thiemmerich/samsung-gtelwifi-project/releases/tag/vendor-sources>

| Asset | What it is | Upstream (original) | commit |
|-------|-----------|---------------------|--------|
| `kernel-src-e81e8d5.tar.gz` (113M) | Samsung 3.10.17 kernel source | `github.com/pmsourcedump/linux-samsung-sm-t560` | `e81e8d5…` |
| `firmware-blob-c055948.tar.gz` (4.6M) | BCM4343 WiFi blob (`bcmdhd_mfg.bin`) | `github.com/gtelwifi/android_vendor_samsung_gtelwifi` | `c055948…` |
| `firmware-config-63c2705.tar.gz` (5.3M) | WiFi nvram config | `github.com/gtelwifi/android_device_samsung_gtelwifi` | `63c2705…` |

## sha512sums (identical to the APKBUILDs)
```
1d951c9e33d79250513665a617867816d81df866e869ba20664c9f4b2f05845e6ff7c667ba0ef11f9287109e6716d1b45164848a750e36202c4f95665759a2aa  kernel-src-e81e8d5.tar.gz
fd87407a42642853c5ac608512a60f7dc91d991d28da675d4b6f4e38e0f9494749c00dc63394b09d0df6922f3407c6ba4310cb0a28fef4425190246fe5618c2e  firmware-blob-c055948.tar.gz
3d8917e7b6a5d4f2610dc623f4c52917024b055a70908ab86994a4171eddca4580fdca3e13769ae5b77a23c69345062a3e92ca9a9cc3122b49ddf8f9e619238d  firmware-config-63c2705.tar.gz
```

## If upstream dies: redirect the build to these mirrors
The bytes are identical, so only the URL changes — pmbootstrap still verifies the sha512,
so a wrong/corrupt mirror would be caught.

- In `pmaports/device/downstream/linux-samsung-gtelwifi/APKBUILD`, repoint the kernel source:
  ```
  $pkgname-$_commit.tar.gz::https://github.com/thiemmerich/samsung-gtelwifi-project/releases/download/vendor-sources/kernel-src-e81e8d5.tar.gz
  ```
- In `pmaports/device/testing/firmware-samsung-gtelwifi/APKBUILD`, repoint both sources:
  ```
  …/releases/download/vendor-sources/firmware-blob-c055948.tar.gz
  …/releases/download/vendor-sources/firmware-config-63c2705.tar.gz
  ```

## Committed directly in this repo (small, so no Release needed)
- **`vendor/mali-utgard-sc8830-r4p1.tar.gz`** (242 KB) — the Mali-400 Utgard **kernel** driver
  (`drivers/gpu/mali/`, 148 files, GPL-2.0). Extracted from
  `github.com/codeworkx/android_kernel_samsung_gtelwifi` branch `cm-11.0`, commit
  `60871e9801b01f445fb184362a9976c1807ff289`. Factory-matched to the stock KitKat `libGLES_mali.so`
  r4p1 userspace blob. `setup-pmaports.sh` copies it into the kernel aport dir, where the APKBUILD
  (patched by `patches/0002-mali-gpu-driver.patch`) consumes it as a local source.
  ```
  de6bb31b921bb201fdb0a7fa94f5064e776adf97c1de5200f64f07a1b4f87d3695379b63e6b1e3e81c65eb1e935471d6d6df7be5e56bd86f88571757338a7490  mali-utgard-sc8830-r4p1.tar.gz
  ```
  (NOTE: the proprietary **userspace** GPU blobs — `libGLES_mali.so` etc. — are NOT committed; they
  live only in `~/pmos-odin/gpu/blobs/`. They're for the upcoming libhybris step, and are ARM/Samsung
  proprietary, so they must never go in this public repo.)

## libhybris musl-port patches (in `hybris/musl-port/`)
For the GPU-userspace step (see `../CLAUDE.md` "THE ULTIMATE HACK"):
- `0001-Make-libhybris-compile-with-musl.patch`, `0002-Implement-X11-EGL-platform-based-on-wayland-code.patch`
  — pmOS's libhybris musl + X11-EGL patches, recovered from the (now-removed-upstream) pmaports
  `hybris/libhybris` aport as preserved in the fork **`Linux-On-Sdm6Series/pmaports@halium9`**. They
  apply to **libhybris commit `1b6090ad6e420fe2139685e0af54fd94edb7d049`** (pmOS pkgver `1.0_git20200504`).
- `linux-sync.h`, `linux-sw_sync.h` — minimal Android sync-framework UAPI (dropped from modern
  linux-headers); install to `/usr/include/linux/` to build libhybris `libsync`.
- `hybris_musl_compat.h` — earlier hand-port scratch header (superseded by 0001; kept for reference).
NOTE: the proprietary Android GPU **userspace blobs** (`libGLES_mali.so` etc.) are NOT vendored here
(ARM/Samsung proprietary) — they live only in `~/pmos-odin/gpu/blobs/` + are re-extractable from
`old-firmware/`'s `system.img` with `scripts/unsparse.py` + `debugfs`.

## Deliberately NOT vendored
- **Alpine/pmOS base binary packages** — rolling edge, hundreds of MB, replaceable. If they
  404, refresh with `pmbootstrap update` (see quest/PHASE0.md).
- **Full pmaports tree + pmbootstrap** — public git; our delta is captured in `patches/`.

## Why a Release and not git / split files
GitHub's 100 MB limit is for files committed to git. Release assets allow up to 2 GB, so the
113 MB kernel fits without splitting and without bloating every clone's history.
