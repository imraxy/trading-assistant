# Project Overview

Mission: Real-time AI-powered trading assistant for Bybit futures with multi-source analysis.

Tech stack: Frontend (HTML/JS + Alpine.js + AG Grid), Backend (FastAPI Python), DB (SQLite dev, PostgreSQL recommended), CI/CD (GitHub Actions TBD), Cloud (TBD).

Key packages/services: Bybit v5, Playwright, SQLAlchemy, Redis (planned), TA-Lib, CoinGecko, Alpha Vantage, CryptoPanic.

Running locally:
- Backend: from `backend/` run `uvicorn app.main:app --reload`
- Frontend: open `frontend/comprehensive-portfolio-dashboard.html`

Environments: dev (local), prod (TBD).

Non-goals: Paid data providers; rewriting working modules.


