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

## Status

**Phase 0 complete (2026-07-24)** — the archived June-2026 port builds and produces a
bootable image (`samsung-gtelwifi.img`) on current tooling. Next: **Phase 1** — flash to
the device, recovery-first. See [quest/ROADMAP.md](quest/ROADMAP.md),
[quest/PHASE0.md](quest/PHASE0.md), [quest/PHASE1.md](quest/PHASE1.md).

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
