#!/usr/bin/env bash
set -euo pipefail

# Start FastAPI backend on port 8000 (all interfaces for Windows access via WSL)
ROOT_DIR="/mnt/i/Sachin/cryptoAnalysis"
BACKEND_DIR="$ROOT_DIR/trading-assistant/backend"

echo "[backend] Ensuring logs dir exists ..."
mkdir -p "$BACKEND_DIR/logs"

echo "[backend] Stopping anything on :8000 ..."
fuser -k 8000/tcp 2>/dev/null || true

cd "$BACKEND_DIR"

echo "[backend] Ensuring Python venv ..."
if [ ! -d venv ]; then
  python3 -m venv venv || true
fi

# Bootstrap pip inside venv if missing
if ! "$BACKEND_DIR/venv/bin/python" -c "import pip" >/dev/null 2>&1; then
  echo "[backend] Bootstrapping pip into venv ..."
  if ! "$BACKEND_DIR/venv/bin/python" -m ensurepip --upgrade >/dev/null 2>&1; then
    echo "[backend] ensurepip not available; using get-pip.py ..."
    TMP_DIR=$(mktemp -d)
    curl -sS https://bootstrap.pypa.io/get-pip.py -o "$TMP_DIR/get-pip.py"
    "$BACKEND_DIR/venv/bin/python" "$TMP_DIR/get-pip.py" >/dev/null 2>&1 || true
    rm -rf "$TMP_DIR"
  fi
fi

echo "[backend] Ensuring dependencies ..."
"$BACKEND_DIR/venv/bin/python" -m pip install --upgrade pip wheel >/dev/null 2>&1 || true
"$BACKEND_DIR/venv/bin/pip" install -r requirements.txt >/dev/null 2>&1 || true

echo "[backend] Starting uvicorn ..."
nohup "$BACKEND_DIR/venv/bin/python" -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --reload > "$BACKEND_DIR/logs/server.out" 2>&1 &

echo "[backend] Waiting for health check (up to 20s) ..."
for i in {1..20}; do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "[backend] ✅ Healthy"
    break
  fi
  sleep 1
done

echo "[backend] Listening sockets:"
ss -lntp | grep 8000 || true

echo "[backend] URL: http://localhost:8000/"
echo "[backend] Logs: $BACKEND_DIR/logs/server.out"


