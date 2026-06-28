# Pip-Boy 3000 Mk V — hacking / hardware-mod project

Reverse-engineering, dumping, rebuilding, and (goal) hardware-modding **The Wand Company
Pip-Boy 3000 Mk V** — the licensed die-cast *Fallout* replica.

## TL;DR
It's an **officially open Espruino platform**, not a locked target. An STM32F407 running
the Espruino JavaScript interpreter; the entire Pip-Boy UI/behavior is JavaScript on a
swappable SD card. The USB port is a live JS REPL. Firmware is downloadable and rebuildable.

## Device facts (verified on-unit)
| | |
|---|---|
| Product | The Wand Company Pip-Boy 3000 Mk V (USB `0483:a4f1`) |
| MCU | **STM32F407VE** — Cortex-M4, 168 MHz, 512 KB flash, 192 KB RAM, +256 KB SPI flash |
| Firmware | **Espruino 2v25.359**, private Wand Co commit `ec7ff98c3` (not in public repo) |
| App | **Pip-OS v1.29** |
| Connection | CDC-ACM serial `/dev/ttyACM1` = live Espruino JS REPL |
| Display | 480×320 16bpp TFT over FSMC | 
| Audio | ES8388 codec + speaker, FM radio (I²C) |
| Bluetooth | **None** — F407 has no radio; the "companion app" is Web Serial over USB |

## Architecture — two layers
1. **`pipboy.bin`** (native, 384 KB) — stock Espruino + STM32F4 drivers + ~24 custom native
   C primitives (`libs/pipboy/jswrap_pipboy.c`: `audioStart`, `blitImage`, `videoStart`,
   `setPalette`, DAC/codec). **Fully open source.** Built from the Espruino repo.
2. **`FW.JS`** (== `.bootcde`, 87 KB tokenised JS) — ALL Pip-Boy behavior (menus, stats,
   inventory, radio, apps). Proprietary to TWC, ships on the SD card, **loaded at boot** —
   *not* embedded in `pipboy.bin`. The `Pip` global object is the seam between the two.

The community CFW tooling (AidansLab/Pip-Boy-CFW-Builder) patches the **`FW.JS`** layer
(untokenise → JS patch → retokenise). Our firmware build covers the **`pipboy.bin`** layer.

## Repo layout
```
dump/      Full device extraction (read-only, over the REPL)
           .bootcde / SD_FW.JS (identical), SD_pipboy.bin (+crc), SD_manifest.txt,
           SD_settings.json, SD_USER_*.js, Pip_members_full.tsv (native-vs-JS map)
firmware/  build_v2.sh (functional rebuild), built_espruino_2v25_pipboy.bin
           espruino/   (gitignored — full upstream clone)
           toolchain/  (gitignored — pinned ARM GCC 13.2)
docs/      hardware-mods.md — expansion pad / pin map
tools/     pip_dump.py, pip_fetch_sd.py, pip_pull_fw.py, pip_classify.py
           (read-only REPL extraction; STX/ETX-sentinel + btoa chunking)
apps/      (future) our own SD-card JS apps
```

## How the dump works (read-only, no flash/reset)
Talk to the live Espruino REPL on `/dev/ttyACM1`. Critical gotcha: the bare `=` inspector
**abbreviates** long output (`"head"…"tail"`) and silently corrupts dumps. Wrap results in
`print(String.fromCharCode(2)+expr+String.fromCharCode(3))` (STX/ETX sentinels) and pull
binary via on-device `btoa()` in chunks. See `tools/`.

## How to build firmware (functional rebuild)
Exact byte reproduction is impossible (device = a *private* commit). We build the closest
public release — same native layer + board, runs the unaltered `FW.JS`:
```sh
cd firmware && ./build_v2.sh      # fetches pinned ARM GCC 13.2, checks out RELEASE_2V25,
                                  # builds bin/espruino_2v25_pipboy.bin, diffs vs device
```
> System `arm-none-eabi-gcc` 16 will NOT work (C23/int-conversion errors). The script pulls
> the **pinned GCC 13.2** Espruino expects.

Flash (if/when desired): `dfu-util -a 0 -s 0x08000000:leave -D pipboy.bin` after entering
DFU (hold Flashlight + Power ~15 s). Don't flash custom firmware without a recovery plan.

## Goal: hardware mods
Expansion surface = test pads near the microSD (full map in `docs/hardware-mods.md`):
- **Serial3 = USART3 PB10(TX)/PB11(RX)** — the 115200 REPL console; free it with a
  `/USER_BOOT/*.js` boot script, then attach a UART peripheral (GPS, ESP8266 WiFi…).
- **SWD = PA13/PA14** — flash/debug a custom `pipboy.bin` with an ST-Link.
- 5V (USB-only) / GND.

Two routes: (a) **UART peripheral, no custom firmware** (RobCo's proven path — JS + USER_BOOT);
(b) **custom native firmware** via SWD when a mod needs a new compiled-in peripheral.

## Ecosystem references
- pip-boy.com — community hub (apps, sims, converters, forum, Discord)
- log.robco-industries.org — teardown + dev docs + GPS/WiFi hardware mods
- github.com/thewandcompany/pip-boy — official mod tool (Web Serial app loader)
- github.com/CodyTolene/pip-boy-3000-mk-v-apps — large app/game collection
- github.com/AidansLab/Pip-Boy-CFW-Builder — FW.JS untokeniser/patcher
- github.com/beaverboy-12/...Community-Guide — teardown/SD/troubleshooting

## Status
✅ identified · ✅ dumped · ✅ ecosystem mapped · ✅ functional firmware build working
▶ next: pick the hardware-mod peripheral and spec it end-to-end.
