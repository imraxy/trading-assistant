# Active Context

## Current Focus (Week 2)
- Enhanced technical indicators and risk assessment
- Stabilize local dev flow; prep for Dockerfile and compose-based runs

## Recent Changes (2025-08-08)
- Backend launched locally at `http://localhost:8000`; health OK
- Using local Python user-site installs due to missing `python3-venv`
- `.env` present at `trading-assistant/backend/.env`
- Playwright installed as package; browsers install pending if browser automation is needed
- Compose file exists, but backend Dockerfile not found → run locally for now
- Database defaults to SQLite in dev (`Settings.DATABASE_URL`), Postgres via compose when Dockerfile is added

## Decisions
- Prefer non-Bybit sources for market/sentiment; Bybit only for open positions
- Local run with SQLite until Dockerfile is added; Postgres/Redis when containerized

## Next Steps
1. Add backend `Dockerfile` to enable compose flow (Postgres/Redis)
2. Implement TA-Lib indicators and multi-timeframe analysis
3. Add config/status endpoint improvements for clarity
4. Optional: `python -m playwright install` if browser automation needed on this host

## Risks/Considerations
- Ensure secrets only in `.env`; never logged
- Keep analysis latency under 5 seconds for full portfolio
