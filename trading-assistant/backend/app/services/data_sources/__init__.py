"""
Data Sources Module for Multi-Source Analysis

This module contains clients for various external data sources:
- CoinGecko: Free crypto price data and market metrics
- Alpha Vantage: Professional technical indicators (RSI, MACD, etc.)
- NewsAPI: Crypto news sentiment analysis

These replace the rate-limited Bybit API for enhanced analysis.
"""

from .coingecko_client import CoinGeckoClient
from .alpha_vantage_client import AlphaVantageClient
from .news_sentiment_client import NewsSentimentClient

__all__ = [
    "CoinGeckoClient",
    "AlphaVantageClient", 
    "NewsSentimentClient"
] 