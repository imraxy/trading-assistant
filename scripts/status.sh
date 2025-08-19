#!/usr/bin/env bash
set -euo pipefail

echo "[status] Listening sockets on :8000"
ss -lntp | grep 8000 || echo "[status] Nothing on 8000"

echo "[status] Health check"
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "[status] ✅ Backend healthy"
else
  echo "[status] ❌ Backend not responding"
fi


