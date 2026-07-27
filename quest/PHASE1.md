# Phase 1 — First hardware contact (boot pmOS on the tablet)

**Goal:** flash the Phase-0 image and prove the kernel actually drives the real
hardware (screen via sprdfb, login, dmesg, then WiFi). This is the first step that
touches the device and is *not* reversible-for-free.

## Status — comms VERIFIED (2026-07-24)
Charge-only cables were the blocker; a real data cable fixed it. With a data cable +
download mode:
- `lsusb`: `04e8:685d SAMSUNG USB DRIVER (Download mode)`, high-speed link.
- `heimdall detect` -> **Device detected** (no sudo needed; udev perms OK). heimdall v2.0.2.
- `heimdall print-pit --no-reboot` -> exit 0, full partition table read, clean session.
  Partitions incl.: BOOT BOOT2 SBOOT MODEM PARAM efs KERNEL RECOVERY CSC SYSTEM userdata.
=> **bidirectional comms proven** — we can flash AND recover. Rule 0 read-path satisfied.

### Remaining gate before the (destructive) flash
- [ ] **Stock SM-T560 firmware** downloaded (the undo button).
- [ ] Tablet **backed up** (flash wipes it).
Flash targets: boot.img -> BOOT partition, rootfs -> SYSTEM partition.

### Resume point (paused mid-session)
Comms verified; only the stock firmware (recovery net) is left before flashing.
- Get firmware: samfw.com/firmware/**SM-T560** (NOT T560NU). Drill in: region -> a
  build (`T560XXU…`) -> Download button is on the build page (below the info table).
  Brazil CSC = ZTO/ZTA/BTU; if absent, ANY SM-T560 build restores a bootable tablet.
  Alternatives: Frija tool, samfrew.com, sammobile.com.
- No user data to back up (game tablet). Bootloader untouched -> download mode always
  reachable, so a true brick isn't possible.
- heimdall v2.0.2 CANNOT dump partition contents (only detect / download-pit / flash),
  so no heimdall-based backup — stock firmware is the recovery net.
- THEN flash: `pmbootstrap flasher flash_kernel` + `pmbootstrap flasher flash_rootfs`
  (device in download mode), then power on and watch for screen + console login.

## Artifacts from Phase 0
- rootfs: `~/.local/var/pmbootstrap/chroot_native/home/pmos/rootfs/samsung-gtelwifi.img`
- kernel+initramfs: `~/.local/var/pmbootstrap/chroot_rootfs_samsung-gtelwifi/boot`
- flash method: `heimdall-bootimg` (Samsung download mode)

## RULE 0 — RECOVERY BEFORE FLASHING (non-negotiable)
Do NOT flash pmOS until we can prove we can put the tablet back to stock.
- [ ] Download **stock SM-T560 firmware** matching the exact model + region
      (samfw.com / Frija / SamMobile). Keep the Odin `.tar.md5` files.
- [ ] Have a way to flash stock back: **Odin** (Windows) or **heimdall** (Linux).
- [ ] Install heimdall on Mint: `sudo apt install heimdall-flash`.
- [ ] Enter **download mode**: power off; hold **Vol Down + Home + Power**;
      press **Vol Up** to confirm.
- [ ] Non-destructive detection test:
      `heimdall detect`  (device seen?)  and  `heimdall print-pit`  (reads the
      partition table — proves comms work without writing anything).
- [ ] Confidence check: know how to reflash stock if the boot fails/bricks.

## THEN — flash pmOS (only after Rule 0 is satisfied)
```sh
pmbootstrap flasher flash_kernel     # boot.img (kernel + initramfs) -> boot partition
pmbootstrap flasher flash_rootfs     # rootfs image -> system partition
```
(Device must be in download mode; these use heimdall under the hood.)

## Boot & verify (the Phase-1 payoff)
- [ ] Screen lights up (sprdfb) — the whole point.
- [ ] Reaches the console UI / getty; log in as `user` with the install password.
- [ ] `dmesg` readable; capture it to `quest/` for the Phase-2 hardware inventory.
- [ ] Try WiFi (BCM4343): `nmtui` / `nmcli` to connect.

## If it goes wrong
Reflash stock firmware via Odin/heimdall (download mode is almost always still
reachable). That's why Rule 0 comes first.

## Exit criterion
Tablet boots our pmOS image to a usable console with the screen working. Then
Phase 2 (full hardware inventory) and later Phase 3 (swap to Devuan).
