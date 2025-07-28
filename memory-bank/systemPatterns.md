# System Patterns - AI Trading Assistant

## System Architecture

### High-Level Design
```
[Frontend Dashboard (React/Next.js)]
       |
       v
[Backend API Aggregator (Node.js)]
       |       |       |
       |       |       +--> [TradingView Webhook Listener]
       |       +--> [3Commas API Client]
       +--> [Bybit REST & WebSocket Client]
               |
               v
[Analysis Engine (Python)]
   |-- Technical Analysis Module
   |-- Sentiment Analysis Module
   |-- Fundamental Analysis Module
   |-- AI Decision Engine (GPT-4)
               |
               v
[Data Layer (PostgreSQL/MongoDB)]
   |-- Position Cache
   |-- Analysis History
   |-- User Preferences
               |
               v
[Notification System]
   |-- Telegram Bot
   |-- Discord Bot
   |-- Email Alerts
```

## Key Design Patterns

### 1. Microservices Architecture
- **API Aggregator**: Centralized data collection from all sources
- **Analysis Engine**: Isolated Python service for calculations
- **Notification Service**: Separate alert management
- **WebSocket Manager**: Real-time data streaming

### 2. Data Flow Pattern
```
Data Sources → API Aggregator → Analysis Engine → Decision Output → Notifications
     ↓              ↓               ↓              ↓             ↓
  Raw Data    →  Normalized   →   Analyzed    →  Actionable  → User Alert
```

### 3. Modular Analysis Pipeline
Each position goes through:
1. **Technical Analysis Layer**: TA-Lib indicators
2. **Sentiment Analysis Layer**: NLP processing
3. **Fundamental Analysis Layer**: Market data correlation
4. **AI Decision Layer**: GPT-4 synthesis and reasoning

### 4. Real-time Update Pattern
- WebSocket connections for live price feeds
- Scheduled analysis runs (10-60 second intervals)
- Event-driven updates for position changes
- Cached results with TTL for performance

## Component Relationships

### Data Sources (Input Layer)
- Bybit API: Positions, balances, market data
- 3Commas API: Bot status, smart trades
- TradingView: Custom signals, alerts
- Sentiment APIs: News, social media data

### Processing Layer
- **Position Tracker**: Monitors all open positions
- **Indicator Calculator**: Computes technical indicators
- **Sentiment Scorer**: Processes news/social sentiment
- **Risk Assessor**: Evaluates position risk levels

### Decision Layer
- **AI Analyzer**: GPT-4 powered decision making
- **Rule Engine**: Systematic trading rules
- **Risk Manager**: Position sizing and stop-loss logic

### Output Layer
- **Dashboard**: Visual position overview
- **Alert System**: Real-time notifications
- **API**: Programmatic access to decisions

## Security Patterns

### API Key Management
- Environment variables for sensitive data
- Token vault for production deployment
- Read-only API permissions where possible
- Encrypted storage for user credentials

### Data Protection
- No persistent storage of API keys
- Secure transmission (HTTPS/WSS only)
- Rate limiting on all external APIs
- User data encryption at rest 