# Active Context

- Bybit positions integration: mainnet only, v5 API, pagination across linear USDT/USDC and inverse.
- Value fix: backend now prefers Bybit `positionValue` when present; fallback to `size * markPrice`.
- Frontend: AG Grid Community with visible `Symbol` column; default sort Symbol then Side; USD formatting; full-width grid; row tint by side; dark mode toggle (global); Decision column powered by LLM endpoint with tooltip reason; correlations section removed for now.
- Snapshot debugging: endpoints to capture and fetch latest screenshot and logs.

Next steps:
- Verify USD values match user samples (e.g., BABYDOGE, MOG). If still off, incorporate contract size/multiplier per category.
- Integrate TA/FA data sources and risk engine, then chatbot querying over local snapshots.
- Extend Decision endpoint to include real support/resistance levels and TA/FA inputs; allow switching to Gemini when configured.
- Ensure stable backend startup: avoid multiple uvicorn instances; free :8000 before launch.
