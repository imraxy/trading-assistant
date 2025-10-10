# System Patterns

- Backend: FastAPI + httpx; services layer (`bybit_service`, `portfolio_service`); SQLite for snapshots via SQLAlchemy.
- Frontend: Static HTML + Alpine.js; AG Grid Community for the positions table.
 - Frontend: Static HTML + Alpine.js; AG Grid Community (Quartz/Quartz Dark) with postSortRows for side adjacency, column auto-size, global dark mode toggle, explicit height/min-height CSS to prevent container collapse.
- Debugging: Playwright-based snapshot service with latest snapshot retrieval.
 - Debugging: Playwright-based snapshot service with latest snapshot retrieval; Browser snapshot/log endpoints surfaced in UI.
- Security: Env-based config via `app.core.config.get_settings()`.

LLM Abstraction & Patterns
- Centralized provider abstraction in `app/services/llm_provider.py` implements: OpenAI, Gemini, Anthropic, Mistral, Groq.
- Global throttling (semaphore), pacing, and exponential backoff with jitter across providers.
- Provider selection rules:
  - If a provider is explicitly requested in the API call, do not fall back to other providers on error.
  - In Auto mode, try preferred (via `AI_PROVIDER`) then fall back to other configured providers.
- Suggested models exposed via `/api/v1/config` and enforced by a lightweight `is_valid_model_for_provider` guard.
- Groq uses OpenAI-compatible API route and returns provider error JSON on non-2xx to aid diagnosis (e.g., model_not_found).

Market Data Integration Patterns
- Binance klines API integration in `app/api/routes/portfolio.py` for accurate market data
- Intelligent caching system with 5-minute expiration stored in `./data/market_data_cache.json`
- Rate limiting: 3 concurrent requests, 0.2s delays between requests, 1s delays between batches
- Timeout handling: 20-second timeout with asyncio.wait_for to prevent hanging
- Fallback strategy: Binance API → Cached data → Simulated data
- Data format: Maintains `symbol -> {Buy: data, Sell: data}` structure for frontend compatibility
- Error handling: Graceful degradation with logging and fallback to simulated data
