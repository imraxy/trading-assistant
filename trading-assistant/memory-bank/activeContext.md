# Active Context

- Bybit positions integration: mainnet only, v5 API, pagination across linear USDT/USDC and inverse.
- Value fix: backend now prefers Bybit `positionValue` when present; fallback to `size * markPrice`.
- Frontend: AG Grid Community with visible `Symbol` column; default sort Symbol then Side; USD formatting; full-width grid; row tint by side; dark mode toggle (global); Decision column powered by LLM endpoint with tooltip reason; correlations section removed for now.
- Snapshot debugging: endpoints to capture and fetch latest screenshot and logs.

Next steps:
- Verify USD values match user samples (e.g., BABYDOGE, MOG). If still off, incorporate contract size/multiplier per category.
- TA/FA/News integration now live via `/api/v1/research/decide` with Binance→CoinGecko OHLC fallback, CoinGecko market data, CryptoPanic news; provenance returned. Per-row and batch endpoints cache to memory and persist to DB (`decision_cache`).
- Frontend: Decisions no longer auto-run; added Decisions On/Off toggle, per-row Refresh in Decision drawer, age badge in grid, tooltips show received time; dark-mode button contrast improved.
- Deltas (1h/1d/1w): backend now selects earliest snapshot at/after window start with fallback to closest-before; oriented by side.
- Research improvements: symbol normalization strips quantity prefixes (e.g., `1000PEPEUSDT`→`PEPEUSDT`), and adds CoinGecko market_chart fallback for TA when Binance lacks pair.
- Planned: add `SymbolResolver` (Bybit→Binance/Kraken/CoinGecko id) with DB cache; `research_snapshots` table; completeness flags per category; background prefetch; UI pills for TA/FA/News status; decision scoring/confidence.
- Ensure stable backend startup: scripts added (`start_backend.sh`, `stop_backend.sh`, `status.sh`, logs tail). Venv bootstrap fixed when pip missing; SQLAlchemy added to requirements.
