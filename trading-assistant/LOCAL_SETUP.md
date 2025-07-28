# Local Development Setup Guide

Quick guide to get the AI Trading Assistant running locally for development and testing.

## 🚀 Quick Start

### 1. Navigate to Backend Directory
```bash
cd trading-assistant/backend
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# You should see (venv) in your terminal prompt
```

### 3. Install Dependencies

**Option A: Basic setup (recommended for first run)**
```bash
pip install -r requirements-basic.txt
```

**Option B: Full setup (includes TA-Lib - may require additional setup)**
```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables (Important!)

Set your API credentials as environment variables:

**Windows:**
```cmd
set BYBIT_API_KEY=your_bybit_api_key_here
set BYBIT_API_SECRET=your_bybit_api_secret_here
set OPENAI_API_KEY=your_openai_api_key_here
```

**Mac/Linux:**
```bash
export BYBIT_API_KEY=your_bybit_api_key_here
export BYBIT_API_SECRET=your_bybit_api_secret_here
export OPENAI_API_KEY=your_openai_api_key_here
```

**Get your API keys:**
- **Bybit Testnet**: https://testnet.bybit.com/app/user/api-management
- **OpenAI**: https://platform.openai.com/api-keys

### 5. Start the Application
```bash
python run_local.py
```

## ✅ Verify Installation

The application will start and show:
- Database initialization
- Configuration status
- Available endpoints

Open your browser and test these URLs:

1. **Health Check**: http://localhost:8000/health
2. **API Documentation**: http://localhost:8000/docs
3. **Configuration Status**: http://localhost:8000/api/v1/config
4. **Test Bybit Connection**: http://localhost:8000/api/v1/bybit/test

## 🧪 Test API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Configuration Status
```bash
curl http://localhost:8000/api/v1/config
```

### Test Bybit Connection
```bash
curl http://localhost:8000/api/v1/bybit/test
```

### Fetch Positions (requires API keys)
```bash
curl http://localhost:8000/api/v1/positions
```

## 📁 Local Development Features

- **SQLite Database**: No PostgreSQL setup needed
- **Auto-reload**: Code changes automatically restart the server
- **Debug Logging**: Detailed logs for development
- **API Documentation**: Interactive docs at `/docs`
- **Configuration Files**: Uses `config/config.development.yaml`

## 🔧 Troubleshooting

### TA-Lib Installation Issues
If you have issues with TA-Lib installation:
1. Use `requirements-basic.txt` instead
2. Install TA-Lib separately:
   ```bash
   # Using conda (recommended)
   conda install -c conda-forge ta-lib
   
   # Or on Windows with pip
   pip install TA-Lib
   ```

### API Key Issues
- Make sure environment variables are set correctly
- For Bybit, use testnet keys first
- Check that APIs have read permissions

### Database Issues
- SQLite database file will be created automatically
- Database is stored as `trading_assistant.db` in the backend directory
- Delete the file to reset the database

### Port Already in Use
If port 8000 is busy, you can change it:
```bash
export APP_PORT=8001
python run_local.py
```

## 📊 What's Working

After successful setup, you can:
- ✅ View API documentation at `/docs`
- ✅ Check application health and configuration
- ✅ Test Bybit API connection
- ✅ Fetch and store position data
- ✅ View stored positions in database

## 🔄 Next Steps

Once basic setup is working:
1. Add your real API credentials
2. Test with actual position data
3. Install full requirements including TA-Lib
4. Explore the technical analysis features (Week 2)

## 🆘 Need Help?

If you encounter issues:
1. Check that your virtual environment is activated
2. Verify API credentials are set correctly
3. Look at the terminal output for error messages
4. Check the API documentation at `/docs` 