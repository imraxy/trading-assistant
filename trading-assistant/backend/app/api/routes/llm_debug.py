"""
LLM Debug API routes

Expose minimal diagnostics for aggregator/providers (Groq, OpenRouter, NVIDIA NIM)
without leaking secrets. Useful to confirm base URL, headers (masked), request schema,
and raw response snippets.

Endpoints:
- GET /api/v1/llm/debug?provider=groq|openrouter|nim[&model=...]
- GET /api/v1/llm/debug/env
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Optional, Dict, Any

from ...services.llm_debug import probe_provider
import os

router = APIRouter()


def _mask(v: Optional[str]) -> str:
    if not v:
        return "unset"
    return (v[:4] + "...") if len(v) >= 4 else "***"


@router.get("/llm/debug")
async def llm_debug(
    provider: str = Query(..., description="groq|openrouter|nim"),
    model: Optional[str] = Query(None, description="Optional model id for provider (used for NIM chat probe)"),
) -> Dict[str, Any]:
    """
    Perform a minimal probe for the given provider and return sanitized diagnostics + raw response snippet.
    """
    out = await probe_provider(provider, model=model)
    return out


@router.get("/llm/debug/env")
async def llm_debug_env() -> Dict[str, Any]:
    """
    Show effective env bindings for LLM aggregators (masked).
    Does not perform network calls.
    """
    data = {
        "groq": {
            "GROQ_API_KEY": _mask(os.getenv("GROQ_API_KEY")),
            "GROQ_BASE_URL": os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1",
        },
        "openrouter": {
            "OPENROUTER_API_KEY": _mask(os.getenv("OPENROUTER_API_KEY")),
            "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
            "OPENROUTER_REFERER": os.getenv("OPENROUTER_REFERER") or "https://localhost",
            "OPENROUTER_TITLE": os.getenv("OPENROUTER_TITLE") or "trading-assistant",
        },
        "nim": {
            "NIM_API_KEY": _mask(os.getenv("NIM_API_KEY")),
            "NIM_TOKEN": _mask(os.getenv("NIM_TOKEN")),
            "NIM_BASE_URL": os.getenv("NIM_BASE_URL") or "https://integrate.api.nvidia.com",
            "resolved_base_for_chat": (os.getenv("NIM_BASE_URL") or "https://integrate.api.nvidia.com").rstrip("/") + "/v1",
        },
        "router": {
            "AGGREGATORS_ENABLED": os.getenv("AGGREGATORS_ENABLED"),
            "AGGREGATOR_OPTOUT_OPENROUTER": os.getenv("AGGREGATOR_OPTOUT_OPENROUTER"),
            "AGGREGATOR_OPTOUT_CHUTES": os.getenv("AGGREGATOR_OPTOUT_CHUTES"),
            "AGGREGATOR_OPTOUT_NIM": os.getenv("AGGREGATOR_OPTOUT_NIM"),
            "CATALOG_REFRESH_INTERVAL_HOURS": os.getenv("CATALOG_REFRESH_INTERVAL_HOURS"),
        }
    }
    return {"status": "success", "data": data}