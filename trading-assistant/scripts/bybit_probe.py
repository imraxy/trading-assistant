#!/usr/bin/env python3
"""
Bybit v5 Sign-Type 2 auth probe (standalone)

Usage (mainnet example):
  BYBIT_API_KEY=... BYBIT_API_SECRET=... BYBIT_BASE_URL=https://api.bybit.com python3 trading-assistant/scripts/bybit_probe.py

Usage (testnet example):
  BYBIT_API_KEY=... BYBIT_API_SECRET=... BYBIT_BASE_URL=https://api-testnet.bybit.com python3 trading-assistant/scripts/bybit_probe.py

This script reproduces the app's signing path for GET /v5/user/query-api:
  signature = HMAC_SHA256(secret, timestamp + api_key + recv_window + params_string)

It prints sanitized diagnostics and the HTTP response so you can validate 200 vs 401 outside the web app.
"""

import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
import json
import sys
import ssl
import urllib.request

def getenv(name: str, default=None):
    v = os.getenv(name)
    return v if v is not None else default

def http_get(url: str, headers: dict) -> (int, str):
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return code, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return e.code, body
    except Exception as e:
        return -1, str(e)

def main():
    api_key = getenv("BYBIT_API_KEY", "")
    api_secret = getenv("BYBIT_API_SECRET", "")
    base_url = getenv("BYBIT_BASE_URL", "")
    recv_window = int(getenv("BYBIT_RECV_WINDOW", "20000") or 20000)

    if not api_key or not api_secret:
        print("Error: BYBIT_API_KEY or BYBIT_API_SECRET is missing in process environment", file=sys.stderr)
        sys.exit(2)
    if not base_url:
        # Resolve from flags if not provided
        use_testnet = str(getenv("BYBIT_USE_TESTNET", "") or getenv("BYBIT_TESTNET", "")).lower() in ("1","true","yes","on")
        base_url = "https://api-testnet.bybit.com" if use_testnet else "https://api.bybit.com"

    # Probe endpoint (auth-required)
    path = "/v5/user/query-api"
    params_items = []  # no params for this GET
    qs = urlencode(params_items)  # empty
    timestamp = str(int(time.time() * 1000))
    presign = f"{timestamp}{api_key}{recv_window}{qs}"

    sign = hmac.new(api_secret.encode("utf-8"), presign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": sign,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": str(recv_window),
        "Content-Type": "application/json",
    }

    url = f"{base_url}{path}"
    if qs:
        url = f"{url}?{qs}"

    # Diagnostics (sanitized)
    diag = {
        "host": base_url,
        "path": path,
        "sign_type": 2,
        "recv_window": recv_window,
        "timestamp_ms": timestamp,
        "api_key_prefix": (api_key[:4] + "..."),
        "params_keys": [k for k,_ in params_items],
        "presign_sha256": hashlib.sha256(presign.encode("utf-8")).hexdigest(),
    }
    print("Probe diagnostics:", json.dumps(diag, indent=2))

    code, body = http_get(url, headers)
    print(f"HTTP {code}")
    try:
        j = json.loads(body)
        print(json.dumps(j, indent=2))
    except Exception:
        print(body[:800])

    # Exit code hint
    if code == 200:
        sys.exit(0)
    sys.exit(1)

if __name__ == "__main__":
    main()