#!/usr/bin/env python3
"""
Local Development Server for AI Trading Assistant

Starts the FastAPI application with all the right settings for local development.
Perfect for testing and development with Python 3.10/3.11.
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment for development
os.environ["ENVIRONMENT"] = "development"

def print_banner():
    """Print a nice banner for the application"""
    print("\n" + "="*60)
    print("🚀 AI Trading Assistant - Local Development Server")
    print("="*60)

def main():
    try:
        print_banner()
        
        # Import and display configuration
        from app.config import get_settings
        settings = get_settings()
        
        print(f"📊 Database: {settings.get_database_url()}")
        print(f"🌐 Host: {settings.app.host}:{settings.app.port}")
        print(f"🔧 Debug: {settings.app.debug}")
        print(f"🧪 Testnet: {settings.bybit.testnet}")
        
        print(f"\n🔑 API Status:")
        print(f"   💱 Bybit: {'✅ Configured' if settings.bybit.api_key else '❌ Not configured'}")
        print(f"   🤖 OpenAI: {'✅ Configured' if settings.openai.api_key else '❌ Not configured'}")
        
        print(f"\n🚀 Multi-Source Analysis:")
        av_status = "✅ Full" if settings.alpha_vantage.api_key and settings.alpha_vantage.api_key != "demo" else "⚠️ Demo"
        news_status = "✅ Active" if settings.news_api.api_key else "❌ Disabled"
        print(f"   💰 CoinGecko: ✅ Always Free")
        print(f"   📊 Alpha Vantage: {av_status}")
        print(f"   📰 NewsAPI: {news_status}")
        print(f"   😨 Fear & Greed: ✅ Always Free")
        
        if settings.alpha_vantage.api_key == "demo" or not settings.news_api.api_key:
            print(f"\n💡 Get free API keys for enhanced analysis:")
            if settings.alpha_vantage.api_key == "demo":
                print(f"   📊 https://www.alphavantage.co/support/#api-key")
            if not settings.news_api.api_key:
                print(f"   📰 https://newsapi.org/register")
        print("="*60)
        
        # Initialize database
        print("🔨 Initializing database...")
        from app.database import create_tables
        create_tables()
        print("✅ Database initialized successfully!")
        
        # Import uvicorn and start the server
        print(f"🚀 Starting server at http://{settings.app.host}:{settings.app.port}")
        print("📚 API Documentation: http://localhost:8000/docs")
        print("🔧 Health Check: http://localhost:8000/health")
        print("⚙️  Configuration: http://localhost:8000/api/v1/config")
        print("="*60)
        print("💡 Press Ctrl+C to stop the server")
        print()
        
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host=settings.app.host,
            port=settings.app.port,
            reload=True,  # Always enable reload in development
            log_level=settings.app.log_level.lower(),
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("\n💡 Make sure you've installed the requirements:")
        print("   pip install -r requirements-modern.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 