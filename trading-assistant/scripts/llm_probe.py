#!/usr/bin/env python3
"""
LLM aggregator probe (standalone)

Probes Groq, OpenRouter, or NVIDIA NIM using the same base URL + header conventions as the backend.

Usage examples:
  # Groq (lists models)
  GROQ_API_KEY=... python3 trading-assistant/scripts/llm_probe.py --provider groq

  # OpenRouter (lists models)
  OPENROUTER_API_KEY=... python3 trading-assistant/scripts/llm_probe.py --provider openrouter

  # NIM (minimal chat completion ping)
  NIM_API_KEY=... python3 trading-assistant/scripts/llm_probe.py --provider nim --model meta/llama-3.1-8b-instruct

Env variables respected:
  GROQ_API_KEY, GROQ_BASE_URL
  OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_REFERER, OPENROUTER_TITLE
  NIM_API_KEY, NIM_TOKEN, NIM_BASE_URL   (probe will call <base>/v1/chat/completions)

Outputs sanitized diagnostics (base_url, headers minus secrets, HTTP status, body snippet).
"""

import os
import sys
import json
import ssl
import argparse
from urllib.parse import urlencode
import urllib.request
import urllib.error

def getenv(name, default=None):
    v = os.getenv(name)
    return v if v is not None else default

def mask(v: str) -> str:
    if not v:
        return "unset"
    return (v[:4] + "...") if len(v) >= 4 else "***"

def http_get(url: str, headers: dict):
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return e.code, body
    except Exception as e:
        return -1, str(e)

def http_post(url: str, headers: dict, body: dict):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, headers=headers, data=data, method="POST")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return e.code, body
    except Exception as e:
        return -1, str(e)

def resolve_groq():
    base = getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    key = getenv("GROQ_API_KEY", "")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    headers["Content-Type"] = "application/json"
    return base, headers

def resolve_openrouter():
    base = getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    key = getenv("OPENROUTER_API_KEY", "")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    headers["HTTP-Referer"] = getenv("OPENROUTER_REFERER", "https://localhost")
    headers["X-Title"] = getenv("OPENROUTER_TITLE", "trading-assistant")
    headers["Content-Type"] = "application/json"
    return base, headers

def resolve_nim():
    base = getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com")
    if not base.rstrip("/").endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    key = getenv("NIM_API_KEY", "") or getenv("NIM_TOKEN", "")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    headers["Content-Type"] = "application/json"
    return base, headers

def snippet(s: str, limit: int = 800) -> str:
    try:
        return s[:limit]
    except Exception:
        return str(s)[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=["groq", "openrouter", "nim"])
    ap.add_argument("--model", required=False, default=None)
    args = ap.parse_args()

    prov = args.provider.lower()
    if prov == "groq":
        base, headers = resolve_groq()
        url = base.rstrip("/") + "/models"
        hdr_preview = {k: ("set" if (k.lower()=="authorization" and v) else v) for k, v in headers.items()}
        if "Authorization" in hdr_preview:
            hdr_preview["Authorization"] = "set" if headers.get("Authorization") else "unset"
        print(json.dumps({"provider":"groq","request":{"method":"GET","url":url,"base_url":base,"headers":hdr_preview}}, indent=2))
        code, body = http_get(url, headers)
        print(f"HTTP {code}")
        try:
            j = json.loads(body)
            print(json.dumps(j, indent=2)[:1200])
        except Exception:
            print(snippet(body))
        sys.exit(0 if code == 200 else 1)

    if prov == "openrouter":
        base, headers = resolve_openrouter()
        url = base.rstrip("/") + "/models"
        hdr_preview = {k: ("set" if (k.lower()=="authorization" and v) else v) for k, v in headers.items()}
        if "Authorization" in hdr_preview:
            hdr_preview["Authorization"] = "set" if headers.get("Authorization") else "unset"
        print(json.dumps({"provider":"openrouter","request":{"method":"GET","url":url,"base_url":base,"headers":hdr_preview}}, indent=2))
        code, body = http_get(url, headers)
        print(f"HTTP {code}")
        try:
            j = json.loads(body)
            print(json.dumps(j, indent=2)[:1200])
        except Exception:
            print(snippet(body))
        sys.exit(0 if code == 200 else 1)

    # NIM
    base, headers = resolve_nim()
    url = base.rstrip("/") + "/chat/completions"
    use_model = args.model or "meta/llama-3.1-8b-instruct"
    payload = {
        "model": use_model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    hdr_preview = {k: ("set" if (k.lower()=="authorization" and v) else v) for k, v in headers.items()}
    if "Authorization" in hdr_preview:
        hdr_preview["Authorization"] = "set" if headers.get("Authorization") else "unset"
    print(json.dumps({"provider":"nim","request":{"method":"POST","url":url,"base_url":base,"headers":hdr_preview,"payload_keys":list(payload.keys())}}, indent=2))
    code, body = http_post(url, headers, payload)
    print(f"HTTP {code}")
    try:
        j = json.loads(body)
        print(json.dumps(j, indent=2)[:1200])
    except Exception:
        print(snippet(body))
    # Treat 200-299 as success, 400/429 as useful but non-fatal (exit 0 to aid CI debugging)
    sys.exit(0 if (200 <= code < 300 or code in (400, 404, 422, 429)) else 1)

if __name__ == "__main__":
    main()