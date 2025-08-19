"""
Chat API Routes
Context-aware chatbot that can answer questions about current positions and analysis.

If OPENAI_API_KEY is set in environment, uses OpenAI; otherwise returns
deterministic answers derived from portfolio and positions data.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging

from ...services.bybit_service import bybit_service
from ...services.portfolio_service import portfolio_service
from ...services.llm_provider import get_llm_client, get_llm_client_for, available_providers

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    provider: Optional[str] = None


class DecisionRequest(BaseModel):
    symbol: str
    side: str
    context: Dict[str, Any]
    provider: Optional[str] = None


@router.post("/chat/ask")
async def ask_chatbot(payload: ChatRequest) -> Dict[str, Any]:
    """Answer portfolio questions using current positions and analytics.

    Falls back to heuristic rules when LLM key is not configured.
    """
    try:
        question = (payload.question or "").strip()
        # Load data
        open_positions_result = await bybit_service.get_positions()
        if open_positions_result.get("status") != "success":
            raise HTTPException(status_code=500, detail="Unable to load positions")

        positions: List[Dict[str, Any]] = open_positions_result.get("positions", [])
        analysis_result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=True, validate_results=False
        )
        if analysis_result.get("status") != "success":
            raise HTTPException(status_code=500, detail="Unable to analyze portfolio")

        portfolio_summary = analysis_result.get("portfolio_summary", {})
        analytics = analysis_result.get("analytics", {})

        # If OpenAI available, build a concise context and ask
        llm = get_llm_client_for(payload.provider) or get_llm_client()
        if llm:
            try:
                # Compact context to keep token usage low
                top_positions = sorted(
                    positions,
                    key=lambda p: abs(p.get("unrealized_pnl", 0)),
                    reverse=True,
                )[:10]
                context = {
                    "summary": {
                        "portfolio_value": portfolio_summary.get("portfolio_value", 0),
                        "unrealized_pnl": portfolio_summary.get("total_unrealized_pnl", 0),
                        "active_positions": portfolio_summary.get("active_positions", 0),
                        "avg_leverage": portfolio_summary.get("avg_leverage", 0),
                    },
                    "top_positions": top_positions,
                    "risk_metrics": analytics.get("risk_metrics", {}),
                }
                system = (
                    "You are a trading assistant. Answer briefly with actionable insights "
                    "based on the provided positions and analytics. Recommend CLOSE/KEEP/REDUCE with reason."
                )
                user = f"Question: {question}\nContext: {context}"
                answer = await llm.chat_complete(system, user)
                if answer:
                    return {"status": "success", "answer": answer}
            except Exception as e:
                logger.warning(f"OpenAI call failed, using heuristic answer: {e}")

        # Heuristic answers
        q = question.lower()
        def fmt(v: float) -> str:
            return f"${v:,.2f}"

        if "most at risk" in q or "risk" in q:
            # Highest leverage and highest abs PnL%
            risky = sorted(
                positions,
                key=lambda p: (p.get("leverage", 1), abs(p.get("pnl_percentage", 0))),
                reverse=True,
            )[:5]
            items = [
                f"{p.get('symbol')} {int(p.get('leverage',1))}x PnL {p.get('pnl_percentage',0):.2f}%"
                for p in risky
            ]
            return {"status": "success", "answer": "Top risk: " + "; ".join(items)}

        if "profitable" in q or "top 3" in q:
            winners = sorted(positions, key=lambda p: p.get("unrealized_pnl", 0), reverse=True)[:3]
            items = [
                f"{p.get('symbol')} {fmt(p.get('unrealized_pnl',0))} ({p.get('pnl_percentage',0):.2f}%)"
                for p in winners
            ]
            return {"status": "success", "answer": "Top winners: " + ", ".join(items)}

        if "should i close" in q or ("close" in q and "?" in q):
            # Simple rule: if pnl% < -10 or leverage > 20 with negative pnl, suggest close
            tokens = [t for t in q.replace("?", "").split() if t.isalpha()]
            sym_hint = tokens[-1].upper() + "USDT" if tokens else None
            candidates = [p for p in positions if sym_hint and sym_hint in p.get("symbol", "")]
            if candidates:
                p = max(candidates, key=lambda x: abs(x.get("pnl_percentage", 0)))
                pnl = p.get("pnl_percentage", 0)
                lev = p.get("leverage", 1)
                if pnl < -10 or (pnl < 0 and lev >= 20):
                    return {"status": "success", "answer": f"Recommend CLOSE {p.get('symbol')}: PnL {pnl:.2f}% at {int(lev)}x"}
                else:
                    return {"status": "success", "answer": f"KEEP {p.get('symbol')} for now: PnL {pnl:.2f}%, {int(lev)}x"}

        # Default brief summary
        ans = (
            f"Active positions: {portfolio_summary.get('active_positions',0)}, "
            f"Value {portfolio_summary.get('portfolio_value',0):.2f}, "
            f"Unrealized PnL {portfolio_summary.get('total_unrealized_pnl',0):.2f}. "
            f"Ask about 'most at risk', 'top 3 profitable', or 'Should I close BTC short?'"
        )
        return {"status": "success", "answer": ans}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/decide")
async def decide_with_llm(payload: DecisionRequest) -> Dict[str, Any]:
    """Ask LLM to decide KEEP/CLOSE for a specific position using rich context.

    Considers TA deltas, leverage, position value, potential hedges, and
    placeholder support/resistance levels. Returns concise decision and reason.
    """
    try:
        symbol = payload.symbol
        side = payload.side
        ctx = payload.context or {}

        llm = get_llm_client_for(payload.provider) or get_llm_client()
        # Prefer configured LLM; if not present or fails, return heuristic decision
        if llm:
            try:
                system = (
                    "You are an expert multi-asset trading assistant."
                    " Use the structured context to perform disciplined analysis and return a concise JSON verdict."
                    " Stay within the provided data; do not fabricate unknown values."
                    " Synthesize Technical (TA), Fundamental (FA), and News/Sentiment if present."
                    " Prioritize risk controls and practical execution."
                )

                # Ensure TA/FA/News keys exist so the model can consume them uniformly
                enriched_ctx = {
                    **ctx,
                    "ta": ctx.get("ta") or {
                        "rsi": None,
                        "macd": None,
                        "ema": None,
                        "sma": None,
                        "support_levels": ctx.get("support"),
                        "resistance_levels": ctx.get("resistance"),
                    },
                    "fa": ctx.get("fa") or {"market_cap": None, "volatility": None, "funding_rate": None},
                    "news": ctx.get("news") or [],  # [{headline, sentiment, source, time}]
                }

                # Strict response contract so the UI can display full reasoning
                response_contract = {
                    "decision": "KEEP | CLOSE | REDUCE",
                    "reason": "<=300 chars executive summary",
                    "factors": {
                        "ta": "short list of TA signals relied upon",
                        "fa": "short list of FA items/funding considered",
                        "news": "short list of news/sentiment items if any",
                        "risk": "key risks (e.g., leverage, drawdown, correlation)",
                    }
                }

                user = {
                    "symbol": symbol,
                    "side": side,
                    "context": enriched_ctx,
                    "return_schema": response_contract,
                }
                content = await llm.chat_complete(system, f"Decide for: {user}")
                # Best-effort JSON extraction
                import json as _json
                try:
                    parsed = _json.loads(content)
                except Exception:
                    parsed = {"decision": "KEEP", "reason": content[:300], "factors": {}}
                return {"status": "success", "data": parsed}
            except Exception as e:
                logger.warning(f"LLM decision failed, using heuristic: {e}")
        # Heuristic fallback
        pnl_pct = float(ctx.get("pnlPct", 0) or 0)
        lev = float(ctx.get("lev", 1) or 1)
        d1h = float(ctx.get("d1h", 0) or 0)
        hedge = bool(ctx.get("hasHedge", False))
        decision = "KEEP"
        reason = "Stable conditions"
        if pnl_pct < -12 or (pnl_pct < 0 and lev >= 20 and d1h < -2):
            decision = "CLOSE"
            reason = "Drawdown with high leverage"
        elif pnl_pct > 25 and d1h > 3 and not hedge:
            decision = "REDUCE"
            reason = "Lock partial profits after strong move"
        return {"status": "success", "data": {"decision": decision, "reason": reason}}
    except Exception as e:
        logger.error(f"Decision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


