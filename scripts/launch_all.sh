#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/mnt/i/Sachin/cryptoAnalysis"

"$ROOT_DIR/scripts/start_backend.sh"

echo "[launch] Opening dashboard in default browser ..."
xdg-open "http://localhost:8000/" >/dev/null 2>&1 || true

echo "[launch] Done. Use scripts/backend_logs.sh to view logs."


