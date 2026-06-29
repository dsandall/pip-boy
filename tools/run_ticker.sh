#!/usr/bin/env bash
# Launch the SPCX uplink under the uv-managed environment, kept alive across
# restarts. If the ticker exits (serial lost, device replug, permission not yet
# granted), wait and retry -- so the moment port access is in place it connects.
#
# Usage:  bash tools/run_ticker.sh [extra pip_ticker.py args...]
#   e.g.  bash tools/run_ticker.sh --inject --period 15
set -u
cd "$(dirname "$0")/.."

while true; do
  uv run python tools/pip_ticker.py "$@"
  rc=$?
  echo "[run_ticker] pip_ticker.py exited (rc=$rc) -- retrying in 5s."
  echo "[run_ticker] if this is a serial PermissionError, grant port access:"
  echo "[run_ticker]   sudo setfacl -m u:$USER:rw /dev/ttyACM0      # one-shot, until replug"
  echo "[run_ticker]   sudo usermod -aG uucp $USER && relog         # permanent"
  sleep 5
done
