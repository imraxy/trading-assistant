"""
Aggregator base client and shared helpers.

All aggregator clients should:
- Implement list_models() to return a list of normalized dicts suitable for ModelCatalog ingestion.
- Use the shared _request_with_retries from services.llm_provider for robust HTTP behavior.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Reuse robust retries, pacing and timeouts
from ..llm_provider import _request_with_retries  # type: ignore


def _bool_env(name: str, default: bool = False) -> bool:
    v = str(os.getenv(name, str(default))).lower()
    return v in ("1", "true", "yes", "on")


class AggregatorClientBase:
    """Base for aggregator catalog clients."""

    name: str = "base"
    enabled_env: Optional[str] = None  # set to env var name that toggles enablement

    def __init__(self) -> None:
        pass

    def is_enabled(self) -> bool:
        if not self.enabled_env:
            return True
        return _bool_env(self.enabled_env, True)

    async def list_models(self) -> List[Dict[str, Any]]:
        """Return a list of normalized model dicts.

        Each dict SHOULD include:
        - id: model identifier at the aggregator
        - display_name: human friendly
        - family: logical family or base name
        - version: string
        - modalities: list[str] like ["text", "code", "vision", "audio"]
        - context_window: int
        - tool_use: bool
        - json_mode: bool
        - guardrails: Optional[str] or dict
        - price: {"input_per_1k": float|None, "output_per_1k": float|None, "input_per_1m": float|None, "output_per_1m": float|None}
        - latency_ms_hint: Optional[int]
        - throughput_tps_hint: Optional[float]
        - rate_limits: Optional[dict]
        - uptime_pct_hint: Optional[float]
        - release_date: Optional[str] ISO8601
        - provider: base provider like "openai|anthropic|mistral|meta|google|nvidia"
        - region: Optional[str]
        - source_aggregator: aggregator name like "groq|openrouter|chutes|nim"
        - endpoint: {"type": "openai_compatible", "base_url": str, "auth_header": {"Authorization": "Bearer ..."}}
        """
        raise NotImplementedError

    async def _http_get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        r = await _request_with_retries("GET", url, headers=headers)
        if r.status_code not in (200, 201):
            try:
                body = r.json()
            except Exception:
                body = {"text": r.text}
            raise RuntimeError(f"{self.name}_catalog_error status={r.status_code} body={body}")
        try:
            return r.json() or {}
        except Exception:
            return {}