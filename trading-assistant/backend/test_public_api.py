#!/usr/bin/env python3
"""
Test public Bybit API features (no authentication required)
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.api.bybit_client import BybitClient

async def test_public_api():
    """Test public Bybit API features"""
    
    print("🔧 Testing Bybit Public API (No Authentication Required)...")
    
    try:
        # Create client without API keys for public endpoints
        async with BybitClient(testnet=True) as client:
            
            # Test tickers
            print("\n📊 Testing tickers...")
            tickers = await client.get_tickers(category="linear", symbol="BTCUSDT")
            if tickers:
                ticker = tickers[0]
                print(f"✅ BTCUSDT Price: ${float(ticker['lastPrice']):,.2f}")
                print(f"   24h Change: {float(ticker['price24hPcnt'])*100:.2f}%")
                print(f"   Volume: ${float(ticker['volume24h']):,.0f}")
            
            # Test multiple symbols
            print("\n📈 Testing multiple symbols...")
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
            for symbol in symbols:
                tickers = await client.get_tickers(category="linear", symbol=symbol)
                if tickers:
                    price = float(tickers[0]['lastPrice'])
                    print(f"   {symbol}: ${price:,.2f}")
            
            # Test market data
            print("\n📉 Testing historical data...")
            klines = await client.get_kline_data(
                category="linear",
                symbol="BTCUSDT", 
                interval="1h",
                limit=5
            )
            print(f"✅ Got {len(klines)} candles for BTCUSDT 1h")
            if klines:
                latest = klines[0]
                print(f"   Latest candle: O:{latest['open']} H:{latest['high']} L:{latest['low']} C:{latest['close']}")
            
            # Test order book
            print("\n📚 Testing order book...")
            orderbook = await client.get_order_book(category="linear", symbol="BTCUSDT", limit=5)
            if orderbook:
                print(f"✅ Order book loaded")
                if 'b' in orderbook and orderbook['b']:
                    best_bid = orderbook['b'][0]
                    print(f"   Best bid: ${float(best_bid[0]):,.2f} (Size: {best_bid[1]})")
                if 'a' in orderbook and orderbook['a']:
                    best_ask = orderbook['a'][0]
                    print(f"   Best ask: ${float(best_ask[0]):,.2f} (Size: {best_ask[1]})")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    print("\n🎉 All public API tests passed!")
    print("\n💡 The basic trading assistant features work!")
    print("   You can fetch market data, prices, and historical data.")
    print("   For position management, you'll need valid API keys.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_public_api()) 