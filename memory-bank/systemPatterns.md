# System Patterns

## Architecture
- Microservices-oriented boundaries: API aggregator, analysis engine, notifications
- FastAPI backend (async); future separate services as scale demands
- Database-first: structured storage for positions/market data; Redis for caching

## Integration Patterns
- Bybit: REST for account/positions; WebSocket for prices (planned)
- Prefer specialized data providers (e.g., CoinGecko, Alpha Vantage) over Bybit for market data
- Rate limiting: batching, exponential backoff, circuit breaker

## Data Flow
Bybit API → Position Cache → Analysis Pipeline → AI Decision → User Alert

## Analysis Engine
- TA-Lib for RSI/MACD/EMA/Bollinger (Week 2+)
- Multi-timeframe (1m/5m/1h/4h/1d)
- Normalized indicator scales and risk scoring

## AI Decision Layer
- Compose Technical + Sentiment + Fundamentals
- Function-calling GPT models for structured outputs (future)

## Security
- Read-only API keys, env-based in dev, encrypted at rest in prod
- No secrets in logs; input validation on all endpoints

## Performance
- <5s latency target
- Redis caching; DB indexing by symbol,timestamp
- Connection pooling and efficient data structures

## Testing
- Unit: indicators, clients, decision logic
- Integration: end-to-end API and WebSocket (planned)
- Performance: latency and concurrency
