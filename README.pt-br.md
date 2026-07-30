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
├── vendor/       # procedência + checksums dos sources irreplacáveis espelhados
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

## Status — um tablet que já roda a GPU 🎉

O que começou como "será que esse tablet de 2015 dá boot no Linux?" hoje é um **desktop LXQt
funcionando, controlado por toque, com Wi-Fi, e a GPU Mali-400 proprietária renderizando OpenGL
ES 2.0 sobre musl** — além de um caminho já mapeado para um desktop 100% composto pela GPU. Log
técnico completo e receita reproduzível: **[CLAUDE.md](CLAUDE.md)**.

### O que já funciona
- ✅ **Compilado e gravado** — `samsung-gtelwifi.img` gerado com o pmbootstrap e gravado
  (Odin/heimdall); dá boot no **kernel 3.10** (engenharia reversa do pmOS) com tela + Wi-Fi BCM4343.
- ✅ **Desktop LXQt** na tela, controlado pelo **touchscreen**; bateria/energia lidos corretamente.
- ✅ **Wi-Fi** (BCM4343 / `brcmfmac`).
- ✅ **Teclado na tela** — `onboard` (GTK), fixo na base, inicia junto com a sessão.
- ✅ **Fim das telas pretas** — o protetor de tela (que este painel não conseguia acordar) foi
  desativado de vez.
- 🏆 **A GPU Mali-400 renderiza OpenGL ES 2.0** — o hack principal, abaixo.

### 🏆 O hack da GPU (o difícil)
O desktop é renderizado por CPU/software, mas conseguimos fazer o **blob proprietário da GPU
Android Mali-400 (`libGLES_mali.so`, KitKat / DDK r4p1) rodar no postmarketOS/musl** — provavelmente
o primeiro port libhybris da era KitKat para musl. Cada camada resolvida de ponta a ponta:
- Portado o **driver de kernel do Mali** → `/dev/mali0` (`patches/0002-mali-gpu-driver.patch`).
- **Port do libhybris para musl** — o linker bionic embutido carrega os blobs Android; uma tabela de
  hooks redireciona as chamadas de libc/pthread deles para o musl.
- Contornada a **colisão do registrador de thread (TLS) entre bionic e musl** com um stub de pthread
  (single-thread, suficiente para renderizar).
- Corrigido o pipeline de vídeo: **fixação do stride 16bpp RGB565**, **buffer de scanout linear**
  (matou a grade de tiles do Mali) e uma **conversão por software RGBA8888→RGB565** (cores corretas).
- **Resultado:** GLES2 nítido e com cor correta — validado por um cubo 3D girando, iluminado e com
  buffer de profundidade (`gpu-demos/gpu_cube.c`) a **~22–28 fps**, com o driver reportando
  `GL_RENDERER=Mali-400 MP`.

Todos os scripts de patch e a receita passo a passo estão em `hybris/musl-port/` e **[CLAUDE.md](CLAUDE.md)**.

### Em andamento / próximos
- 🔊 **Som** — o codec Spreadtrum existe (ALSA `card0 sprdphone`, `sprd-codec` HiFi/Voice/FM); a rota
  de reprodução DAPM (DAC→alto-falante/fone) ainda não engata o estágio analógico. Um mergulho focado
  no driver do codec está na fila (sem `mixer_paths.xml` do fabricante nem DAPM debugfs — é um
  bring-up do zero).
- 🔵 **Bluetooth** — BT combo do BCM4343 (rfkill liberado); precisa de `hciattach` + firmware `.hcd`.
- 🌈 **O sonho — um desktop 100% composto pela GPU.** Depende de uma **ponte de TLS bionic** de
  verdade (para substituir o stub de pthread single-thread) → depois um compositor Wayland sobre
  libhybris-EGL. O bloqueio está diagnosticado e a implementação planejada em
  **[hybris/musl-port/TLS_BRIDGE_PLAN.md](hybris/musl-port/TLS_BRIDGE_PLAN.md)**; adiado até terminar
  as peças do dia a dia (som, Bluetooth).

> Obs.: o userspace-alvo continua sendo **Devuan + LXDE**; o bring-up atual roda **postmarketOS
> (Alpine/musl) + LXQt**, onde todas as vitórias de hardware acima foram provadas.

Veja também [quest/ROADMAP.md](quest/ROADMAP.md), [quest/PHASE0.md](quest/PHASE0.md),
[quest/PHASE1.md](quest/PHASE1.md).

## Achados da Fase 0 (o que foi preciso para reviver o port)

O port foi arquivado por estar **sem mantenedor, não por estar quebrado**. Revivê-lo a
partir do commit `a1ceca353` foi, na maior parte, corrigir a defasagem entre o pin de
junho e as ferramentas de julho:

- O **pmbootstrap** agora instala via git (todas as versões do PyPI foram removidas). Seu
  `init` interativo (sem TTY sob automação) foi contornado com um
  `~/.config/pmbootstrap_v3.cfg` escrito à mão + work dir.
- Forçado `service_manager = openrc` — **sem systemd** (systemd exige kernel ≥4.x; o nosso é 3.10).
- **O kernel compila limpo no GCC 15.2.0** — o temido "GCC 15 vs kernel de 2015" nunca
  apareceu; os patches gcc7/8/10 existentes bastaram. *(Bloqueador 1 resolvido.)*
- Dois ajustes de uma linha, guardados como patches reproduzíveis (aplicados por `scripts/setup-pmaports.sh`):
  - **`patches/0001`** — o `abuild` atual proíbe vírgulas em nomes de arquivo de source
    (`fix-dtb_qcom,msm-id.patch` → `fix-dtb_qcom-msm-id.patch`).
  - **`patches/0002`** — o `header_version` do `deviceinfo_schema.toml` precisava de
    `datatype = "integer"` junto ao seu `integer_interval` (agora obrigatório).
- O pacote de firmware do WiFi (`firmware-samsung-gtelwifi`, em `device/testing/`) precisa
  ser **compilado separadamente** antes do `pmbootstrap install`.
- **Deriva do edge**: os pacotes base giram rápido (ex.: `postmarketos-base` 65→66-r0). Em
  404: `pmbootstrap update`, e limpe `cache_apk_armv7/APKINDEX*` se persistir.

Resultado: uma imagem gravável `samsung-gtelwifi.img` — UI console, OpenRC, o kernel 3.10 + firmware BCM4343.
