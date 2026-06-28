# Pip-Boy 3000 Mk V — Hardware Mod Surface

Authoritative pin data from `boards/PIPBOY.py` (Espruino upstream). MCU: **STM32F407VE**,
LQFP100, 168 MHz, 192 KB RAM, 512 KB flash. The only realistically solderable expansion
is the **test-pad cluster near the microSD slot** (identified in RobCo Industries teardown
log entry012–013). Everything else is fine-pitch IC pins.

## The expansion pads (near microSD)
| Pad | STM32 pin | Espruino name | Notes |
|-----|-----------|---------------|-------|
| UART TX | **PB10** | `Serial3` TX | Default **console/REPL @ 115200** — repurpose for a peripheral |
| UART RX | **PB11** | `Serial3` RX | |
| SWDIO | **PA13** | `JTAG.pin_MS` | SWD debug (flash/debug custom `pipboy.bin` via ST-Link) |
| SWCLK | **PA14** | `JTAG.pin_CK` | SWD clock |
| 5V | — | — | USB rail — **only present when USB-C plugged in** |
| GND | — | — | |

> `Serial3` (USART3, PB10/PB11) **is** the UART test pad and **is** the default Espruino
> console at 115200. To use it for a peripheral you must first free it (see USER_BOOT below).

## The two mod paths
1. **UART peripheral (no custom firmware)** — RobCo's proven route. Solder a UART device to
   Serial3 + power, disable the Serial3 REPL via a `USER_BOOT/*.js` boot script, then
   `Serial3.setup(baud)` and drive it in JS. Examples done by the community:
   - **GPS**: Adafruit PA1010D → `Serial3.setup(9600)` + Espruino `GPS` module (NMEA).
   - **WiFi**: Adafruit HUZZAH ESP8266 (AT firmware) in the battery compartment, 5V pad.
2. **SWD + custom native firmware** — ST-Link to PA13/PA14, flash a self-built `pipboy.bin`
   (our `~/pipboy/firmware` build). Needed only if a mod requires new native drivers
   (extra UART/I2C/SPI/ADC peripheral compiled in). RDP appears off (DFU stays enabled).

## USER_BOOT hook (free the console for a peripheral)
Files in `/USER_BOOT/` on the SD run at startup in alphanumeric order. To take Serial3 away
from the REPL (RobCo `10_repl.js` pattern):
```js
// USER_BOOT/10_repl.js  — move REPL off Serial3 so a peripheral can use the pads
E.setConsole("USB");           // keep interactive console on USB
Serial3.setup(9600);           // now free for e.g. GPS
```

## What is NOT free (already in use)
- **Port D / Port E**: almost entirely the FSMC parallel LCD (D0–D15, RS, RD, WR, CS, BL=PB15).
- **Port C**: SDIO microSD (PC8–PC12), `PD3` = SD power **also gates the ES8388 audio codec power**.
- **Port A**: buttons/encoders (PA0–PA3, PA8, PA10), USB (PA9/11/12), battery sense (PA6),
  mode selector resistor ladder (PA7), SWD (PA13/14).
- **Port B**: SPI-flash (PB3/4/5/14), clock encoder (PB0/1), LCD backlight (PB15),
  Serial3 (PB10/11).
- I2C bus carries the **ES8388 codec + FM radio** — sharable for an I2C sensor only if you
  can tap the bus pads (not broken out to the test-pad cluster).

## Power notes
- 5V pad is **USB-only**. For battery-powered mods you need 3.3V (RobCo added a JST breakout).
- ESP8266 draws ~300 mA peak — a real load on the small LiPo; budget accordingly.

## Reference
- RobCo teardown/UART discovery: log.robco-industries.org/log/entry012–013, GPS entry017, WiFi entry018
- `Pip` API + SD layout: log.robco-industries.org/documentation/pipboy-3000/
