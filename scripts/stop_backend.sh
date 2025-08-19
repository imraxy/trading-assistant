#!/usr/bin/env bash
set -euo pipefail

echo "[backend] Stopping uvicorn on :8000 ..."
fuser -k 8000/tcp 2>/dev/null || true
echo "[backend] Done."


