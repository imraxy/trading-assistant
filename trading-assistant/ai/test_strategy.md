# Test Strategy

- Pyramid: unit > integration > e2e
- What to test: technical indicator calculations, API client error handling, decision engine logic
- What not to test: trivial getters/setters, framework internals
- Fixtures/mocks: stub network calls; deterministic seeds for analysis
- CI gates: add coverage threshold later; ensure lints/tests pass before merge


