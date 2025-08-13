# Architecture

- High-level diagram: see `memory-bank/systemPatterns.md` for current block diagram.
- Modules & boundaries: frontend (dashboard UI), backend (FastAPI services), analysis engine (TA/FA), notification service (planned).
- Data models & ownership: position snapshots stored by backend; analysis aggregates computed on demand; frontend displays via AG Grid.
- Cross-cutting concerns: auth (API keys via env), logging (structured logs), config (env + settings), feature flags (TBD).
- External integrations and failure modes: Bybit v5 (rate limits, signature errors), CoinGecko/Alpha Vantage/CryptoPanic (HTTP failures, backoff), Playwright (browser availability).


