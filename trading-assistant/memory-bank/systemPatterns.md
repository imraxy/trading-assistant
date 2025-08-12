# System Patterns

- Backend: FastAPI + httpx; services layer (`bybit_service`, `portfolio_service`); SQLite for snapshots via SQLAlchemy.
- Frontend: Static HTML + Alpine.js; AG Grid Community for the positions table.
- Debugging: Playwright-based snapshot service with latest snapshot retrieval.
- Security: Env-based config via `app.core.config.get_settings()`.
