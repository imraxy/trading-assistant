"""
Models API routes for aggregator-backed catalog and curation.

Base prefix is expected to be mounted at /api/v1/models in app.main.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Query

from ...services import model_catalog as mc

router = APIRouter()


def _filters_from_query(
    category: Optional[str],
    modality: Optional[str],
    context_min: Optional[int],
    budget_usd_per_m: Optional[float],
    latency_target_ms: Optional[int],
) -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    if modality:
        f["modality"] = modality
    if context_min is not None:
        f["context_min"] = int(context_min)
    if budget_usd_per_m is not None:
        f["budget_usd_per_m"] = float(budget_usd_per_m)
    if latency_target_ms is not None:
        f["latency_target_ms"] = int(latency_target_ms)
    return f


@router.get("/top")
async def get_top(
    category: Optional[str] = Query(None, description="Category filter e.g., general_chat, coding, advanced_reasoning, long_context, multimodal, structured_tool_use, safety_guardrailed"),
    modality: Optional[str] = Query(None, description="Prefer models that include this modality e.g., text, code, vision, audio"),
    context_min: Optional[int] = Query(None, ge=0),
    budget_usd_per_m: Optional[float] = Query(None, ge=0),
    latency_target_ms: Optional[int] = Query(None, ge=1),
    per_cat_cap: Optional[int] = Query(8, ge=1, le=20),
):
    curated = await mc.get_top_models(
        _filters_from_query(category, modality, context_min, budget_usd_per_m, latency_target_ms)
    )
    if category and curated.get(category):
        return {"status": "success", "data": {category: curated.get(category, [])[: per_cat_cap or 8]}}
    # Enforce cap per category
    capped = {k: (v[: per_cat_cap or 8]) for k, v in curated.items()}
    return {"status": "success", "data": capped}


@router.get("/all")
async def get_all(
    modality: Optional[str] = Query(None),
    context_min: Optional[int] = Query(None, ge=0),
    budget_usd_per_m: Optional[float] = Query(None, ge=0),
    latency_target_ms: Optional[int] = Query(None, ge=1),
):
    items = await mc.get_all_models(
        _filters_from_query(None, modality, context_min, budget_usd_per_m, latency_target_ms)
    )
    return {"status": "success", "data": items}


@router.post("/refresh")
async def refresh():
    data = await mc.refresh_catalog(force=True)
    return {"status": "success", "data": {"ts": data.get("ts"), "counts": {"models": len(data.get("models") or []), "categories": len((data.get("curated") or {}).keys())}}}


@router.get("/health")
async def health():
    # Surface minimal telemetry and cache status for diagnostics
    try:
        # Access internal cache fields best effort
        cat = await mc.get_catalog(False)
        models = cat.get("models") or []
        curated = cat.get("curated") or {}
        # Access internal telemetry dict for quick summary
        tel = getattr(mc, "_TELEMETRY", {}) or {}
        total_eps = len(tel.keys())
        ok = sum(1 for k, v in tel.items() if (v or {}).get("ok", 0) > 0)
        return {
            "status": "success",
            "data": {
                "catalog": {"models": len(models), "categories": list(curated.keys()), "ts": cat.get("ts")},
                "telemetry": {"endpoints": total_eps, "endpoints_ever_ok": ok},
                "config": {
                    "budget_per_m": mc.ROUTER_BUDGET_CEILING_USD_PER_M,
                    "latency_target_ms": mc.ROUTER_LATENCY_TARGET_MS,
                    "refresh_interval_hours": mc.CATALOG_REFRESH_INTERVAL_HOURS,
                },
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}