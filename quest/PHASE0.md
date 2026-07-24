# Phase 0 — Host-side build setup (log)

Goal: get pmbootstrap configured and cross-compile the downstream 3.10 kernel,
with zero risk to the tablet.

## Environment
- Host: Linux Mint 22.3 (Ubuntu 24.04 base), Python 3.12, x86_64
- pmbootstrap: **3.11.1**, installed from git (PyPI releases were all yanked —
  the project moved to git-only install). Symlinked to `~/.local/bin/pmbootstrap`.
- pmaports: our clone at `pmaports/`, branch `quest-gtelwifi` @ `a1ceca353`
  (pre-archival; `gtelwifi` still live in `device/downstream/`).

## Kernel build recipe (from device/downstream/linux-samsung-gtelwifi/APKBUILD)
- Kernel: Samsung fork **3.10.17**, config `gtelwifi-dt_hw07_defconfig`
- Source: GitHub mirror `pmsourcedump/linux-samsung-sm-t560` @ `e81e8d5…` (confirmed live)
- Cross-compiled (`pmb:cross-native`), builds a master DTB via `dtbtool` (qcdt)

## pmbootstrap config — done NON-interactively
`pmbootstrap init` is interactive and dies with "EOF when reading a line" when run
through the agent (no TTY on stdin). We routed around it entirely:

1. pmbootstrap `config` needs a config file first; `init` normally creates it.
2. Config is `~/.config/pmbootstrap_v3.cfg` (INI, `[pmbootstrap]` section).
   Hand-wrote it — verified `Config.__setattr__` coerces values (e.g. the
   `service_manager` enum) so a hand-written file loads identically to init's.
3. `init` also creates the work dir; replicated it: `~/.local/var/pmbootstrap/`
   with a `version` file (content `8` = `pmb.config.work_version`) and `cache_git/`.

Resulting `pmbootstrap status`:
```
Channel: edge (pmaports: quest-gtelwifi)   # plain edge, not systemd-edge
Device:  samsung-gtelwifi (armv7)
UI:      console
systemd: no (openrc selected)
```
Key win: forced `service_manager = openrc` so NO systemd (critical for the 3.10 kernel).

## Blocker: chroot/build needs sudo (TTY)
`pmbootstrap chroot` runs `sudo mkdir .../chroot_native/dev`. sudo needs an
interactive password prompt, which the agent's shell can't provide. So the actual
**build must be run in a real terminal by the user.** (Set `sudo_timer = True` in
the config so the long build doesn't re-prompt.)

## NEXT: run the build (USER, in a normal terminal)
```sh
pmbootstrap -y build linux-samsung-gtelwifi
```
This will: bootstrap the native chroot (asks sudo password once), download the
cross-toolchain + kernel source (~hundreds of MB), then compile the 3.10 kernel.

**This is the Blocker-1 test** — does the 2015 kernel still build on a modern
toolchain? Paste the tail of the output back:
- Success → look for `linux-samsung-gtelwifi-*.apk` built. Then Phase 1 (flashing).
- Failure → almost certainly a GCC/compile error; paste it and we patch (there are
  already gcc7/8/10 survival patches in the package to extend).

## Build attempt 1 (2026-07-24)
Got past DNS (transient) and toolchain setup. Cross-compiler installed:
**gcc-armv7 15.2.0** (GCC 15 vs a 2015 kernel — noted for later).

Failed NOT at compile but at APKBUILD *validation*:
```
>>> ERROR: linux-samsung-gtelwifi: Forbidden character(s) in filename
    fix-dtb_qcom,msm-id.patch: ,
```
Cause: current `abuild 3.18.0_rc3` forbids commas in source filenames; the pinned
package (fine in June 2026) has `fix-dtb_qcom,msm-id.patch`. Pure tooling drift.

**Fix** (patches/0001-abuild-forbid-comma-in-source-filename.patch):
renamed `fix-dtb_qcom,msm-id.patch` -> `fix-dtb_qcom-msm-id.patch` and updated the
APKBUILD `source=` + `sha512sums` (content/hash unchanged, only the name).

The actual kernel compile still hasn't run — re-run the build to reach it.
