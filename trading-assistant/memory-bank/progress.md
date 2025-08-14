# Progress

- Fixed AG Grid to show visible Symbol and removed enterprise-only grouping; default sort by Symbol then Side.
- Implemented backend fix: use Bybit `positionValue` for `position_value` with fallback to `size * markPrice`.
- Snapshot debugging endpoints live; frontend buttons wired.
- Migrated AG Grid to Theming API (Quartz), full-width grid, column auto-size to content, row highlight by side, dark mode toggle (global styles applied).
- Added Decision column and `/api/v1/chat/decide` endpoint; decisions surfaced with hover tooltip reasons.
- Fixed backend reload crash by cleaning exception handlers in `chat.py`. Stabilized port 8000 by killing lingering processes before restart.

Pending:
- Validate value correctness vs Bybit UI for select symbols; adjust for inverse multiplier if needed.
- TA/FA integration, risk engine, chatbot, refresh cadence.
