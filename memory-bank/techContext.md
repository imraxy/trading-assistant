# Technical Context - AI Trading Assistant

## Technology Stack

### Frontend
- **Framework**: React with Next.js 14+
- **Styling**: Tailwind CSS for responsive design
- **Charts**: Lightweight charting library (Chart.js or TradingView widgets)
- **State Management**: React Query for API state, Zustand for local state
- **Real-time**: WebSocket connections for live updates

### Backend Services
- **API Aggregator**: Node.js with Express
- **Analysis Engine**: Python 3.11+ with FastAPI
- **WebSocket Manager**: Socket.io for real-time communication
- **Task Scheduler**: Node-cron or Python APScheduler for periodic analysis

### Analysis Libraries
- **Technical Analysis**: TA-Lib, pandas-ta, technicalindicators.js
- **Sentiment Analysis**: HuggingFace Transformers, VADER, TextBlob
- **AI Integration**: OpenAI GPT-4 API with function calling
- **Data Processing**: pandas, numpy for Python; lodash for JavaScript

### Database & Storage
- **Primary Database**: PostgreSQL for structured data
- **Cache Layer**: Redis for real-time data and session management
- **Alternative**: MongoDB for flexible document storage

### External APIs & Integrations
- **Bybit API**: REST + WebSocket for trading data
- **3Commas API**: Portfolio and bot management
- **TradingView**: Webhook receivers, Pine Script integration
- **Sentiment Sources**: Twitter API, Reddit API, CryptoPanic
- **Market Data**: CoinGecko, CoinMarketCap APIs

## Development Environment

### Prerequisites
```bash
# Node.js 18+ for backend services
# Python 3.11+ for analysis engine
# PostgreSQL 15+ or MongoDB 6+
# Redis 7+ for caching
```

### Environment Variables
```env
# API Keys (Read-only permissions recommended)
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
THREECOMMAS_API_KEY=your_3commas_key
OPENAI_API_KEY=your_openai_key

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/trading_db
REDIS_URL=redis://localhost:6379

# External Services
TELEGRAM_BOT_TOKEN=your_telegram_token
TWITTER_BEARER_TOKEN=your_twitter_token
```

### Project Structure
```
trading-assistant/
├── frontend/                 # Next.js dashboard
├── backend/
│   ├── api-aggregator/      # Node.js API service
│   ├── analysis-engine/     # Python analysis service
│   └── notification-service/ # Alert management
├── shared/
│   ├── types/              # TypeScript type definitions
│   └── utils/              # Common utilities
└── infrastructure/         # Docker, deployment configs
```

## Dependencies & Versions

### Python Dependencies
```
fastapi>=0.104.0
pandas>=2.1.0
numpy>=1.24.0
ta-lib>=0.4.26
transformers>=4.30.0
openai>=1.0.0
websockets>=11.0.0
redis>=4.6.0
psycopg2-binary>=2.9.0
```

### Node.js Dependencies
```json
{
  "express": "^4.18.0",
  "socket.io": "^4.7.0",
  "axios": "^1.5.0",
  "ws": "^8.14.0",
  "node-cron": "^3.0.0",
  "redis": "^4.6.0"
}
```

### Frontend Dependencies
```json
{
  "next": "^14.0.0",
  "react": "^18.2.0",
  "tailwindcss": "^3.3.0",
  "zustand": "^4.4.0",
  "@tanstack/react-query": "^4.35.0"
}
```

## Performance Considerations

### Scalability
- Stateless services for horizontal scaling
- Redis caching for frequently accessed data
- Database indexing on symbol, timestamp columns
- Rate limiting for external API calls

### Real-time Requirements
- WebSocket connections for sub-second updates
- Efficient data structures for position tracking
- Optimized SQL queries with proper indexing
- Memory-efficient indicator calculations

### Security & Compliance
- API key encryption at rest
- HTTPS/WSS only for all communications
- Input validation and sanitization
- Rate limiting and DDoS protection

## Development Tools
- **Code Quality**: ESLint, Prettier, Black (Python)
- **Testing**: Jest (Node.js), pytest (Python), Cypress (E2E)
- **API Documentation**: Swagger/OpenAPI
- **Monitoring**: Application logs, error tracking
- **CI/CD**: GitHub Actions or similar 