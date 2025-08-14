# AI Trading Assistant

A standalone, real-time AI-powered trading assistant that integrates with Bybit, 3Commas, and TradingView to provide actionable trading recommendations based on technical analysis, sentiment analysis, and AI decision-making.

## 🚀 Features

- **Real-time Position Monitoring**: Track 193+ positions simultaneously
- **Multi-layered Analysis**: Technical indicators + Sentiment analysis + AI reasoning
- **Standalone Deployment**: No external dependencies, runs anywhere
- **Secure API Management**: Encrypted credential storage
- **Database-first Architecture**: Local analysis with historical data
- **Docker Ready**: Easy deployment with Docker containers

## 📋 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or use Docker)
- Docker & Docker Compose (optional but recommended)

### Option 1: Docker Deployment (Recommended)

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd trading-assistant
   cp env.example .env
   ```

2. **Configure environment variables**:
   Edit `.env` file with your API credentials:
   ```bash
   # Bybit API (get from https://testnet.bybit.com/app/user/api-management)
   BYBIT_API_KEY=your_bybit_api_key_here
   BYBIT_API_SECRET=your_bybit_api_secret_here
   
   # OpenAI API (get from https://platform.openai.com/api-keys)
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Verify setup**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/config
   ```

### Option 2: Local Development

1. **Setup Python environment**:
   ```bash
   cd trading-assistant/backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Setup PostgreSQL database**:
   ```bash
   # Create database
   createdb trading_assistant
   
   # Or use Docker for database only
   docker run -d --name postgres \
     -e POSTGRES_DB=trading_assistant \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=password \
     -p 5432:5432 postgres:15-alpine
   ```

3. **Configure environment**:
   ```bash
   cp ../env.example .env
   # Edit .env with your credentials
   ```

4. **Run the application**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

## 🔧 Configuration

### Environment Variables

Key configuration options:

| Variable | Description | Required |
|----------|-------------|----------|
| `BYBIT_API_KEY` | Bybit API key | Yes |
| `BYBIT_API_SECRET` | Bybit API secret | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `DB_URL` | PostgreSQL connection string | Yes |
| `SECURITY_SECRET_KEY` | JWT secret key | Yes |
| `SECURITY_ENCRYPTION_KEY` | API key encryption key | Recommended |

### API Credentials Setup

1. **Bybit API**:
   - Testnet: https://testnet.bybit.com/app/user/api-management
   - Mainnet: https://www.bybit.com/app/user/api-management
   - Permissions needed: Read-only (Account, Positions, Orders)

2. **OpenAI API**:
   - Get key from: https://platform.openai.com/api-keys
   - Recommended model: GPT-4

## 📊 API Endpoints

### Health & Status
- `GET /` - Basic info
- `GET /health` - Health check
- `GET /api/v1/config` - Configuration status

### Bybit Integration
- `GET /api/v1/bybit/test` - Test Bybit connection
- `GET /api/v1/positions` - Fetch positions from Bybit and store in DB
- `GET /api/v1/positions/db` - Get stored positions from database

### Interactive Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
│   Dashboard     │    │   API Server    │    │   Position Data │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   External APIs │
                    │   • Bybit       │
                    │   • 3Commas     │
                    │   • TradingView │
                    │   • OpenAI      │
                    └─────────────────┘
```

### Core Components

1. **API Aggregator**: Fetches data from multiple sources
2. **Database Layer**: Stores positions, market data, analysis results
3. **Analysis Engine**: Technical indicators + AI decision making
4. **Configuration System**: Flexible config (env vars + database + files)

## 🧪 Testing

### Test Bybit Connection
```bash
curl -X GET "http://localhost:8000/api/v1/bybit/test"
```

### Fetch Your Positions
```bash
curl -X GET "http://localhost:8000/api/v1/positions"
```

### Check Stored Data
```bash
curl -X GET "http://localhost:8000/api/v1/positions/db"
```

## 🔒 Security Features

- **Encrypted API Keys**: Sensitive credentials encrypted at rest
- **Read-only Permissions**: API keys only need read access
- **Environment Isolation**: Separate configs for dev/test/prod
- **Docker Security**: Non-root user, security scanning
- **Rate Limiting**: Built-in API rate limiting

## 📈 Roadmap

### Week 1 ✅
- [x] Project structure and database setup
- [x] Bybit API integration
- [x] Position monitoring
- [x] Docker deployment

### Week 2 (Current)
- [ ] Technical analysis engine (TA-Lib)
- [ ] Multiple timeframe analysis
- [ ] 3Commas API integration
- [ ] Advanced indicators

### Week 3-6
- [ ] Sentiment analysis
- [ ] AI decision engine (GPT-4)
- [ ] TradingView webhooks
- [ ] Frontend dashboard
- [ ] Notification system

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**:
   ```bash
   # Check if PostgreSQL is running
   docker ps | grep postgres
   
   # Check connection string in .env
   DB_URL=postgresql://postgres:password@localhost:5432/trading_assistant
   ```

2. **Bybit API Errors**:
   ```bash
   # Test connection
   curl http://localhost:8000/api/v1/bybit/test
   
   # Check API credentials and permissions
   ```

3. **TA-Lib Installation Issues**:
   ```bash
   # Use Docker (recommended) or install TA-Lib manually
   # See Dockerfile for installation steps
   ```

### Logs

```bash
# Docker logs
docker-compose logs backend

# Local development
tail -f logs/app.log
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk of loss. Always do your own research and never trade with money you cannot afford to lose.

## 📞 Support

- GitHub Issues: Report bugs and feature requests
- Documentation: Check `/docs` endpoint when running
- API Reference: `/docs` and `/redoc` endpoints 
 - Resources: see `docs/resources.md` for shared links