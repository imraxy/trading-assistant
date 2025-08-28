"""
Model Catalog Aggregator and Curator

This module ingests model catalogs from multiple aggregators, normalizes and deduplicates
entries, ranks endpoints, and produces a curated shortlist of top models by category.

Supported aggregators (initial):
- Groq
- OpenRouter
- Chutes (stub)
- NVIDIA NIM (stub)

Environment variables:
- GROQ_API_KEY
- OPENROUTER_API_KEY
- CHUTES_API_KEY
- NIM_API_KEY or NIM_TOKEN
- NIM_BASE_URL
- AGGREGATORS_ENABLED=true|false
- AGGREGATOR_OPTOUT_OPENROUTER=true|false
- AGGREGATOR_OPTOUT_CHUTES=true|false
- AGGREGATOR_OPTOUT_NIM=true|false
- CATALOG_REFRESH_INTERVAL_HOURS=24
- CATALOG_CACHE_PATH=./.cache/models_catalog.json
- ROUTER_BUDGET_CEILING_USD_PER_M=5
- ROUTER_LATENCY_TARGET_MS=2000
"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .llm_provider import _request_with_retries  # reuse robust HTTP
from .aggregators.base import AggregatorClientBase  # optional base (present)


# -----------------------------
# Helpers and configuration
# -----------------------------

def _bool_env(name: str, default: bool = False) -> bool:
    v = str(os.getenv(name, str(default))).lower()
    return v in ("1", "true", "yes", "on")


CATALOG_REFRESH_INTERVAL_HOURS = int(os.getenv("CATALOG_REFRESH_INTERVAL_HOURS", "24"))
CATALOG_CACHE_PATH = os.getenv("CATALOG_CACHE_PATH", "./.cache/models_catalog.json")
ROUTER_BUDGET_CEILING_USD_PER_M = float(os.getenv("ROUTER_BUDGET_CEILING_USD_PER_M", "5"))
ROUTER_LATENCY_TARGET_MS = int(os.getenv("ROUTER_LATENCY_TARGET_MS", "2000"))

# Telemetry snapshot shape used by scoring hints
_TELEMETRY: Dict[str, Dict[str, Any]] = {}  # key > metrics


def telemetry_update(endpoint_key: str, success: bool, latency_ms: Optional[float] = None, cost_usd: Optional[float] = None) -> None:
    """Minimal telemetry aggregator; a fuller version can live in services/telemetry.py."""
    m = _TELEMETRY.setdefault(endpoint_key, {"count": 0, "ok": 0, "p50_ms": None, "p95_ms": None, "cost_sum": 0.0})
    m["count"] += 1
    if success:
        m["ok"] += 1
    # simple rolling median approx using last N, but keep it simple here
    if latency_ms is not None:
        arr = m.get("_lat_arr") or []
        arr.append(float(latency_ms))
        if len(arr) > 50:
            arr.pop(0)
        arr_sorted = sorted(arr)
        if arr_sorted:
            p50 = arr_sorted[len(arr_sorted) // 2]
            p95 = arr_sorted[int(len(arr_sorted) * 0.95) - 1 if len(arr_sorted) > 1 else 0]
            m["p50_ms"] = int(p50)
            m["p95_ms"] = int(max(p95, p50))
        m["_lat_arr"] = arr
    if cost_usd:
        m["cost_sum"] = float(m.get("cost_sum", 0.0)) + float(cost_usd)


# -----------------------------
# Normalization and scoring
# -----------------------------

def _strip_prefix(text: str, prefix: str) -> str:
    return text[len(prefix):] if text.startswith(prefix) else text


def _infer_provider_family(model_id: str, display_name: Optional[str] = None) -> Tuple[str, str]:
    """Infer base provider and logical family for dedup key."""
    mid = model_id.lower()
    name = (display_name or "").lower()
    # rough heuristics
    if "llama" in mid or "llama" in name:
        return "meta", "llama"
    if "gpt" in mid or "o4" in mid or "openai" in mid or "gpt" in name:
        return "openai", "gpt"
    if "claude" in mid or "anthropic" in mid:
        return "anthropic", "claude"
    if "mistral" in mid or "ministral" in mid:
        return "mistral", "mistral"
    if "gemini" in mid or "google" in mid:
        return "google", "gemini"
    if "qw" in mid and "nvidia" in name:
        return "nvidia", "qw"
    return "unknown", (display_name or model_id).split(":")[0].split("/")[-1]


def _logical_key(rec: Dict[str, Any]) -> str:
    provider = rec.get("provider") or "unknown"
    family = rec.get("family") or "unknown"
    version = rec.get("version") or ""
    modalities = tuple(sorted(set(rec.get("modalities") or [])))
    ctx = int(rec.get("context_window") or 0)
    return f"{provider}:{family}:{version}:{modalities}:{_bucket_ctx(ctx)}"


def _bucket_ctx(ctx: int) -> str:
    if ctx >= 200000: return "200k+"
    if ctx >= 128000: return "128k+"
    if ctx >= 64000: return "64k+"
    if ctx >= 32000: return "32k+"
    if ctx >= 16000: return "16k+"
    return "short"


def _price_per_m(price: Dict[str, Any]) -> Optional[float]:
    if not price:
        return None
    # prefer explicit per 1M, else scale from 1K
    if price.get("input_per_1m") and price.get("output_per_1m"):
        return float(price["input_per_1m"]) + float(price["output_per_1m"])
    if price.get("input_per_1k") or price.get("output_per_1k"):
        ip = float(price.get("input_per_1k") or 0.0)
        op = float(price.get("output_per_1k") or 0.0)
        return (ip + op) * 1000.0
    return None


def _capability_tags(rec: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    if (rec.get("json_mode")): tags.append("JSON")
    if (rec.get("tool_use")): tags.append("Tools")
    if "vision" in (rec.get("modalities") or []): tags.append("Vision")
    if "audio" in (rec.get("modalities") or []): tags.append("Audio")
    ctx = int(rec.get("context_window") or 0)
    if ctx >= 128000: tags.append("Long")
    return tags


def _score(rec: Dict[str, Any], task: Optional[Dict[str, Any]] = None) -> float:
    """Composite score S = wq*Quality + wr*Reliability + wl*Latency + wc*Cost + wk*Capabilities + ws*Stability."""
    # weights
    wq, wr, wl, wc, wk, ws = 0.35, 0.15, 0.15, 0.15, 0.15, 0.05

    # quality proxy: heuristic by family/version; can be overwritten with benchmark feeds later
    fam = (rec.get("family") or "").lower()
    ver = (rec.get("version") or "").lower()
    quality = 0.5
    if "llama" in fam:
        if "3.3" in ver or "70b" in rec.get("id","").lower(): quality = 0.78
        elif "8b" in rec.get("id","").lower(): quality = 0.65
    if "gpt" in fam or "o4" in rec.get("id","").lower():
        quality = 0.82 if "mini" not in rec.get("id","").lower() else 0.75
    if "claude" in fam:
        quality = 0.83 if "sonnet" in rec.get("id","").lower() else 0.78
    if "gemini" in fam:
        quality = 0.78 if "pro" in rec.get("id","").lower() else 0.7
    if "mistral" in fam:
        quality = 0.72

    # reliability from telemetry
    endpoint_key = rec.get("_best_endpoint_key")
    rel = 0.6
    if endpoint_key and endpoint_key in _TELEMETRY:
        m = _TELEMETRY[endpoint_key]
        count = max(1, m.get("count", 0))
        ok = m.get("ok", 0)
        rel = 0.4 + 0.6 * (ok / count)

    # latency: higher score better; normalize target around ROUTER_LATENCY_TARGET_MS
    lat_target = float(task.get("latency_target_ms") if task else ROUTER_LATENCY_TARGET_MS)
    p50 = None
    if endpoint_key and endpoint_key in _TELEMETRY:
        p50 = _TELEMETRY[endpoint_key].get("p50_ms")
    lat_ms = float(rec.get("latency_ms_hint") or p50 or lat_target)
    latency_score = max(0.0, min(1.0, (lat_target / max(1.0, lat_ms))))
    # cap above target to 1.0
    latency_score = min(1.0, latency_score)

    # cost-efficiency: inverse of price within budget
    budget = float(task.get("budget_usd_per_m") if task else ROUTER_BUDGET_CEILING_USD_PER_M)
    pm = _price_per_m(rec.get("price") or {})
    if pm is None:
        cost_eff = 0.6  # unknown
    else:
        # if within budget, scale between 0.6..1; if above, decay quickly
        if pm <= budget: cost_eff = max(0.6, 1.0 - (pm / max(1.0, budget)) * 0.4)
        else: cost_eff = max(0.05, 0.6 - min(1.0, (pm - budget) / budget) * 0.6)

    # capability fit: modalities, JSON, tools, context length
    req = (task or {}).get("requirements") or {}
    modalities_req = set(req.get("modalities") or [])
    have_mods = set(rec.get("modalities") or [])
    mod_fit = 1.0 if not modalities_req else (1.0 if modalities_req.issubset(have_mods) else 0.0)
    json_need = bool(req.get("json_mode"))
    tool_need = bool(req.get("tool_use"))
    json_fit = 1.0 if (not json_need or rec.get("json_mode")) else 0.0
    tool_fit = 1.0 if (not tool_need or rec.get("tool_use")) else 0.0
    ctx_min = int(req.get("context_min") or 0)
    ctx_fit = 1.0 if int(rec.get("context_window") or 0) >= ctx_min else 0.0
    cap_fit = 0.4 * mod_fit + 0.2 * json_fit + 0.2 * tool_fit + 0.2 * ctx_fit

    # stability: prefer stable release_date present
    stability = 0.6 if rec.get("release_date") else 0.5

    S = wq*quality + wr*rel + wl*latency_score + wc*cost_eff + wk*cap_fit + ws*stability
    return round(S, 4)


# -----------------------------
# Aggregator fetchers
# -----------------------------

class GroqCatalog(AggregatorClientBase):
    name = "groq"

    async def list_models(self) -> List[Dict[str, Any]]:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return []
        headers = {"Authorization": f"Bearer {key}"}
        r = await _request_with_retries("GET", "https://api.groq.com/openai/v1/models", headers=headers)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        out: List[Dict[str, Any]] = []
        for m in (data.get("data") or []):
            mid = str(m.get("id", ""))
            provider, family = _infer_provider_family(mid)
            # heuristics
            modalities = ["text", "code"]
            if "vision" in mid or "multimodal" in mid:
                modalities.append("vision")
            rec = {
                "id": mid,
                "display_name": m.get("id"),
                "family": family,
                "version": "",
                "modalities": modalities,
                "context_window": 32768 if "32768" in mid else 8192,
                "tool_use": True,
                "json_mode": True,
                "guardrails": None,
                "price": {},  # not exposed via endpoint; leave empty
                "latency_ms_hint": 900 if "70b" in mid else 600,
                "throughput_tps_hint": None,
                "rate_limits": None,
                "uptime_pct_hint": None,
                "release_date": None,
                "provider": provider,
                "region": None,
                "source_aggregator": "groq",
                "endpoint": {
                    "type": "openai_compatible",
                    "base_url": "https://api.groq.com/openai/v1",
                    "auth_header": {"Authorization": f"Bearer {key}"},
                },
            }
            out.append(rec)
        return out


class OpenRouterCatalog(AggregatorClientBase):
    name = "openrouter"

    async def list_models(self) -> List[Dict[str, Any]]:
        if _bool_env("AGGREGATOR_OPTOUT_OPENROUTER", False):
            return []
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            return []
        headers = {"Authorization": f"Bearer {key}"}
        r = await _request_with_retries("GET", "https://openrouter.ai/api/v1/models", headers=headers)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        out: List[Dict[str, Any]] = []
        for m in (data.get("data") or []):
            mid = str(m.get("id", ""))
            name = str(m.get("name", mid))
            provider, family = _infer_provider_family(mid, name)
            pricing = m.get("pricing") or {}
            # normalize pricing
            price = {
                "input_per_1k": _to_float(pricing.get("prompt")),
                "output_per_1k": _to_float(pricing.get("completion")),
                "input_per_1m": _scale_m(pricing.get("prompt")),
                "output_per_1m": _scale_m(pricing.get("completion")),
            }
            modalities = []
            if m.get("architecture", {}).get("modality"):
                mm = m["architecture"]["modality"]
                if isinstance(mm, list):
                    modalities = [str(x) for x in mm]
                else:
                    modalities = [str(mm)]
            if not modalities:
                modalities = ["text", "code"]
            rec = {
                "id": mid,
                "display_name": name,
                "family": family,
                "version": "",
                "modalities": modalities,
                "context_window": int(m.get("context_length") or 8192),
                "tool_use": bool(m.get("top_provider", {}).get("tools")),
                "json_mode": True,
                "guardrails": None,
                "price": price,
                "latency_ms_hint": None,
                "throughput_tps_hint": None,
                "rate_limits": None,
                "uptime_pct_hint": None,
                "release_date": None,
                "provider": provider,
                "region": None,
                "source_aggregator": "openrouter",
                "endpoint": {
                    "type": "openai_compatible",
                    "base_url": "https://openrouter.ai/api/v1",
                    "auth_header": {"Authorization": f"Bearer {key}", "HTTP-Referer": "https://localhost", "X-Title": "trading-assistant"},
                },
            }
            out.append(rec)
        return out


class ChutesCatalog(AggregatorClientBase):
    name = "chutes"

    async def list_models(self) -> List[Dict[str, Any]]:
        # Placeholder; if CHUTES_API_KEY present, return empty list until API mapping is finalized.
        if _bool_env("AGGREGATOR_OPTOUT_CHUTES", False):
            return []
        if not os.getenv("CHUTES_API_KEY"):
            return []
        # TODO: implement when API schema confirmed
        return []


class NIMCatalog(AggregatorClientBase):
    name = "nim"

    async def list_models(self) -> List[Dict[str, Any]]:
        if _bool_env("AGGREGATOR_OPTOUT_NIM", False):
            return []
        token = os.getenv("NIM_API_KEY") or os.getenv("NIM_TOKEN")
        base = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com")
        if not token:
            return []
        # Some NIM deployments expose OpenAI-compatible chat completions at /v1/chat/completions without listing endpoint.
        # Seed with a few common entries as placeholders; users can still route by exact id.
        seeds = [
            {"id": "meta/llama-3.1-70b-instruct", "modalities": ["text", "code"], "context_window": 128000},
            {"id": "meta/llama-3.1-8b-instruct", "modalities": ["text", "code"], "context_window": 128000},
            {"id": "google/gemma-2-9b-it", "modalities": ["text", "code"], "context_window": 8192},
        ]
        out: List[Dict[str, Any]] = []
        for s in seeds:
            mid = s["id"]
            provider, family = _infer_provider_family(mid)
            rec = {
                "id": mid,
                "display_name": mid.split("/")[-1],
                "family": family,
                "version": "",
                "modalities": s["modalities"],
                "context_window": s["context_window"],
                "tool_use": True,
                "json_mode": True,
                "guardrails": None,
                "price": {},
                "latency_ms_hint": 800,
                "throughput_tps_hint": None,
                "rate_limits": None,
                "uptime_pct_hint": None,
                "release_date": None,
                "provider": provider,
                "region": None,
                "source_aggregator": "nim",
                "endpoint": {
                    "type": "openai_compatible",
                    "base_url": f"{base}/v1",
                    "auth_header": {"Authorization": f"Bearer {token}"},
                },
            }
            out.append(rec)
        return out


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _scale_m(v: Any) -> Optional[float]:
    f = _to_float(v)
    return f * 1000.0 if f is not None else None


# -----------------------------
# Catalog lifecycle
# -----------------------------

_CATALOG_CACHE: Dict[str, Any] = {}
_CATALOG_TS: float = 0.0


async def _fetch_all_catalogs() -> List[Dict[str, Any]]:
    if not _bool_env("AGGREGATORS_ENABLED", True):
        return []
    tasks = []
    outs: List[List[Dict[str, Any]]] = []
    # Build client list
    clients = [GroqCatalog(), OpenRouterCatalog(), ChutesCatalog(), NIMCatalog()]
    # sequential to keep code simple; can convert to asyncio.gather if needed
    for client in clients:
        try:
            models = await client.list_models()
            outs.append(models)
        except Exception:
            outs.append([])
    # flatten
    flat: List[Dict[str, Any]] = []
    for arr in outs:
        flat.extend(arr or [])
    return flat


def _merge_offers(recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate logical models and rank endpoints by effective cost then latency."""
    by_key: Dict[str, Dict[str, Any]] = {}
    for r in recs:
        # ensure provider/family fields
        if not r.get("provider") or not r.get("family"):
            prov, fam = _infer_provider_family(r.get("id", ""), r.get("display_name"))
            r["provider"] = r.get("provider") or prov
            r["family"] = r.get("family") or fam
        key = _logical_key(r)
        price_m = _price_per_m(r.get("price") or {}) or 999999.0
        lat = float(r.get("latency_ms_hint") or 2000.0)
        ep = r.get("endpoint") or {}
        ep_key = f"{r.get('source_aggregator','unknown')}|{ep.get('base_url','')}|{r.get('id','')}"
        offer = {
            "aggregator": r.get("source_aggregator"),
            "endpoint": ep,
            "price_per_m": price_m,
            "latency_ms": lat,
            "uptime": r.get("uptime_pct_hint"),
            "id": r.get("id"),
        }
        if key not in by_key:
            rec = dict(r)
            rec["_offers"] = [offer]
            rec["_best_endpoint_key"] = ep_key
            by_key[key] = rec
        else:
            rec = by_key[key]
            offers = rec.get("_offers") or []
            offers.append(offer)
            # sort by price asc, then latency asc
            offers.sort(key=lambda o: (o.get("price_per_m") or 9e9, o.get("latency_ms") or 9e9))
            rec["_offers"] = offers
            best = offers[0]
            rec["_best_endpoint_key"] = f"{best.get('aggregator')}|{best.get('endpoint',{}).get('base_url','')}|{best.get('id')}"
            # merge minimal fields
            rec["price"] = rec.get("price") or r.get("price")
            rec["latency_ms_hint"] = min(float(rec.get("latency_ms_hint") or 9e9), lat)
    # flatten merged list
    return list(by_key.values())


def _categorize(rec: Dict[str, Any]) -> List[str]:
    cats: List[str] = []
    mods = set(rec.get("modalities") or [])
    ctx = int(rec.get("context_window") or 0)
    # Categories
    cats.append("general_chat")
    # coding
    if "code" in mods or "text" in mods:
        cats.append("coding")
    # advanced reasoning: families known for high reasoning
    fam = (rec.get("family") or "").lower()
    if any(k in fam for k in ["gpt", "claude", "llama"]):
        cats.append("advanced_reasoning")
    if ctx >= 128000:
        cats.append("long_context")
    if "vision" in mods:
        cats.append("multimodal")
    if rec.get("json_mode") or rec.get("tool_use"):
        cats.append("structured_tool_use")
    # safety placeholder
    cats.append("safety_guardrailed")
    return list(sorted(set(cats)))


def _curate(models: List[Dict[str, Any]], task: Optional[Dict[str, Any]] = None, per_cat_cap: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    """Produce a curated shortlist per category with caps."""
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in models:
        s = _score(r, task)
        rr = dict(r)
        rr["_score"] = s
        rr["tags"] = _capability_tags(rr)
        scored.append((s, rr))
    scored.sort(key=lambda t: t[0], reverse=True)
    out: Dict[str, List[Dict[str, Any]]] = {
        "general_chat": [],
        "coding": [],
        "advanced_reasoning": [],
        "long_context": [],
        "multimodal": [],
        "structured_tool_use": [],
        "safety_guardrailed": [],
    }
    for _, rec in scored:
        for cat in _categorize(rec):
            if len(out[cat]) < per_cat_cap:
                out[cat].append(rec)
    return out


async def refresh_catalog(force: bool = False) -> Dict[str, Any]:
    """Fetch, normalize, deduplicate, rank endpoints, and curate."""
    global _CATALOG_CACHE, _CATALOG_TS
    now = time.time()
    if (not force) and _CATALOG_CACHE and (now - _CATALOG_TS) < CATALOG_REFRESH_INTERVAL_HOURS * 3600:
        return _CATALOG_CACHE

    models = await _fetch_all_catalogs()
    merged = _merge_offers(models)
    curated = _curate(merged, task={
        "budget_usd_per_m": ROUTER_BUDGET_CEILING_USD_PER_M,
        "latency_target_ms": ROUTER_LATENCY_TARGET_MS,
        "requirements": {},  # default balanced
    })
    payload = {
        "ts": now,
        "models": merged,
        "curated": curated,
    }
    _CATALOG_CACHE = payload
    _CATALOG_TS = now

    # Persist to disk best-effort
    try:
        os.makedirs(os.path.dirname(CATALOG_CACHE_PATH), exist_ok=True)
        with open(CATALOG_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass

    return payload


async def get_catalog(force_refresh: bool = False) -> Dict[str, Any]:
    global _CATALOG_CACHE, _CATALOG_TS
    if _CATALOG_CACHE and not force_refresh:
        return _CATALOG_CACHE
    # Try disk cache
    if not force_refresh and not _CATALOG_CACHE:
        try:
            if os.path.exists(CATALOG_CACHE_PATH):
                with open(CATALOG_CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _CATALOG_CACHE = data
                _CATALOG_TS = float(data.get("ts") or 0.0)
        except Exception:
            pass
    # If stale, refresh live
    now = time.time()
    if (not _CATALOG_CACHE) or ((now - _CATALOG_TS) >= CATALOG_REFRESH_INTERVAL_HOURS * 3600):
        return await refresh_catalog(force=True)
    return _CATALOG_CACHE


async def get_top_models(filters: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Return curated shortlist; apply basic filters client-side."""
    cat = await get_catalog(False)
    curated = dict(cat.get("curated") or {})
    return _apply_filters_to_curated(curated, filters or {})


async def get_all_models(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cat = await get_catalog(False)
    items = list(cat.get("models") or [])
    return _apply_filters_to_list(items, filters or {})


def _apply_filters_to_curated(curated: Dict[str, List[Dict[str, Any]]], filters: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for k, arr in curated.items():
        out[k] = _apply_filters_to_list(arr, filters)
    return out


def _apply_filters_to_list(items: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    modality = filters.get("modality")
    budget = filters.get("budget_usd_per_m")
    ctx_min = int(filters.get("context_min") or 0)
    latency = int(filters.get("latency_target_ms") or 0)
    only_vision = filters.get("only_vision", False)
    out: List[Dict[str, Any]] = []
    for r in items:
        if modality and modality not in (r.get("modalities") or []):
            continue
        if ctx_min and int(r.get("context_window") or 0) < ctx_min:
            continue
        pm = _price_per_m(r.get("price") or {})
        if budget is not None and pm is not None and pm > float(budget):
            continue
        if only_vision and "vision" not in (r.get("modalities") or []):
            continue
        # latency filter is best-effort
        if latency:
            lat = float(r.get("latency_ms_hint") or latency)
            if lat > float(latency) * 1.5:  # allow some margin
                continue
        out.append(r)
    return out