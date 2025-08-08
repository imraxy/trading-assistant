# Product Context

## Why This Exists
Managing 193+ crypto positions across volatile markets demands continuous monitoring, triage of risk, and quick, justifiable actions. Manual workflows are slow and error-prone.

## Problems Solved
- Fragmented data across APIs and sources
- Lack of consistent multi-timeframe technical context
- Reactive instead of proactive risk handling
- No unified, explainable decision output

## How It Should Work
- Polls/streams data, caches positions and market snapshots
- Runs multi-layer analysis and synthesizes a concise decision
- Exposes decisions via API, dashboard, and notifications

## User Experience Goals
- Single-pane portfolio overview with filters and drill-down
- Per-position cards: exact exits, TP/SL, risk level, reasoning
- Real-time feel (<5s), stable, and secure

## Decision Output Format
| Symbol | PnL | RSI | MACD | Sentiment | Risk | Suggestion | Reason |
|--------|-----|-----|------|-----------|------|------------|--------|
| BTCUSDT | +12% | 54 | Bullish | Neutral | Low | ✅ Hold | Trend aligned |
