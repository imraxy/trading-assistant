# Progress

- Fixed AG Grid to show visible Symbol and removed enterprise-only grouping; default sort by Symbol then Side.
- Implemented backend fix: use Bybit `positionValue` for `position_value` with fallback to `size * markPrice`.
- Snapshot debugging endpoints live; frontend buttons wired.

Pending:
- Validate value correctness vs Bybit UI for select symbols; adjust for inverse multiplier if needed.
- TA/FA integration, risk engine, chatbot, refresh cadence.
