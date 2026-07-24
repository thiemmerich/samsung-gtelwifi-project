# Quest: Raspbian-flavored Linux on the Samsung Galaxy Tab E (SM-T560)

**One-line goal:** Glue the postmarketOS reverse-engineered downstream kernel (working
display + WiFi) to a Devuan userspace styled like Raspberry Pi OS (LXDE desktop),
on a 2015 Spreadtrum tablet.

## The device
- **Model:** Samsung Galaxy Tab E 9.6 — SM-T560
- **Codename:** `samsung-gtelwifi` (Spreadtrum variant — NOT `gtelwifiue`, which is Qualcomm)
- **SoC:** Spreadtrum SC7730 · **Arch:** `armv7` · **Screen:** 800x1280
- **Flash method:** `heimdall-bootimg` (Samsung download mode; heimdall = Linux Odin)

## The core idea (say it precisely)
"Raspberry Pi OS" = a Broadcom-specific kernel/firmware (CANNOT be ported) + a Debian armhf
userspace (portable to any armv7 device with a working kernel). So we do NOT port an OS. We:

  [ pmOS downstream 3.10 kernel + sprdfb + BCM4343 ]  <- the crown jewel, already solved
  +  [ Devuan armhf userspace + LXDE, Raspbian-styled ] <- the swappable, easy half
  =  a usable Linux tablet

## Known-good base (from git archaeology)
- Port was **archived 2026-06-22** by a `treewide: archive unmaintained packages` sweep —
  administrative (no maintainer), **NOT because it broke**. It was live ~1 month ago.
- **Resurrection commit:** `a1ceca353` (parent of the archival commit `cfbc1de3c`).
  At that commit, the package lives in `device/downstream/device-samsung-gtelwifi`.
- Plan: build from that commit + a matching ~June-2026 pmbootstrap. Recent = likely still builds.

## The two blockers (honest)
1. **Kernel build:** a 2015-era 3.10 kernel fights modern toolchains (hence all the gcc7/8/10
   fixup patches). Mitigated by using the era-matched pmbootstrap/Alpine SDK, not the latest.
2. **Old kernel vs modern userspace:** modern systemd needs kernel >=4.x -> breaks on 3.10.
   SOLVED by choosing Devuan (Debian minus systemd). glibc itself is fine on 3.10.

## Kernel policy
The 3.10 downstream kernel is **permanent**. Forward-porting Spreadtrum drivers to mainline is
graveyard-tier and out of scope. "Kernel upgrade" is NOT a project goal; making the old kernel
pleasant is. Keep pmOS's exact kernel + its exact modules together — never mix ABIs.

## Decisions locked
- **Userspace distro: Devuan** (Debian-family, no systemd, kernel-safe, runs .debs).
  - Rejected: modern Raspbian/Debian (systemd fights kernel), Arch Linux ARM (worst — newest
    systemd), old Raspbian (authentic but EOL/stale).
  - **Alpine** is used ONLY as the Phase-1 bring-up vehicle (musl can't run .debs long-term).
- **Desktop: LXDE** — lightest real DE, no compositor (fits no-GPU), Windows-style taskbar,
  and it's the base of Raspberry Pi OS's PIXEL desktop -> free "Raspbian flavor."
  - Rejected: GNOME/Plasma/Cinnamon (need GPU/compositing). Fallback if sluggish: IceWM.

## Roadmap (climb the ladder — each rung is a shippable win)

### Phase 0 — Host-side build, zero device risk
- [ ] Create working branch at commit `a1ceca353`.
- [ ] Install the matching pmbootstrap (~June 2026 release).
- [ ] `pmbootstrap init` -> select samsung / gtelwifi.
- [ ] Build kernel + device pkg; produce a bootable Alpine image.
- **Exit criterion:** it *compiles* and yields an image. De-risks Blocker 1 before touching hardware.

### Phase 1 — First hardware contact (boot Alpine)
- [ ] **RECOVERY FIRST:** download stock SM-T560 firmware; confirm Odin/heimdall download-mode
      re-flash works. Never flash anything experimental until unbrick is proven.
- [ ] Research serial/UART console access (the debugging lifeline).
- [ ] heimdall-flash the pmOS boot image; boot to pmOS console/UI.
- **Exit criterion:** screen lights up, we can log in, `dmesg` readable. Kernel lives on-device.

### Phase 2 — Hardware inventory (reality vs wiki)
- [ ] Test each subsystem on booted Alpine and record PASS/FAIL:
      display · touch · WiFi(BCM4343) · Bluetooth · audio · battery% · charging · sensors ·
      USB-OTG host · SD card.
- **Exit criterion:** an honest capability sheet — defines what the final product can do.

### Phase 3 — Glue on Devuan (the actual "port")
- [ ] Keep pmOS kernel + boot image untouched. Build a Devuan armhf rootfs (debootstrap).
- [ ] Copy kernel modules into rootfs `/lib/modules/<ver>`; add BCM4343 firmware blob.
- [ ] Wire root=, fstab, cmdline; init = sysvinit/OpenRC (no systemd).
- **Exit criterion:** boots to a Devuan console with WiFi.

### Phase 4 — Raspberry Pi OS flavor (LXDE)
- [ ] Software-rendered X (fbdev/fbturbo on sprdfb — no GPU accel).
- [ ] Install LXDE; optionally pull PIXEL theming from the Raspberry Pi apt repo (skip rpi-only deps).
- [ ] Bump UI element sizes for touch; touch calibration; on-screen keyboard (onboard/matchbox).
- **Exit criterion:** boots to an LXDE (Raspbian-looking) desktop, usable (sluggish, software-rendered).

### Phase 5 — Polish
- [ ] Fix power-button-instant-shutdown (known pmOS bug).
- [ ] Autologin, light display manager (LightDM hung on pmOS — try nodm/startx).
- [ ] Brightness, suspend, battery behavior.

## Who does what
- **Claude (host side):** git checkouts, build config, patching build errors, rootfs build
  scripts, module/firmware wiring, Xorg/LXDE/init config, log analysis.
- **You (device loop):** flashing, serial-console capture, per-subsystem testing, pasting logs,
  obtaining stock firmware for recovery. The test-on-device loop is the real bottleneck.

## Definition of done (realistic)
Tablet boots a Raspberry-Pi-OS-styled Devuan + LXDE desktop from the pmOS 3.10 kernel, with
working display + touch + WiFi; sluggish but usable. Some peripherals (BT/audio/sensors) may
stay TODO.

## Risk register
- Kernel won't build even from a1ceca353 -> match pmbootstrap/SDK version exactly.
- Builds but won't boot -> need serial console; may be undebuggable without HW docs.
- A peripheral never works on 3.10 -> accept and document.
- Bricking -> download mode + stock firmware is the safety net (Phase 1, step 1).
