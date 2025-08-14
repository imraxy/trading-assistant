# Tech Context

- Python 3.11+, FastAPI, httpx, SQLAlchemy (SQLite for snapshots), Playwright for snapshots.
 - Frontend uses Tailwind CDN, Alpine.js, AG Grid Community UMD; theme: Quartz/Quartz Dark with postSortRows.
 - Bybit v5 REST APIs for positions and closed PnL. Mainnet only.
 - Chat/Decision: `/api/v1/chat/ask` and `/api/v1/chat/decide` use OpenAI by default via `OPENAI_API_KEY` and `OPENAI_MODEL`, with heuristic fallback. Gemini can be introduced via config later.
