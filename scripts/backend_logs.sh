#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/mnt/i/Sachin/cryptoAnalysis/trading-assistant/backend/logs/server.out"
if [ ! -f "$LOG_FILE" ]; then
  echo "[logs] Log file not found: $LOG_FILE" >&2
  exit 1
fi

echo "[logs] Tailing $LOG_FILE (Ctrl-C to stop)"
tail -n 200 -F "$LOG_FILE"


