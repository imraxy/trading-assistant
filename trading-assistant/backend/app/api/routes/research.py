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
from ...services.llm_provider import get_llm_client


router = APIRouter()


async def fetch_binance_ohlc(symbol: str, interval: str = "1h", limit: int = 200) -> List[float]:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1000)}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    # close prices are at index 4
    closes = [float(k[4]) for k in data]
    return closes


async def fetch_coingecko_market(symbol: str) -> Dict[str, Any]:
    try:
        sym = symbol.replace("USDT", "").lower()
        async with httpx.AsyncClient(timeout=15.0) as client:
            lst = await client.get("https://api.coingecko.com/api/v3/coins/list")
        lst.raise_for_status()
        coins = lst.json()
        match = next((c for c in coins if c.get("symbol") == sym), None)
        if not match:
            return {}
        coin_id = match.get("id")
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


async def fetch_news(symbol: str) -> List[Dict[str, Any]]:
    token = os.getenv("CRYPTOPANIC_TOKEN") or os.getenv("CRYPTOPANIC_API_TOKEN")
    if not token:
        return []
    cur = symbol.replace("USDT", "").upper()
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
async def research_decide(symbol: str = Query(...), side: str = Query(...)) -> Dict[str, Any]:
    """Auto-research pipeline: TA (Binance OHLC), FA (CoinGecko), News (CryptoPanic), then LLM decision."""
    try:
        closes = await fetch_binance_ohlc(symbol, interval="1h", limit=300)
        ta: Dict[str, Any] = {}
        if closes:
            ta_rsi = rsi_calc(closes, 14)
            ta["rsi"] = ta_rsi[-1] if ta_rsi else None
            ta["ema50"] = ema_calc(closes, 50)[-1] if len(closes) >= 50 else None
            ta["ema200"] = ema_calc(closes, 200)[-1] if len(closes) >= 200 else None
            sr = support_resistance(closes, lookback=100)
            ta["support_levels"] = [sr.get("support")]
            ta["resistance_levels"] = [sr.get("resistance")]
            ta.update(compute_macd(closes))

        fa = await fetch_coingecko_market(symbol)
        news = await fetch_news(symbol)

        ctx = {
            "ta": ta,
            "fa": fa,
            "news": news,
        }

        llm = get_llm_client()
        if not llm:
            # fallback heuristic
            pnl_bias = "KEEP"
            reason = "No LLM configured; heuristic fallback"
            return {"status": "success", "data": {"decision": pnl_bias, "reason": reason, "context": ctx}}

        system = (
            "You are an expert multi-asset trading assistant. Synthesize the provided TA/FA/News context to produce a clear action."
            " Respond with compact JSON: {decision, reason, factors}. decision in [KEEP,CLOSE,REDUCE]."
        )
        user = {
            "symbol": symbol,
            "side": side,
            "context": ctx,
            "return_schema": {
                "decision": "KEEP|CLOSE|REDUCE",
                "reason": "<=300 chars",
                "factors": {"ta": [], "fa": [], "news": [], "risk": []},
            },
        }
        content = await llm.chat_complete(system, f"Decide for: {user}")
        import json as _json
        try:
            parsed = _json.loads(content)
        except Exception:
            parsed = {"decision": "KEEP", "reason": content[:300], "factors": {}}
        parsed["context"] = ctx
        return {"status": "success", "data": parsed}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


