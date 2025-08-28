"""
LLM Aggregator debug utilities.

Resolves provider base URL, builds sanitized auth headers, and performs a minimal probe
request to validate connectivity and auth. Designed for diagnostics only.

Env precedence: process env > backend/.env > backend/app/.env (via app.main dotenv).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import json
import httpx

from .llm_provider import _request_with_retries  # reuse robust HTTP (if needed)


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


def _snip(s: Optional[str]) -> str:
    if not s:
        return "unset"
    return (s[:4] + "...") if len(s) >= 4 else "***"


def _body_snippet(text: str, limit: int = 600) -> str:
    try:
        return text[:limit]
    except Exception:
        return ""


def _json_snippet(obj: Any, limit: int = 600) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)[:limit]
    except Exception:
        return str(obj)[:limit]


def resolve_groq() -> Tuple[str, Dict[str, str]]:
    """
    Groq (OpenAI-compatible):
      - Base URL: https://api.groq.com/openai/v1
      - Header: Authorization: Bearer <GROQ_API_KEY>
    """
    base = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
    key = os.getenv("GROQ_API_KEY") or ""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return base, headers


def resolve_openrouter() -> Tuple[str, Dict[str, str]]:
    """
    OpenRouter:
      - Base URL: https://openrouter.ai/api/v1
      - Header: Authorization: Bearer <OPENROUTER_API_KEY>
      - Recommended: HTTP-Referer and X-Title
    """
    base = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    key = os.getenv("OPENROUTER_API_KEY") or ""
    headers: Dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    headers["HTTP-Referer"] = os.getenv("OPENROUTER_REFERER") or "https://localhost"
    headers["X-Title"] = os.getenv("OPENROUTER_TITLE") or "trading-assistant"
    return base, headers


def resolve_nim() -> Tuple[str, Dict[str, str]]:
    """
    NVIDIA NIM:
      - Base URL: https://integrate.api.nvidia.com/v1
      - Header: Authorization: Bearer <NIM_API_KEY or NIM_TOKEN>
    """
    base = os.getenv("NIM_BASE_URL") or "https://integrate.api.nvidia.com"
    # Ensure we add the /v1 suffix for OpenAI chat
    if not base.rstrip("/").endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    key = os.getenv("NIM_API_KEY") or os.getenv("NIM_TOKEN") or ""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return base, headers


async def probe_provider(provider: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Probe the given provider with a minimal, low-cost request and return sanitized diagnostics.

    provider: groq | openrouter | nim
    model (optional): used for nim chat probe
    """
    prov = (provider or "").strip().lower()
    if prov not in ("groq", "openrouter", "nim"):
        return {"status": "error", "error": f"unsupported_provider:{provider}"}

    # Resolve base URL and headers
    if prov == "groq":
        base, headers = resolve_groq()
        url = base.rstrip("/") + "/models"
        method = "GET"
        payload = None
    elif prov == "openrouter":
        base, headers = resolve_openrouter()
        url = base.rstrip("/") + "/models"
        method = "GET"
        payload = None
    else:  # nim
        base, headers = resolve_nim()
        url = base.rstrip("/") + "/chat/completions"
        method = "POST"
        use_model = model or "meta/llama-3.1-8b-instruct"
        payload = {
            "model": use_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }

    # Build sanitized header preview
    hdr_preview = {k: ("set" if (k.lower() == "authorization" and v) else v) for k, v in (headers or {}).items()}
    if "Authorization" in hdr_preview:
        hdr_preview["Authorization"] = "set" if headers.get("Authorization") else "unset"

    # Execute
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            else:
                resp = await client.post(url, headers=headers, json=payload)

        status = resp.status_code
        text = resp.text or ""
        # Consider 200-299 as success; 400/429 indicate schema/quota but prove auth+reachability
        ok = 200 <= status < 300
        # Useful outcome: 401/403 -> auth, 404 -> route mismatch, 429 -> quota/rate-limit
        outcome = "success" if ok else ("quota_or_schema" if status in (400, 404, 422, 429) else "auth_or_network" if status in (401, 403) else "other_error")

        return {
            "status": "success",
            "data": {
                "provider": prov,
                "request": {
                    "method": method,
                    "url": url,
                    "base_url": base,
                    "headers": hdr_preview,
                    "payload_keys": list((payload or {}).keys()),
                },
                "response": {
                    "status_code": status,
                    "body_snippet": _body_snippet(text, 800),
                    "outcome": outcome,
                },
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "data": {
                "provider": prov,
                "request": {"method": method, "url": url, "base_url": base, "headers": hdr_preview},
            },
        }