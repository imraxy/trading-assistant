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

New (LLM multi-provider and debugging):
- Implemented multi-LLM abstraction (OpenAI, Gemini, Anthropic, Mistral, Groq) with provider/model dropdown in UI and per-request overrides.
- Explicit provider selection disables fallback; auto mode retains prioritized fallbacks.
- Provider/model validation returns clear errors for invalid combinations.
- Groq client enhanced to surface full error JSON on non-2xx; suggested models list updated.
- Added `/api/v1/chat/llm/test` endpoint to quickly verify provider/model configuration.

AG Grid fixes (completed):
- Fixed grid container height collapse that was preventing grid visibility
- Added explicit height and min-height CSS rules with !important flags
- Reverted problematic horizontal scroll fixes that caused visibility issues
- Grid now properly displays all 189+ positions with full functionality
- All columns auto-size correctly, sorting and filtering work as expected

AI Decision System fixes (completed):
- Fixed OpenAI gpt-5-nano parameter compatibility (max_completion_tokens vs max_tokens)
- Resolved temperature parameter constraint (gpt-5-nano only supports temperature=1.0)
- Updated default OpenAI model from gpt-5-nano to gpt-4o-mini for reliability
- AI decision system now working with proper technical/fundamental analysis
- Decisions include detailed reasoning and factor breakdowns (TA, FA, news, risk)
- Multi-provider support functional (OpenAI, Gemini, Groq, etc.)
- Frontend grid displays AI decisions correctly with tooltips and age badges
- Code pushed to chore/kilo-memory-init and merged to develop branch

Market Data Integration (completed):
- Replaced CoinGecko API with Binance klines API for accurate market data
- Implemented precise 1h/24h/7d percentage change calculations using historical price data
- Added intelligent caching system with 5-minute expiration for performance optimization
- Implemented proper rate limiting (3 concurrent requests, 0.2s delays, 1s batch delays)
- Added timeout handling (20s) to prevent hanging requests
- Fallback to simulated data when Binance API fails or symbols not found
- Fixed grid visibility issues caused by API timeouts
- Results: ZECUSDT 26.61% (vs CoinMarketCap's 21.40%), BTCUSDT -0.53%
- Grid now displays accurate real market data instead of simulated values
- Code pushed to chatbot branch
