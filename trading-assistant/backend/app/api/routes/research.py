"""
Research & Decision API

Fetches TA/FA/News using public/free APIs and synthesizes a decision via the LLM
provider. This gives a reliable agentic pipeline without relying on the model to
perform outbound network calls by itself.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
import httpx
import os
import math

from ...services.ta_utils import rsi as rsi_calc, ema as ema_calc, support_resistance
from ...services.llm_provider import get_llm_client, get_llm_clients, get_llm_client_for, available_providers
from ...database.database import SessionLocal, engine
from ...database import models as db_models


router = APIRouter()
_DECISION_CACHE: Dict[str, Dict[str, Any]] = {}
_DECISION_TTL_SECONDS = int(os.getenv("DECISION_TTL_SECONDS", "300"))
import time


def _normalize_for_binance(symbol: str) -> str:
    # Strip Bybit-specific size prefixes like 1000PEPEUSDT -> PEPEUSDT
    sym = symbol.upper().strip()
    if sym.endswith("USDT"):
        base = sym[:-4]
        # remove leading digits in base (e.g., 1000PEPE -> PEPE)
        i = 0
        while i < len(base) and base[i].isdigit():
            i += 1
        norm_base = base[i:] if i < len(base) else base
        if not norm_base:
            norm_base = base
        return f"{norm_base}USDT"
    return sym


def _base_without_prefix(symbol: str) -> str:
    """Return base asset code without quote (USDT/USDC) and any leading digits (e.g., 1000PEPE -> PEPE)."""
    s = symbol.upper().strip()
    for quote in ("USDT", "USDC"):
        if s.endswith(quote):
            s = s[: -len(quote)]
            break
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    base = s[i:] if i < len(s) else s
    return base or s


async def fetch_binance_ohlc(symbol: str, interval: str = "1h", limit: int = 200) -> List[float]:
    url = "https://api.binance.com/api/v3/klines"
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Try original symbol first
        for s in [symbol.upper(), _normalize_for_binance(symbol)]:
            params = {"symbol": s, "interval": interval, "limit": min(limit, 1000)}
            try:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
                closes = [float(k[4]) for k in data]
                if closes:
                    return closes
            except Exception:
                continue
    return []


async def fetch_coingecko_market(symbol: str) -> Dict[str, Any]:
    try:
        query = _base_without_prefix(symbol).lower()
        async with httpx.AsyncClient(timeout=15.0) as client:
            sr = await client.get("https://api.coingecko.com/api/v3/search", params={"query": query})
        sr.raise_for_status()
        coins = (sr.json() or {}).get("coins", [])
        if not coins:
            return {}
        coin_id = coins[0].get("id")
        async with httpx.AsyncClient(timeout=15.0) as client:
            m = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                    "sparkline": "false",
                },
            )
        m.raise_for_status()
        data = m.json()
        md = data.get("market_data", {})
        return {
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "market_cap": md.get("market_cap", {}).get("usd"),
            "volume_24h": md.get("total_volume", {}).get("usd"),
            "price_change_24h_pct": md.get("price_change_percentage_24h"),
        }
    except Exception:
        return {}


async def fetch_coingecko_closes(symbol: str, days: int = 7, interval: str = "hourly") -> List[float]:
    """Fallback OHLC closes from CoinGecko market_chart when Binance lacks the pair."""
    try:
        query = _base_without_prefix(symbol).lower()
        async with httpx.AsyncClient(timeout=15.0) as client:
            sr = await client.get("https://api.coingecko.com/api/v3/search", params={"query": query})
        sr.raise_for_status()
        coins = (sr.json() or {}).get("coins", [])
        if not coins:
            return []
        coin_id = coins[0].get("id")
        async with httpx.AsyncClient(timeout=20.0) as client:
            mc = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": str(days), "interval": interval},
            )
        mc.raise_for_status()
        data = mc.json() or {}
        prices = data.get("prices") or []
        closes = [float(p[1]) for p in prices if isinstance(p, list) and len(p) >= 2]
        return closes
    except Exception:
        return []

async def fetch_news(symbol: str) -> List[Dict[str, Any]]:
    token = os.getenv("CRYPTOPANIC_TOKEN") or os.getenv("CRYPTOPANIC_API_TOKEN")
    if not token:
        return []
    cur = _base_without_prefix(symbol)
    params = {"auth_token": token, "currencies": cur, "public": "true", "kind": "news"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get("https://cryptopanic.com/api/v1/posts/", params=params)
    if r.status_code != 200:
        return []
    data = r.json().get("results", [])
    out: List[Dict[str, Any]] = []
    for item in data[:5]:
        out.append({
            "title": item.get("title"),
            "source": (item.get("source") or {}).get("title"),
            "url": item.get("url"),
        })
    return out


def compute_macd(closes: List[float]) -> Dict[str, Optional[float]]:
    if len(closes) < 35:
        return {"macd": None, "signal": None, "hist": None}
    ema12 = ema_calc(closes, 12)
    ema26 = ema_calc(closes, 26)
    macd_line = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
    signal = ema_calc(macd_line, 9)
    hist = macd_line[-len(signal):]
    hist = [m - s for m, s in zip(hist, signal)]
    return {"macd": macd_line[-1], "signal": signal[-1], "hist": hist[-1]}


@router.get("/research/decide")
async def research_decide(
    symbol: str = Query(...),
    side: str = Query(...),
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh decision"),
    debug: bool = Query(False, description="Include exact LLM prompt in response"),
    provider: str | None = Query(None, description="Force a specific LLM provider (openai|gemini|anthropic|mistral|groq)")
) -> Dict[str, Any]:
    """Auto-research pipeline with graceful fallbacks and provenance.

    - Try public sources (Binance, CoinGecko, CryptoPanic).
    - If sources fail, still return 200 with a decision by asking the LLM to perform full research.
    - Include provenance of which sources contributed.
    """
    # Ensure tables exist for decision persistence
    try:
        db_models.Base.metadata.create_all(bind=engine)
    except Exception:
        pass

    # Cache key
    cache_key = f"{symbol}|{side}"
    now = time.time()
    cached = _DECISION_CACHE.get(cache_key)
    if not force_refresh and cached and (now - cached.get("_ts", 0)) < _DECISION_TTL_SECONDS:
        return {"status": "success", "data": cached["data"], "cached": True}

    ta: Dict[str, Any] = {}
    fa: Dict[str, Any] = {}
    news: List[Dict[str, Any]] = []
    provenance = {"ta": "none", "fa": "none", "news": "none"}

    # Position context from latest snapshots (adds entry/size/lev/pnl and oriented deltas)
    position_ctx: Dict[str, Any] = {}
    deltas_ctx: Dict[str, Any] = {}
    try:
        db = SessionLocal()
        # Latest snapshot for this (symbol, side)
        q_latest = (
            db.query(db_models.PositionSnapshot)
            .filter(db_models.PositionSnapshot.symbol == symbol, db_models.PositionSnapshot.side == side)
            .order_by(db_models.PositionSnapshot.captured_at.desc())
            .limit(1)
        )
        latest_row = q_latest.first()
        if latest_row:
            position_ctx = {
                "entry_price": float(latest_row.entry_price or 0),
                "current_price": float(latest_row.current_price or 0),
                "size": float(latest_row.size or 0),
                "position_value": float(latest_row.position_value or 0),
                "leverage": float(latest_row.leverage or 0),
                "pnl_usd": float(latest_row.unrealized_pnl or 0),
                "pnl_pct": float(latest_row.pnl_percentage or 0),
                "category": str(latest_row.category or ""),
                "captured_at": latest_row.captured_at.isoformat(),
            }
            # Hedge presence = do we have the opposite side open recently?
            opp_side = "Sell" if side == "Buy" else "Buy"
            q_opp = (
                db.query(db_models.PositionSnapshot)
                .filter(db_models.PositionSnapshot.symbol == symbol, db_models.PositionSnapshot.side == opp_side)
                .order_by(db_models.PositionSnapshot.captured_at.desc())
                .limit(1)
            )
            opp = q_opp.first()
            position_ctx["has_hedge"] = bool(opp and (opp.size or 0) > 0)

            # Compute 1h/1d/1w price % change oriented by side
            from datetime import datetime, timedelta
            now_py = datetime.utcnow()
            windows = {
                "1h": now_py - timedelta(hours=1),
                "1d": now_py - timedelta(days=1),
                "1w": now_py - timedelta(days=7),
            }
            for label, since in windows.items():
                q_hist = (
                    db.query(db_models.PositionSnapshot)
                    .filter(
                        db_models.PositionSnapshot.symbol == symbol,
                        db_models.PositionSnapshot.side == side,
                        db_models.PositionSnapshot.captured_at <= latest_row.captured_at,
                    )
                    .order_by(db_models.PositionSnapshot.captured_at.asc())
                )
                rows = q_hist.all()
                earliest = None
                for r in rows:
                    if r.captured_at >= since:
                        earliest = r
                        break
                if earliest is None:
                    before = [r for r in rows if r.captured_at < since]
                    if before:
                        earliest = before[-1]
                if earliest is None:
                    continue
                try:
                    if (earliest.current_price or 0) > 0:
                        price_pct = ((latest_row.current_price - earliest.current_price) / earliest.current_price) * 100.0
                    else:
                        price_pct = 0.0
                except Exception:
                    price_pct = 0.0
                oriented = price_pct if side == "Buy" else -price_pct
                deltas_ctx[label] = oriented
        try:
            db.close()
        except Exception:
            pass
    except Exception:
        pass

    # TA (Binance OHLC) – try multiple intervals for robustness; fallback to CoinGecko market_chart
    try:
        c1h = await fetch_binance_ohlc(symbol, interval="1h", limit=300)
        c1d = await fetch_binance_ohlc(symbol, interval="1d", limit=300)
        closes = c1h or c1d
        provenance_ta = "binance"
        if not closes:
            # Fallback to CoinGecko close series
            closes = await fetch_coingecko_closes(symbol, days=7, interval="hourly")
            provenance_ta = "coingecko_prices" if closes else "none"
        if closes:
            ta_rsi = rsi_calc(closes, 14)
            ta["rsi"] = ta_rsi[-1] if ta_rsi else None
            ta["ema50"] = ema_calc(closes, 50)[-1] if len(closes) >= 50 else None
            ta["ema200"] = ema_calc(closes, 200)[-1] if len(closes) >= 200 else None
            sr = support_resistance(closes, lookback=100)
            ta["support_levels"] = [sr.get("support")]
            ta["resistance_levels"] = [sr.get("resistance")]
            ta.update(compute_macd(closes))
            # Derived signals
            sig: list[str] = []
            try:
                rsi_v = ta.get("rsi")
                if rsi_v is not None:
                    if rsi_v >= 70: sig.append("RSI overbought")
                    elif rsi_v <= 30: sig.append("RSI oversold")
            except Exception:
                pass
            try:
                e50 = ta.get("ema50"); e200 = ta.get("ema200")
                if e50 and e200:
                    if e50 > e200: sig.append("EMA uptrend (50>200)")
                    elif e50 < e200: sig.append("EMA downtrend (50<200)")
            except Exception:
                pass
            try:
                m = ta.get("macd"); s = ta.get("signal")
                if m is not None and s is not None:
                    if m > s: sig.append("MACD bullish")
                    elif m < s: sig.append("MACD bearish")
            except Exception:
                pass
            ta["signals"] = sig
            provenance["ta"] = provenance_ta
    except Exception:
        # ignore; fall back to LLM-only if needed
        pass

    # FA (CoinGecko)
    try:
        fa = await fetch_coingecko_market(symbol)
        if fa:
            provenance["fa"] = "coingecko"
    except Exception:
        pass

    # News (CryptoPanic)
    try:
        news = await fetch_news(symbol)
        if news:
            provenance["news"] = "cryptopanic"
    except Exception:
        pass

    # Compact summaries to guide the model clearly
    ta_summary = []
    if ta:
        if ta.get("rsi") is not None:
            ta_summary.append(f"RSI {ta['rsi']:.1f}")
        if ta.get("ema50") and ta.get("ema200"):
            trend = "up" if ta["ema50"] > ta["ema200"] else "down"
            ta_summary.append(f"EMA50/200 {trend}")
        if ta.get("macd") is not None and ta.get("signal") is not None:
            cross = "bullish" if ta["macd"] > ta["signal"] else "bearish"
            ta_summary.append(f"MACD {cross}")
    fa_summary = []
    if fa:
        if fa.get("price_change_24h_pct") is not None:
            fa_summary.append(f"24h {fa['price_change_24h_pct']:.2f}%")
        if fa.get("market_cap"):
            fa_summary.append("market-cap present")
        if fa.get("volume_24h"):
            fa_summary.append("volume present")
    news_summary = f"{len(news)} headlines" if news else "no headlines"

    ctx = {"ta": ta, "fa": fa, "news": news, "provenance": provenance,
           "position": position_ctx, "deltas": deltas_ctx,
           "summaries": {"ta": ", ".join(ta_summary), "fa": ", ".join(fa_summary), "news": news_summary}}

    import json as _json
    # Choose prompt depending on data availability
    have_any_context = bool(ta) or bool(fa) or bool(news)
    if have_any_context:
        system = (
            "You are an expert trading assistant. Prioritize the provided Position + TA/FA/News context. "
            "Use position fields (entry/current, size, value, leverage, pnl, 1h/1d/1w deltas, hedge) together with TA/FA/News summaries. "
            "If any key fields are missing, reason conservatively using market structure and typical behavior; do not fabricate exact numbers. "
            "Decide KEEP/CLOSE/REDUCE and explain briefly (<=300 chars). Return JSON: {decision, reason, factors}."
        )
        user_payload = {
            "symbol": symbol,
            "side": side,
            "context": ctx,
            "return_schema": {
                "decision": "KEEP|CLOSE|REDUCE",
                "reason": "<=300 chars",
                "factors": {"ta": [], "fa": [], "news": [], "risk": []},
            },
        }
    else:
        system = (
            "You are an expert trading assistant. No external context could be fetched. Perform deep research using your knowledge and typical market behavior. "
            "State uncertainties clearly; avoid fabricating precise values. Return JSON: {decision, reason, factors}."
        )
        user_payload = {
            "symbol": symbol,
            "side": side,
            "context": {},
            "return_schema": {
                "decision": "KEEP|CLOSE|REDUCE",
                "reason": "<=300 chars",
                "factors": {"ta": [], "fa": [], "news": [], "risk": []},
            },
        }

    llm = get_llm_client_for(provider) or get_llm_client()
    if not llm:
        # fallback heuristic if no LLM configured, but still expose prompt when debug=true
        pnl_bias = "KEEP"
        reason = "LLM not configured; heuristic fallback using available context"
        resp = {"status": "success", "data": {"decision": pnl_bias, "reason": reason, "factors": {}, "context": ctx, "provenance": provenance}}
        if debug:
            resp["prompt"] = {"system": system, "user": user_payload}
        return resp

    try:
        user_str = _json.dumps(user_payload)
        # Try preferred provider, then any configured fallbacks to mitigate 429s
        last_err: Optional[str] = None
        for client in ([llm] + [c for c in get_llm_clients() if c is not llm]):
            try:
                content = await client.chat_complete(system, user_str)
                break
            except Exception as e:
                last_err = str(e)
                content = ""
                continue
        if not content:
            raise RuntimeError(last_err or "empty LLM response")
        try:
            parsed = _json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("non-dict json")
        except Exception:
            parsed = {"decision": "KEEP", "reason": content[:300], "factors": {}}
        parsed["context"] = {"ta": ta, "fa": fa, "news": news}
        parsed["provenance"] = provenance
        resp = {"status": "success", "data": parsed}
        if debug:
            resp["prompt"] = {"system": system, "user": user_payload}
        _DECISION_CACHE[cache_key] = {"_ts": now, "data": parsed}
        # Persist to DB
        try:
            import json as _json
            db = SessionLocal()
            row = db_models.DecisionCache(
                symbol=symbol,
                side=side,
                decision=str(parsed.get("decision") or ""),
                reason=str(parsed.get("reason") or ""),
                factors_json=_json.dumps(parsed.get("factors") or {}),
                provenance_json=_json.dumps(parsed.get("provenance") or {}),
                context_json=_json.dumps(parsed.get("context") or {}),
            )
            db.add(row)
            db.commit()
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
        return resp
    except Exception as e:
        # As a last resort, never 500 – return minimal decision
        fallback = {"decision": "KEEP", "reason": f"Fallback due to error: {str(e)[:180]}", "factors": {}, "context": ctx, "provenance": provenance}
        _DECISION_CACHE[cache_key] = {"_ts": now, "data": fallback}
        # Persist fallback as well for visibility
        try:
            import json as _json
            db = SessionLocal()
            row = db_models.DecisionCache(
                symbol=symbol,
                side=side,
                decision=str(fallback.get("decision") or ""),
                reason=str(fallback.get("reason") or ""),
                factors_json=_json.dumps(fallback.get("factors") or {}),
                provenance_json=_json.dumps(fallback.get("provenance") or {}),
                context_json=_json.dumps(fallback.get("context") or {}),
            )
            db.add(row)
            db.commit()
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
        return {"status": "success", "data": fallback}


@router.post("/research/decide/batch")
async def research_decide_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Batch decisions for multiple positions to reduce API calls and tokens.

    Request body: { positions: [ {symbol, side}, ... ], force_refresh?: bool }
    Response: { results: [ {symbol, side, decision, reason, factors, context, provenance}, ... ] }
    """
    positions: List[Dict[str, str]] = payload.get("positions", [])
    force_refresh: bool = bool(payload.get("force_refresh", False))
    recent_only_minutes: Optional[int] = payload.get("recent_only_minutes")
    provider: Optional[str] = payload.get("provider")
    now = time.time()
    out: List[Dict[str, Any]] = []
    for p in positions:
        sym = p.get("symbol"); sd = p.get("side")
        if not sym or not sd:
            continue
        if not force_refresh:
            ck = f"{sym}|{sd}"
            c = _DECISION_CACHE.get(ck)
            if c and (time.time() - c.get("_ts", 0)) < _DECISION_TTL_SECONDS:
                out.append({"symbol": sym, "side": sd, **c["data"]})
                continue
            # Try DB last decision within recent_only_minutes if provided
            if recent_only_minutes:
                try:
                    from datetime import datetime, timedelta
                    db = SessionLocal()
                    cutoff = datetime.utcnow() - timedelta(minutes=int(recent_only_minutes))
                    q = db.query(db_models.DecisionCache).filter(
                        db_models.DecisionCache.symbol == sym,
                        db_models.DecisionCache.side == sd,
                        db_models.DecisionCache.created_at >= cutoff,
                    ).order_by(db_models.DecisionCache.created_at.desc()).first()
                    if q:
                        import json as _json
                        data = {
                            "decision": q.decision,
                            "reason": q.reason,
                            "factors": (_json.loads(q.factors_json or "{}")),
                            "provenance": (_json.loads(q.provenance_json or "{}")),
                            "context": (_json.loads(q.context_json or "{}")),
                            "received_at": q.created_at.isoformat(),
                        }
                        out.append({"symbol": sym, "side": sd, **data})
                        db.close()
                        continue
                    db.close()
                except Exception:
                    pass
        try:
            res = await research_decide(symbol=sym, side=sd, provider=provider)  # will fill cache
            data = res.get("data") or {}
            out.append({"symbol": sym, "side": sd, **data})
        except Exception as e:
            out.append({"symbol": sym, "side": sd, "decision": "KEEP", "reason": f"Error: {str(e)[:120]}", "factors": {}, "context": {}, "provenance": {}})
    return {"status": "success", "results": out}


@router.get("/research/history")
async def research_history(
    symbol: str = Query(...),
    side: str = Query(...),
    limit: int = Query(10, ge=1, le=100)
) -> Dict[str, Any]:
    """Return recent decision history for a symbol/side from the DB cache."""
    try:
        db_models.Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    try:
        db = SessionLocal()
        q = (
            db.query(db_models.DecisionCache)
            .filter(db_models.DecisionCache.symbol == symbol, db_models.DecisionCache.side == side)
            .order_by(db_models.DecisionCache.created_at.desc())
            .limit(limit)
        )
        rows = q.all()
        import json as _json
        results = []
        for r in rows:
            try:
                results.append({
                    "symbol": r.symbol,
                    "side": r.side,
                    "decision": r.decision,
                    "reason": r.reason,
                    "factors": (_json.loads(r.factors_json or "{}")),
                    "provenance": (_json.loads(r.provenance_json or "{}")),
                    "context": (_json.loads(r.context_json or "{}")),
                    "created_at": r.created_at.isoformat(),
                })
            except Exception:
                continue
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        try:
            db.close()
        except Exception:
            pass


