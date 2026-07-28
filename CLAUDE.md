# CLAUDE.md — Samsung Galaxy Tab E (SM-T560 / gtelwifi) → postmarketOS

Master reference for this hobby project. Detailed narrative lives in `quest/*.md`;
this file is the quick-orient + the reproducible recipe. **Read this first.**

## What this is
Bring a modern-ish Linux to a 2015 **Samsung Galaxy Tab E 9.6 (SM-T560, `gtelwifi`,
Spreadtrum SC7730, armv7)** by gluing the postmarketOS reverse-engineered **downstream
3.10 kernel** (working display + BCM4343 WiFi) to a lightweight userspace. NOT a
Raspberry-Pi-OS port (Broadcom kernel can't move) — it's kernel-glue + a Debian-family
rootfs. End goal: **Devuan (no systemd) + LXDE**, Windows-like feel. See `quest/ROADMAP.md`.

## STATUS (2026-07-28) — BOOTS + SSH + DISPLAY all WORK ✅✅✅
- Kernel `3.10.17 #N-postmarketOS` runs; `/` (pmOS_root) mounted rw; services up;
  **`ssh user@172.16.42.1` works**; **the console renders on the panel** (login prompt visible).
- Display was NOT a color/geometry bug: `# CONFIG_FRAMEBUFFER_CONSOLE is not set` (only a
  dummy vtcon existed) → nothing drew to the framebuffer, so the boot splash sat frozen. A raw
  red fill of /dev/fb0 proved the panel is perfect. Fix: enable `CONFIG_FRAMEBUFFER_CONSOLE=y`
  + `CONFIG_FONT_8x16=y` (in patch 0001) → readable console. (Same class as the seccomp fix.)
- **Remaining:** on-device input (tablet has NO keyboard — use SSH now, or a USB-OTG keyboard,
  or the eventual on-screen keyboard). Then per ROADMAP: hw inventory → Devuan (no systemd) → LXDE.

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
1. **Display** (current): garbled 16bpp. Diag: sprdfb, bpp=16, stride=1600 (correct), 800x1280.
   Investigate `/dev/fb0` color format (RGB565 vs BGR565), fbcon; the kernel already has
   `sprdfb-fix-swapped-colors`. Fix live over SSH; you'll need to eyeball the screen per attempt.
2. Then per `quest/ROADMAP.md`: Phase 2 hw inventory → Phase 3 swap Alpine console → Devuan →
   Phase 4 LXDE + PIXEL-style theming.

## History / details
`quest/PHASE0.md` (build), `quest/PHASE1.md` (flash + SSH saga), `quest/ROADMAP.md` (plan + decisions),
`vendor/SOURCES.md` (mirrored sources). GitHub: thiemmerich/samsung-gtelwifi-project.
