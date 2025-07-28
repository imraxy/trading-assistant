#!/usr/bin/env python3
"""
Quick test to verify Bybit API credentials work
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.api.bybit_client import BybitClient

async def test_bybit_api():
    """Test Bybit API connection with hardcoded credentials"""
    
    # Your API credentials
    api_key = "BsGC3wc2ZKHiObcNgj"
    api_secret = "SlwbwGvZnJSeFrsV67JuebYwTSfMWwqvGMXM"
    
    print("🔧 Testing Bybit API Connection...")
    print(f"API Key: {api_key[:8]}...")
    print(f"Using testnet: True")
    
    try:
        async with BybitClient(api_key=api_key, api_secret=api_secret, testnet=True) as client:
            # Test public endpoint first
            print("\n📊 Testing public API (tickers)...")
            tickers = await client.get_tickers(category="linear", symbol="BTCUSDT")
            print(f"✅ Public API works! Got {len(tickers)} ticker(s)")
            
            # Test authenticated endpoint
            print("\n🔐 Testing authenticated API (account info)...")
            account_info = await client.get_account_info()
            print(f"✅ Authenticated API works! Account type: {account_info.get('accountType', 'Unknown')}")
            
            # Test positions
            print("\n📈 Testing positions...")
            positions = await client.get_positions(category="linear")
            active_positions = [pos for pos in positions if float(pos.get("size", 0)) > 0]
            print(f"✅ Positions API works! Found {len(active_positions)} active positions")
            
            if active_positions:
                print("\nActive positions:")
                for pos in active_positions[:3]:  # Show first 3
                    print(f"  - {pos['symbol']}: {pos['side']} {pos['size']}")
            else:
                print("  No active positions found")
                
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False
    
    print("\n🎉 All API tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_bybit_api())
    if success:
        print("\n💡 Your API credentials work! The issue is with .env loading.")
        print("   Try setting environment variables manually in terminal.")
    else:
        print("\n💡 There might be an issue with your API credentials.") 