# samsung-gtelwifi-project

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

Phase 0 (host-side build, zero device risk). See the roadmap checklist.
