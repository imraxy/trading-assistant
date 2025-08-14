# System Patterns

- Backend: FastAPI + httpx; services layer (`bybit_service`, `portfolio_service`); SQLite for snapshots via SQLAlchemy.
- Frontend: Static HTML + Alpine.js; AG Grid Community for the positions table.
 - Frontend: Static HTML + Alpine.js; AG Grid Community (Quartz/Quartz Dark) with postSortRows for side adjacency, column auto-size, global dark mode toggle.
- Debugging: Playwright-based snapshot service with latest snapshot retrieval.
 - Debugging: Playwright-based snapshot service with latest snapshot retrieval; Browser snapshot/log endpoints surfaced in UI.
- Security: Env-based config via `app.core.config.get_settings()`.
