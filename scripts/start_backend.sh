#!/usr/bin/env bash
set -euo pipefail

# Start FastAPI backend on port 8000, bound to all interfaces for Windows access
ROOT_DIR="/mnt/i/Sachin/cryptoAnalysis"
BACKEND_DIR="$ROOT_DIR/trading-assistant/backend"

echo "[backend] Stopping anything on :8000 ..."
fuser -k 8000/tcp 2>/dev/null || true

echo "[backend] Starting uvicorn ..."
cd "$BACKEND_DIR"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > logs/server.out 2>&1 &
sleep 2

echo "[backend] Listening sockets:"
ss -lntp | grep 8000 || true

echo "[backend] Health:"
curl -sf http://127.0.0.1:8000/health || true
echo
echo "[backend] Logs: $BACKEND_DIR/logs/server.out"


