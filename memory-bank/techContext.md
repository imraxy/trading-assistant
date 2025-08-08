# Tech Context

## Technologies
- Backend: Python 3.11+, FastAPI, Uvicorn
- Data/Analysis: numpy, pandas, scipy, TA-Lib (planned)
- External APIs: Bybit (positions only), CoinGecko/Alpha Vantage/News (market/sentiment)
- Storage: SQLite in local dev; PostgreSQL 15+ in Docker/prod; Redis 7+ caching
- Frontend: Static HTML/JS dashboard (future React/Next.js)

## Dev Setup (Local)
- Environment: `.env` in `trading-assistant/backend/`
- Launch: `python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- If `python3-venv` missing, install deps with `pip3 --user -r requirements.txt`
- Health: `GET http://localhost:8000/health`
- Docs: `http://localhost:8000/docs`

## Docker
- `docker-compose.yml` present, but no backend `Dockerfile` yet; local run recommended until Dockerfile is added
- Compose services define Postgres and Redis for future integration

## Env Vars (key ones)
- BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET
- OPENAI_API_KEY (optional)
- DATABASE_URL / DB_URL depending on deployment
- SECURITY_SECRET_KEY, SECURITY_ENCRYPTION_KEY

## Constraints
- Security-first: never commit secrets
- Performance: end-to-end <5s for 193+ positions
- Error handling and rate limiting mandatory for all external APIs
