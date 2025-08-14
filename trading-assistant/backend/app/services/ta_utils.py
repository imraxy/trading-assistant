from __future__ import annotations

from typing import List, Dict, Any


def ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    ema_vals: List[float] = []
    ema_prev: float | None = None
    for v in values:
        ema_prev = v if ema_prev is None else (v - ema_prev) * k + ema_prev
        ema_vals.append(ema_prev)
    return ema_vals


def rsi(values: List[float], period: int = 14) -> List[float]:
    if len(values) < period + 1:
        return []
    gains: List[float] = []
    losses: List[float] = []
    rsis: List[float] = []
    # initial averages
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = (avg_gain / avg_loss) if avg_loss != 0 else float("inf")
    rsis.append(100 - (100 / (1 + rs)))
    # subsequent
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = (avg_gain / avg_loss) if avg_loss != 0 else float("inf")
        rsis.append(100 - (100 / (1 + rs)))
    return rsis


def support_resistance(values: List[float], lookback: int = 50) -> Dict[str, Any]:
    if not values:
        return {"support": None, "resistance": None}
    window = values[-lookback:] if len(values) > lookback else values
    return {"support": min(window), "resistance": max(window)}


