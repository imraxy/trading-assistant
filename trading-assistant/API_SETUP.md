# 🔑 API Setup Guide - Multi-Source Analysis

This guide helps you set up **free API keys** for the enhanced multi-source analysis system.

## 🚀 Quick Setup

### 1. **Copy Environment Template**
```bash
# Run the setup script
python setup_env.py

# OR manually copy the template
cp backend/env_template.txt backend/.env
```

### 2. **Get Free API Keys** (Optional but Recommended)

## 📊 Alpha Vantage - Technical Indicators

**🔗 Signup Link**: https://www.alphavantage.co/support/#api-key

**📋 What you get**:
- 500 API calls per day **FREE**
- Professional technical indicators (RSI, MACD, Bollinger Bands, Stochastic)
- Real-time and historical data

**⏱️ Signup Time**: ~2 minutes  
**📝 Requirements**: Just email address

**📋 Steps**:
1. Visit https://www.alphavantage.co/support/#api-key
2. Enter your email address
3. Check your email for the API key
4. Copy the key to your `.env` file:
   ```bash
   ALPHA_VANTAGE_API_KEY=your_actual_key_here
   ```

## 📰 NewsAPI - Sentiment Analysis

**🔗 Signup Link**: https://newsapi.org/register

**📋 What you get**:
- 1000 API calls per day **FREE**
- Crypto news sentiment analysis
- Market news coverage

**⏱️ Signup Time**: ~2 minutes  
**📝 Requirements**: Email + name

**📋 Steps**:
1. Visit https://newsapi.org/register
2. Fill in your name and email
3. Verify your email
4. Copy the API key from your dashboard
5. Add to your `.env` file:
   ```bash
   NEWS_API_API_KEY=your_actual_key_here
   ```

## 💱 Bybit API - Position Data (Required)

**🔗 API Management**: https://www.bybit.com/app/user/api-management

**📋 What you need**:
- API Key and Secret for accessing your positions
- **READ-ONLY permissions** (for safety)

**⚠️ IMPORTANT**: Use **production keys** (not testnet) and set `BYBIT_TESTNET=false`

**📋 Steps**:
1. Log into your Bybit account
2. Go to API Management
3. Create new API key with **read-only** permissions
4. Copy both the key and secret to your `.env` file:
   ```bash
   BYBIT_API_KEY=your_bybit_key_here
   BYBIT_API_SECRET=your_bybit_secret_here
   BYBIT_TESTNET=false
   ```

## 🆓 Always Free APIs (No Setup Needed)

### 🪙 CoinGecko
- **Unlimited** price data
- Market cap, volume, trends
- **No API key required**

### 😨 Fear & Greed Index
- Market sentiment indicator
- **No API key required**
- Updates daily

## 📁 Complete .env File Example

```bash
# Required for positions
BYBIT_API_KEY=your_bybit_key_here
BYBIT_API_SECRET=your_bybit_secret_here
BYBIT_TESTNET=false

# Enhanced analysis (optional)
ALPHA_VANTAGE_API_KEY=your_alphavantage_key_here
NEWS_API_API_KEY=your_newsapi_key_here

# Database
DB_URL=sqlite:///./trading_assistant.db

# App settings
APP_DEBUG=true
APP_HOST=127.0.0.1
APP_PORT=8000
```

## 🧪 Test Your Setup

### 1. **Test Multi-Source APIs**
```bash
cd backend
python test_multisource.py
```

### 2. **Start the Application**
```bash
cd backend
python run_local.py
```

### 3. **Open Dashboard**
Visit: http://localhost:8000

Select "🚀 Multi-Source (Recommended)" mode and click "🔄 Refresh"

## 📊 What Works Without API Keys

Even without optional API keys, you still get:

- ✅ **CoinGecko price data** (unlimited)
- ✅ **Fear & Greed Index** (free)
- ✅ **Basic position analysis**
- ⚠️ **Alpha Vantage demo mode** (limited to basic functionality)
- ❌ **News sentiment** (requires NewsAPI key)

## 🎯 Analysis Modes Explained

### 🚀 Multi-Source (Recommended)
- **Data Sources**: CoinGecko + Alpha Vantage + NewsAPI + Fear & Greed
- **Speed**: Fast (no rate limits)
- **Quality**: Professional-grade analysis
- **API Calls**: Generous free tiers

### ⚡ Basic (Fastest)
- **Data Sources**: Position data only
- **Speed**: Fastest
- **Quality**: Essential metrics only
- **API Calls**: Minimal

### ⚠️ Bybit Trend (Legacy)
- **Data Sources**: Bybit only
- **Speed**: Slow (rate limited)
- **Quality**: Basic trend analysis
- **API Calls**: Rate limited, may cause delays

## 🔧 Troubleshooting

### Common Issues

**❓ "Demo mode" for Alpha Vantage**
- The system defaults to demo mode if no API key is provided
- Demo mode has limited functionality but still works
- Get a free key to unlock full technical analysis

**❓ "API key not configured" warnings**
- These are just warnings - the system will work with free alternatives
- Add API keys for enhanced functionality

**❓ Rate limiting errors**
- Switch to "🚀 Multi-Source" mode to avoid Bybit rate limits
- The multi-source system doesn't have rate limiting issues

### Getting Help

If you encounter issues:
1. Check the terminal output for specific error messages
2. Run `python test_multisource.py` to diagnose API connections
3. Verify your API keys are correctly copied to the `.env` file

## 🎉 Ready to Trade!

Once set up, you'll have access to:
- **Professional technical indicators** (RSI, MACD, Bollinger Bands)
- **News sentiment analysis** for each crypto
- **Market context** (ATH/ATL distances, market cap trends)
- **Enhanced recommendations** based on multiple data sources
- **No rate limiting issues** for smooth operation

Happy trading! 🚀 