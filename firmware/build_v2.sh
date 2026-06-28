#!/usr/bin/env bash
# Functional rebuild: pinned ARM GCC 13.2 + RELEASE_2V25 tag (device's exact
# commit ec7ff98c3 / 2v25.359 is a PRIVATE Wand Co build, not in the public repo).
set -uo pipefail
FW=/home/thebu/pipboy/firmware
ESP=$FW/espruino
TC=$FW/toolchain
GROUND=/home/thebu/pipboy/dump/SD_pipboy.bin
TCURL="https://github.com/espruino/EspruinoBuildTools/raw/master/arm/arm-gnu-toolchain-13.2.rel1-x86_64-arm-none-eabi-stripped.tar.xz"

# 1. toolchain
if [ ! -x "$TC"/*/bin/arm-none-eabi-gcc ]; then
  echo "[*] downloading pinned ARM GCC 13.2 ..."
  mkdir -p "$TC"; cd "$TC"
  curl -Ls "$TCURL" | tar xJf - --no-same-owner && echo "[*] toolchain extracted"
fi
TCBIN=$(dirname $(ls "$TC"/*/bin/arm-none-eabi-gcc 2>/dev/null | head -1))
export PATH="$TCBIN:$PATH"
echo "[*] using: $(arm-none-eabi-gcc --version | head -1)"

# 2. source at the closest public release
cd "$ESP"
git checkout -q RELEASE_2V25 2>&1 | tail -2
git submodule update --init --recursive 2>&1 | tail -2
echo "[*] source: $(git describe --tags 2>/dev/null) @ $(git rev-parse --short HEAD)"

# 3. build
make clean >/dev/null 2>&1
export RELEASE=1 BOARD=PIPBOY
echo "[*] building (RELEASE=1 BOARD=PIPBOY make) ..."
time make 2>&1 | tee "$FW/build_v2.log" | tail -25
echo "[*] make exit: ${PIPESTATUS[0]}"

# 4. compare
BUILT=$(ls -1 "$ESP"/bin/*pipboy*.bin 2>/dev/null | head -1)
echo "[*] built artifact: ${BUILT:-NONE}"
if [ -n "$BUILT" ]; then
  echo "[*] built $(stat -c%s "$BUILT") B   vs   device $(stat -c%s "$GROUND") B"
  sha256sum "$BUILT" "$GROUND"
  cmp "$BUILT" "$GROUND" >/dev/null 2>&1 && echo "BYTE-IDENTICAL" || echo "differs (expected: private commit + diff toolchain)"
  arm-none-eabi-strings "$BUILT" 2>/dev/null | grep -iE "2v25|pipboy|wand" | head -3
fi
echo "[*] DONE"
