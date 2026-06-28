#!/usr/bin/env bash
# Wait for clone, checkout the device's exact commit, build PIPBOY firmware,
# and compare against the ground-truth dump pulled off the device.
set -uo pipefail
ESP=/home/thebu/newhome/projects/pip-boy/firmware/espruino
GROUND=/home/thebu/newhome/projects/pip-boy/dump/SD_pipboy.bin
COMMIT=ec7ff98c3

echo "[*] waiting for clone to finish..."
for i in $(seq 1 120); do
  pgrep -f "clone https://github.com/espruino" >/dev/null || break
  sleep 5
done
cd "$ESP" || { echo "no espruino dir"; exit 1; }
echo "[*] clone done, size $(du -sh . | cut -f1)"

echo "[*] checkout $COMMIT (device = 2v25.359)"
git checkout -q "$COMMIT" 2>&1 | tail -3
git log -1 --format='HEAD %h %cd %s'
git submodule update --init --recursive 2>&1 | tail -3

echo "[*] building: RELEASE=1 BOARD=PIPBOY make"
export RELEASE=1 BOARD=PIPBOY
time make 2>&1 | tee /home/thebu/newhome/projects/pip-boy/firmware/build.log | tail -40
echo "[*] build exit: ${PIPESTATUS[0]}"

echo "[*] artifacts:"
ls -la "$ESP"/bin/*pipboy*.bin 2>/dev/null || ls -la "$ESP"/*.bin 2>/dev/null
BUILT=$(ls -1 "$ESP"/bin/*pipboy*.bin 2>/dev/null | head -1)
if [ -n "$BUILT" ]; then
  echo "[*] compare built vs ground-truth device firmware:"
  ls -l "$BUILT" "$GROUND"
  sha256sum "$BUILT" "$GROUND"
  cmp "$BUILT" "$GROUND" && echo "BYTE-IDENTICAL" || echo "(differs - expected unless toolchain matches exactly)"
fi
echo "[*] done"
