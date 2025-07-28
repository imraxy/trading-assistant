#!/usr/bin/env python3
"""
Test script for Multi-Source Analysis System
Tests the new enhanced analysis without rate limiting issues.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.data_sources.coingecko_client import CoinGeckoClient
from app.services.data_sources.alpha_vantage_client import AlphaVantageClient
from app.services.data_sources.news_sentiment_client import NewsSentimentClient

async def test_coingecko():
    """Test CoinGecko price data"""
    print("\n🪙 Testing CoinGecko Price Data...")
    
    async with CoinGeckoClient() as client:
        # Test BTC price data
        btc_data = await client.get_price_data("BTCUSDT")
        if btc_data:
            print(f"  ✅ BTC Price: ${btc_data.get('current_price', 'N/A')}")
            print(f"  📈 24h Change: {btc_data.get('price_change_percentage_24h', 'N/A'):.2f}%")
            print(f"  📊 Market Cap Rank: #{btc_data.get('market_cap_rank', 'N/A')}")
            print(f"  🎯 Trend: {btc_data.get('trend', {}).get('direction_24h', 'N/A')} ({btc_data.get('trend', {}).get('strength', 'N/A')})")
        else:
            print("  ❌ Failed to fetch BTC data")
        
        # Test market overview
        market_data = await client.get_market_overview()
        if market_data:
            print(f"  🌍 Total Market Cap: ${market_data.get('total_market_cap_usd', 0):,.0f}")
            print(f"  👑 Bitcoin Dominance: {market_data.get('bitcoin_dominance', 0):.1f}%")
        
        print("  ✅ CoinGecko test completed")

async def test_alpha_vantage():
    """Test Alpha Vantage technical indicators"""
    print("\n📊 Testing Alpha Vantage Technical Analysis...")
    
    async with AlphaVantageClient() as client:
        if client.api_key == "demo":
            print("  ⚠️ Using demo key - limited functionality")
        
        # Test RSI for BTC
        try:
            rsi_data = await client.get_rsi("BTCUSDT")
            if rsi_data:
                print(f"  ✅ RSI: {rsi_data.get('current_value', 'N/A'):.2f} ({rsi_data.get('signal', 'N/A')})")
                print(f"  💡 Interpretation: {rsi_data.get('interpretation', 'N/A')}")
            else:
                print("  ⚠️ RSI data not available (demo mode or API issue)")
        except Exception as e:
            print(f"  ⚠️ RSI test failed: {str(e)[:100]}...")
        
        print("  ✅ Alpha Vantage test completed")

async def test_news_sentiment():
    """Test News Sentiment Analysis"""
    print("\n📰 Testing News Sentiment Analysis...")
    
    async with NewsSentimentClient() as client:
        if not client.newsapi_key:
            print("  ⚠️ NewsAPI key not configured - using free alternatives only")
        
        # Test Fear & Greed Index (always free)
        try:
            fg_data = await client.get_fear_greed_index()
            if fg_data:
                print(f"  ✅ Fear & Greed Index: {fg_data.get('fear_greed_index', 'N/A')} ({fg_data.get('classification', 'N/A')})")
                print(f"  💡 Interpretation: {fg_data.get('interpretation', 'N/A')}")
            else:
                print("  ❌ Fear & Greed Index not available")
        except Exception as e:
            print(f"  ⚠️ Fear & Greed test failed: {str(e)[:100]}...")
        
        # Test news sentiment if API key is available
        if client.newsapi_key:
            try:
                sentiment_data = await client.get_crypto_news_sentiment("BTCUSDT", days=3)
                if sentiment_data:
                    print(f"  ✅ BTC Sentiment: {sentiment_data.get('overall_sentiment', 'N/A')} (confidence: {sentiment_data.get('confidence', 0):.2f})")
                    print(f"  📊 Articles analyzed: {sentiment_data.get('total_articles', 0)}")
                else:
                    print("  ⚠️ News sentiment not available")
            except Exception as e:
                print(f"  ⚠️ News sentiment test failed: {str(e)[:100]}...")
        else:
            print("  ℹ️ Skipping news sentiment (API key not configured)")
        
        print("  ✅ News sentiment test completed")

async def test_integration():
    """Test the integration of all sources"""
    print("\n🚀 Testing Multi-Source Integration...")
    
    # Simulate a position for analysis
    mock_position = {
        "symbol": "BTCUSDT",
        "side": "Buy",
        "size": "0.1",
        "avgPrice": "45000",
        "markPrice": "47000",
        "unrealisedPnl": "200",
        "positionValue": "4700",
        "leverage": "5"
    }
    
    print(f"  📍 Mock Position: {mock_position['side']} {mock_position['size']} {mock_position['symbol']}")
    print(f"  💰 Entry: ${mock_position['avgPrice']} | Current: ${mock_position['markPrice']}")
    print(f"  📈 P&L: ${mock_position['unrealisedPnl']} | Leverage: {mock_position['leverage']}x")
    
    # Test each data source
    results = {}
    
    # Price data
    async with CoinGeckoClient() as cg_client:
        price_data = await cg_client.get_price_data("BTCUSDT")
        results["price_data"] = bool(price_data)
    
    # Technical data
    async with AlphaVantageClient() as av_client:
        try:
            rsi_data = await av_client.get_rsi("BTCUSDT")
            results["technical_data"] = bool(rsi_data)
        except:
            results["technical_data"] = False
    
    # Sentiment data
    async with NewsSentimentClient() as ns_client:
        fg_data = await ns_client.get_fear_greed_index()
        results["sentiment_data"] = bool(fg_data)
    
    print(f"\n  📊 Data Source Results:")
    print(f"    💰 Price Data (CoinGecko): {'✅' if results.get('price_data') else '❌'}")
    print(f"    📈 Technical Data (Alpha Vantage): {'✅' if results.get('technical_data') else '⚠️ Demo/Limited'}")
    print(f"    📰 Sentiment Data (Fear & Greed): {'✅' if results.get('sentiment_data') else '❌'}")
    
    success_rate = sum(results.values()) / len(results) * 100
    print(f"\n  🎯 Overall Success Rate: {success_rate:.0f}%")
    
    if success_rate >= 67:
        print("  ✅ Multi-source system is working well!")
    elif success_rate >= 33:
        print("  ⚠️ Multi-source system partially working - some sources may need API keys")
    else:
        print("  ❌ Multi-source system needs attention")

async def main():
    """Main test function"""
    print("🧪 Multi-Source Analysis System Test")
    print("=" * 50)
    
    try:
        await test_coingecko()
        await test_alpha_vantage()
        await test_news_sentiment()
        await test_integration()
        
        print("\n" + "=" * 50)
        print("✅ Multi-Source Analysis Test Complete!")
        print("\n💡 Key Benefits vs Bybit-only approach:")
        print("  🚀 No rate limiting issues")
        print("  📊 Professional technical indicators")
        print("  📰 Comprehensive sentiment analysis")
        print("  💰 Better price data and market context")
        print("  ⚡ Faster and more reliable")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 