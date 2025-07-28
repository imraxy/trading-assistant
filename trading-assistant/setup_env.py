#!/usr/bin/env python3
"""
Setup script for AI Trading Assistant
Helps configure environment variables for multi-source analysis
"""

import os
import shutil
from pathlib import Path

def main():
    print("🚀 AI Trading Assistant - Environment Setup")
    print("=" * 50)
    
    # Get paths
    backend_dir = Path(__file__).parent / "backend"
    env_template = backend_dir / "env_template.txt"
    env_file = backend_dir / ".env"
    
    print(f"📁 Backend directory: {backend_dir}")
    print(f"📄 Template file: {env_template}")
    print(f"🎯 Target .env file: {env_file}")
    
    # Check if template exists
    if not env_template.exists():
        print(f"❌ Template file not found: {env_template}")
        return
    
    # Check if .env already exists
    if env_file.exists():
        print(f"\n⚠️  .env file already exists!")
        choice = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if choice not in ['y', 'yes']:
            print("✅ Setup cancelled - keeping existing .env file")
            return
    
    # Copy template to .env
    try:
        shutil.copy(env_template, env_file)
        print(f"\n✅ Created .env file from template")
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return
    
    print("\n🔑 API Key Setup Instructions:")
    print("-" * 40)
    
    print("\n1. 📊 Alpha Vantage (Technical Indicators - FREE 500/day)")
    print("   🔗 https://www.alphavantage.co/support/#api-key")
    print("   ⏱️  Signup: ~2 minutes")
    print("   📝 Just need email address")
    print("   💡 Replace 'demo' in ALPHA_VANTAGE_API_KEY")
    
    print("\n2. 📰 NewsAPI (Sentiment Analysis - FREE 1000/day)")
    print("   🔗 https://newsapi.org/register")
    print("   ⏱️  Signup: ~2 minutes")
    print("   📝 Need email + name")
    print("   💡 Replace 'your_newsapi_key_here' in NEWS_API_API_KEY")
    
    print("\n3. 💱 Bybit API (Required for positions)")
    print("   🔗 https://www.bybit.com/app/user/api-management")
    print("   ⚠️  IMPORTANT: Use production keys (set BYBIT_TESTNET=false)")
    print("   🔒 Permissions needed: Read-only for positions")
    print("   💡 Replace values in BYBIT_API_KEY and BYBIT_API_SECRET")
    
    print("\n📁 What works without API keys:")
    print("   ✅ CoinGecko price data (unlimited, always free)")
    print("   ✅ Fear & Greed Index (free)")
    print("   ✅ Basic position analysis")
    print("   ⚠️  Alpha Vantage in demo mode (limited)")
    print("   ❌ News sentiment (needs API key)")
    
    print(f"\n📝 Next steps:")
    print(f"   1. Edit {env_file}")
    print(f"   2. Add your API keys")
    print(f"   3. Run: cd backend && python run_local.py")
    print(f"   4. Open: http://localhost:8000")
    print(f"   5. Test multi-source analysis!")
    
    print(f"\n🧪 Test the setup:")
    print(f"   cd backend && python test_multisource.py")
    
    print("\n✅ Environment setup complete!")

if __name__ == "__main__":
    main() 