#!/usr/bin/env bash
set -euo pipefail

# Start BrowserTools MCP in WSL pointing to Windows Chrome DevTools

PORT_DEVTOOLS=${1:-9224}
PORT_MCP=${2:-3025}

# Discover a reachable Windows host IP (nameserver or default gateway)
NAMESERVER_IP=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf || true)
GATEWAY_IP=$(ip route 2>/dev/null | awk '/default via/ {print $3; exit}' || true)

echo "[mcp] Candidate Windows hosts: nameserver=$NAMESERVER_IP gateway=$GATEWAY_IP"

WINDOWS_HOST=${WINDOWS_HOST:-}
if [ -n "${3:-}" ]; then WINDOWS_HOST="$3"; fi

if [ -z "$WINDOWS_HOST" ]; then
  for host in "$NAMESERVER_IP" "$GATEWAY_IP"; do
  if [ -n "${host}" ]; then
    if curl -sf "http://${host}:${PORT_DEVTOOLS}/json/version" >/dev/null 2>&1; then
      WINDOWS_HOST="$host"
      break
    fi
  fi
  done
fi

if [ -z "$WINDOWS_HOST" ]; then
  echo "[mcp] DevTools not reachable on candidates. Ensure Chrome was started with scripts/start_windows_chrome.ps1 and firewall allows TCP ${PORT_DEVTOOLS}." >&2
  exit 1
fi

echo "[mcp] Using Windows host: $WINDOWS_HOST (DevTools ${PORT_DEVTOOLS})"

echo "[mcp] Using Node via nvm (20) ..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 20 >/dev/null

export BROWSERTOOLS_DEVTOOLS_HOST=$WINDOWS_HOST
export BROWSERTOOLS_DEVTOOLS_PORT=$PORT_DEVTOOLS
export BROWSERTOOLS_MCP_HOST=0.0.0.0
export BROWSERTOOLS_MCP_PORT=$PORT_MCP
export BROWSERTOOLS_DISABLE_DISCOVERY=1

echo "[mcp] Starting MCP on 0.0.0.0:$PORT_MCP ..."
npx -y @agentdeskai/browser-tools-mcp@latest


