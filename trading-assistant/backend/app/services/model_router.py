"""
Auto router for aggregator-backed model selection and failover.

- Pulls the merged catalog from services.model_catalog
- Filters by task constraints
- Ranks by curated score order (already computed in catalog)
- Attempts request on best endpoint first with graceful failover
- Updates lightweight telemetry

Currently supports OpenAI-compatible chat completions across Groq, OpenRouter, Chutes [todo], and NVIDIA NIM.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .llm_provider import _request_with_retries  # pacing + retries
from . import model_catalog as mc


class RouterError(RuntimeError):
    pass


def _endpoint_key(aggr: str, base_url: str, model_id: str) -> str:
    return f"{aggr}|{base_url}|{model_id}"


def _constraints_defaults(task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t = task or {}
    return {
        "budget_usd_per_m": float(t.get("budget_usd_per_m", mc.ROUTER_BUDGET_CEILING_USD_PER_M)),
        "latency_target_ms": int(t.get("latency_target_ms", mc.ROUTER_LATENCY_TARGET_MS)),
        "requirements": dict(t.get("requirements", {})),
    }


def _candidate_sort_key(r: Dict[str, Any]) -> Tuple[float, float]:
    # lower cost then lower latency
    price = mc._price_per_m(r.get("price") or {}) or 9e9
    lat = float(r.get("latency_ms_hint") or 9e9)
    return (price, lat)


def _filter_candidates(models: List[Dict[str, Any]], task: Dict[str, Any]) -> List[Dict[str, Any]]:
    req = task.get("requirements", {}) or {}
    mod = set(req.get("modalities") or [])
    ctx_min = int(req.get("context_min") or 0)
    json_mode = bool(req.get("json_mode", False))
    tool_use = bool(req.get("tool_use", False))
    preferred_model = (req.get("preferred_model_id") or "").strip()
    preferred_agg = (req.get("preferred_aggregator") or "").strip().lower()
    budget = float(task.get("budget_usd_per_m", mc.ROUTER_BUDGET_CEILING_USD_PER_M))

    out: List[Dict[str, Any]] = []
    for r in models:
        if preferred_model and str(r.get("id") or "") != preferred_model:
            continue
        if preferred_agg and (str(r.get("source_aggregator") or "").lower() != preferred_agg):
            continue
        if mod and not mod.issubset(set(r.get("modalities") or [])):
            continue
        if ctx_min and int(r.get("context_window") or 0) < ctx_min:
            continue
        pm = mc._price_per_m(r.get("price") or {})
        if pm is not None and pm > budget:
            continue
        if json_mode and not r.get("json_mode"):
            continue
        if tool_use and not r.get("tool_use"):
            continue
        out.append(r)

    # Seed with catalog sort (already ranked by score) but apply a stable second-key on price/lat
    out.sort(key=_candidate_sort_key)
    return out


async def _openai_compatible_chat_complete(base_url: str, auth_header: Dict[str, str], model: str, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 600) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = dict(auth_header or {})
    headers["Content-Type"] = "application/json"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = await _request_with_retries("POST", url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json() or {}
    try:
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    except Exception:
        # Some providers might return plain text field
        return (data.get("content") or "").strip()


async def auto_chat_complete(system: str, user: str, task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a chat completion using the Auto Best route.

    task fields:
    - budget_usd_per_m: float (default from env)
    - latency_target_ms: int (default from env)
    - requirements: { modalities: [text,code,vision,audio], context_min: int, json_mode: bool, tool_use: bool }
    """
    t = _constraints_defaults(task)
    # Get catalog and merged models
    catalog = await mc.get_catalog(False)
    merged: List[Dict[str, Any]] = list(catalog.get("models") or [])
    candidates = _filter_candidates(merged, t)
    if not candidates:
        raise RouterError("no_candidate_models")

    errors: List[Dict[str, Any]] = []
    start = time.time()
    for idx, rec in enumerate(candidates[:24]):  # limit breadth
        offers: List[Dict[str, Any]] = list(rec.get("_offers") or [])
        if not offers:
            # synthesize from best endpoint key
            ep = rec.get("endpoint") or {}
            offers = [{
                "aggregator": rec.get("source_aggregator"),
                "endpoint": ep,
                "price_per_m": mc._price_per_m(rec.get("price") or {}),
                "latency_ms": float(rec.get("latency_ms_hint") or 0),
                "id": rec.get("id"),
            }]
        # iterate best endpoint first
        for jdx, off in enumerate(offers[:4]):  # avoid long fail chain
            aggr = off.get("aggregator") or "unknown"
            ep = off.get("endpoint") or {}
            base_url = str(ep.get("base_url") or "")
            auth = dict(ep.get("auth_header") or {})
            model_id = str(off.get("id") or rec.get("id") or "")

            if not base_url or not auth or not model_id:
                continue

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            ep_key = _endpoint_key(aggr, base_url, model_id)
            try:
                t0 = time.time()
                content = await _openai_compatible_chat_complete(base_url, auth, model_id, messages)
                dt = (time.time() - t0) * 1000.0
                mc.telemetry_update(ep_key, True, latency_ms=dt, cost_usd=None)
                return {
                    "status": "success",
                    "content": content,
                    "model": {
                        "id": model_id,
                        "display_name": rec.get("display_name") or model_id,
                        "provider": rec.get("provider"),
                        "family": rec.get("family"),
                        "source_aggregator": aggr,
                        "base_url": base_url,
                        "tags": mc._capability_tags(rec),
                        "context_window": rec.get("context_window"),
                        "price_per_m": mc._price_per_m(rec.get("price") or {}),
                    },
                    "latency_ms": int(dt),
                    "attempts": idx + 1,
                }
            except Exception as e:
                # record failure and proceed to next endpoint or model
                mc.telemetry_update(ep_key, False, latency_ms=None, cost_usd=None)
                errors.append({"endpoint": ep_key, "error": str(e)[:400]})
                continue

    raise RouterError(json.dumps({"message": "all_endpoints_failed", "errors": errors[:6]}))