# Coding Standards

- Language/Framework conventions: follow FastAPI and Alpine.js idioms; Python 3.11+.
- Error handling patterns: fail fast; return clear errors; avoid bare excepts.
- Logging: use structured logs; levels: debug/info/warn/error.
- API/contract: versioned under `/api/v1`; validate inputs; no breaking changes without migration.
- Frontend: prefer pure functions; small components; avoid global mutable state.
- Backend: service layer for external APIs; repository/service patterns for DB.
- DB: migrations (TBD), indexing on symbol/timestamp; avoid N+1 queries.


