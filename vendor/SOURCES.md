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

## Deliberately NOT vendored
- **Alpine/pmOS base binary packages** — rolling edge, hundreds of MB, replaceable. If they
  404, refresh with `pmbootstrap update` (see quest/PHASE0.md).
- **Full pmaports tree + pmbootstrap** — public git; our delta is captured in `patches/`.

## Why a Release and not git / split files
GitHub's 100 MB limit is for files committed to git. Release assets allow up to 2 GB, so the
113 MB kernel fits without splitting and without bloating every clone's history.
