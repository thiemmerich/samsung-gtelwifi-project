# Samsung Galaxy Tab E 2015 (gtelwifi)

🇧🇷 Português (Brasil) · [🇺🇸 English](README.md)

Uma missão de hobby para trazer um desktop Linux mais moderno a um **Samsung Galaxy
Tab E 9.6 (SM-T560, `gtelwifi`, Spreadtrum SC7730)** de 2015, **colando o kernel
downstream do postmarketOS** (que já faz a tela e o Wi-Fi funcionarem, fruto de
engenharia reversa) a um **userspace Devuan com desktop LXDE**.

> Isto **não** é um "port do Raspberry Pi OS" — isso é impossível (o kernel é
> específico da Broadcom). Em vez disso: mantemos o kernel 3.10 do pmOS que já
> controla este hardware e colocamos por cima um userspace da família Debian
> (Devuan, sem systemd).

Veja **[quest/ROADMAP.md](quest/ROADMAP.md)** para o plano completo, as decisões e o
checklist de fases (o roadmap está em inglês).

## Estrutura do repositório

```
samsung-gtelwifi-project/
├── quest/        # nosso roadmap, notas, planilha de capacidades, logs
├── patches/      # nossos diffs para os pacotes de kernel/device do gtelwifi
├── scripts/      # scripts de setup / build / flash
└── pmaports/     # clone do pmOS — ENTRADA DE BUILD, no gitignore (recriável)
```

A árvore `pmaports/` é do postmarketOS (upstream) e **não** é versionada aqui — ela é
reproduzível. Recrie-a com:

```sh
./scripts/setup-pmaports.sh
```

Esse script clona o pmaports e faz checkout do nosso commit conhecido-bom
`a1ceca353` (anterior ao arquivamento, onde o `gtelwifi` ainda vive em
`device/downstream/`) numa branch `quest-gtelwifi`.

## Por que isto é possível

O port do pmOS foi **arquivado em 22/06/2026** por uma limpeza automática de pacotes
"sem mantenedor" — motivo **administrativo**, não porque quebrou. Ele estava ativo há
cerca de um mês. Então partimos de uma base recente e provavelmente ainda compilável.

## Decisões travadas

- **Kernel:** fork downstream 3.10.17 do pmOS — **permanente** (portar os drivers
  Spreadtrum para o mainline é inviável e está fora de escopo).
- **Userspace:** Devuan (Debian sem systemd → compatível com o kernel antigo, roda `.deb`).
- **Desktop:** LXDE (o mais leve, sem compositor — cabe na restrição de "sem GPU").
- **Veículo de bring-up:** Alpine via pmOS, só para provar que o kernel dá boot no aparelho.

## Status

Fase 0 (build no host, risco zero para o aparelho). Veja o checklist no roadmap.
