# Progress

- Fixed AG Grid to show visible Symbol and removed enterprise-only grouping; default sort by Symbol then Side.
- Implemented backend fix: use Bybit `positionValue` for `position_value` with fallback to `size * markPrice`.
- Snapshot debugging endpoints live; frontend buttons wired.
- Migrated AG Grid to Theming API (Quartz), full-width grid, column auto-size to content, row highlight by side, dark mode toggle (global styles applied).
- Added Decision column and LLM endpoints: `/api/v1/chat/decide` (fallback) and `/api/v1/research/decide` (primary). Research endpoint fetches TA (Binance with CoinGecko fallback), FA (CoinGecko), News (CryptoPanic), returns provenance and persists to DB.
- Fixed backend reload crash by cleaning exception handlers in `chat.py`. Stabilized port 8000 by killing lingering processes before restart.

Pending:
- Validate value correctness vs Bybit UI for select symbols; adjust for inverse multiplier if needed.
- Implement `SymbolResolver`, `research_snapshots`, completeness flags, background prefetch, UI source-status pills, decision scoring/confidence.
- Chatbot to query local snapshots and research history; add per-row decision history in drawer using `/api/v1/research/history`.
