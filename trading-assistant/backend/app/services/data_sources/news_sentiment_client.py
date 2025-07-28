"""
News Sentiment API Client for crypto news sentiment analysis.
Free tier: 1000 requests/day from NewsAPI.
"""

import httpx
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import re

logger = logging.getLogger(__name__)

class NewsSentimentClient:
    """News sentiment client for crypto market sentiment analysis"""
    
    def __init__(self, newsapi_key: Optional[str] = None):
        self.newsapi_key = newsapi_key
        self.newsapi_base_url = "https://newsapi.org/v2"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.request_count = 0
        self.max_requests_per_day = 1000
        
    async def _make_newsapi_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to NewsAPI"""
        try:
            if not self.newsapi_key:
                logger.warning("NewsAPI key not configured, skipping news sentiment")
                return {}
            
            if self.request_count >= self.max_requests_per_day:
                logger.warning("NewsAPI daily request limit reached")
                return {}
            
            params["apiKey"] = self.newsapi_key
            url = f"{self.newsapi_base_url}{endpoint}"
            
            # Add delay to respect rate limits
            await asyncio.sleep(0.1)
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "error":
                logger.error(f"NewsAPI error: {data.get('message')}")
                return {}
            
            self.request_count += 1
            return data
            
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return {}
    
    def _extract_crypto_name(self, symbol: str) -> str:
        """Extract full crypto name from symbol for better news search"""
        crypto_names = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "ADA": "Cardano", 
            "DOT": "Polkadot",
            "LINK": "Chainlink",
            "MATIC": "Polygon",
            "AVAX": "Avalanche",
            "LUNA": "Terra",
            "ATOM": "Cosmos",
            "NEAR": "Near",
            "FTM": "Fantom",
            "ALGO": "Algorand",
            "XLM": "Stellar",
            "VET": "VeChain",
            "FIL": "Filecoin",
            "ICP": "Internet Computer",
            "FLOW": "Flow",
            "HBAR": "Hedera",
            "WAVES": "Waves",
            "CELO": "Celo",
            "NEO": "Neo",
            "IOTA": "IOTA",
            "QTUM": "Qtum",
            "ZIL": "Zilliqa",
            "ONT": "Ontology",
            "ICX": "ICON",
            "ZRX": "0x",
            "BAT": "Basic Attention Token",
            "ENJ": "Enjin",
            "MANA": "Decentraland",
            "SAND": "The Sandbox",
            "GALA": "Gala",
            "CHZ": "Chiliz",
            "LRC": "Loopring",
            "IMX": "Immutable X",
            "GMT": "STEPN",
            "APT": "Aptos",
            "OP": "Optimism",
            "ARB": "Arbitrum",
            "SUI": "Sui",
            "PEPE": "Pepe",
            "SHIB": "Shiba Inu",
            "DOGE": "Dogecoin",
            "WIF": "dogwifcoin",
            "BONK": "Bonk",
            "FLOKI": "Floki",
            "TAO": "Bittensor"
        }
        
        # Remove USDT/USD suffix
        clean_symbol = symbol.replace("USDT", "").replace("USD", "").replace("PERP", "")
        return crypto_names.get(clean_symbol, clean_symbol)
    
    def _analyze_sentiment_simple(self, text: str) -> Dict[str, Any]:
        """Simple rule-based sentiment analysis"""
        try:
            text_lower = text.lower()
            
            # Positive keywords
            positive_words = [
                "bullish", "bull", "surge", "pump", "moon", "rally", "gain", "rise", "up",
                "positive", "optimistic", "buy", "strong", "breakthrough", "adoption",
                "partnership", "upgrade", "growth", "success", "breakthrough", "innovation",
                "milestone", "record", "high", "profit", "institutional", "mainstream"
            ]
            
            # Negative keywords
            negative_words = [
                "bearish", "bear", "dump", "crash", "fall", "down", "decline", "drop",
                "negative", "pessimistic", "sell", "weak", "concern", "risk", "fear",
                "regulation", "ban", "hack", "scam", "fraud", "bubble", "correction",
                "liquidation", "loss", "panic", "uncertainty", "volatile", "unstable"
            ]
            
            # Count sentiment words
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            # Calculate sentiment score (-1 to 1)
            total_words = len(text.split())
            if total_words == 0:
                return {"sentiment": "neutral", "score": 0, "confidence": 0}
            
            sentiment_score = (positive_count - negative_count) / total_words
            
            # Determine overall sentiment
            if sentiment_score > 0.01:
                sentiment = "positive"
            elif sentiment_score < -0.01:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            
            # Calculate confidence based on number of sentiment words found
            confidence = min(1.0, (positive_count + negative_count) / 10)
            
            return {
                "sentiment": sentiment,
                "score": round(sentiment_score, 3),
                "confidence": round(confidence, 2),
                "positive_signals": positive_count,
                "negative_signals": negative_count
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {"sentiment": "neutral", "score": 0, "confidence": 0}
    
    async def get_crypto_news_sentiment(self, symbol: str, days: int = 7) -> Dict[str, Any]:
        """Get news sentiment for a specific crypto"""
        try:
            crypto_name = self._extract_crypto_name(symbol)
            
            # Calculate date range
            to_date = datetime.now(timezone.utc)
            from_date = to_date - timedelta(days=days)
            
            # Search for news
            params = {
                "q": f"{crypto_name} OR {symbol} cryptocurrency crypto",
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 20
            }
            
            news_data = await self._make_newsapi_request("/everything", params)
            
            if not news_data or "articles" not in news_data:
                return self._get_neutral_sentiment(symbol)
            
            articles = news_data["articles"]
            
            if not articles:
                return self._get_neutral_sentiment(symbol)
            
            # Analyze sentiment of each article
            sentiments = []
            article_summaries = []
            
            for article in articles:
                title = article.get("title", "")
                description = article.get("description", "")
                content = article.get("content", "")
                
                # Combine title and description for sentiment analysis
                text_to_analyze = f"{title} {description}".strip()
                
                if not text_to_analyze:
                    continue
                
                sentiment_analysis = self._analyze_sentiment_simple(text_to_analyze)
                sentiments.append(sentiment_analysis)
                
                article_summaries.append({
                    "title": title,
                    "description": description[:200] + "..." if len(description) > 200 else description,
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                    "source": article.get("source", {}).get("name", ""),
                    "sentiment": sentiment_analysis["sentiment"],
                    "sentiment_score": sentiment_analysis["score"]
                })
            
            if not sentiments:
                return self._get_neutral_sentiment(symbol)
            
            # Calculate overall sentiment
            total_score = sum(s["score"] for s in sentiments)
            avg_score = total_score / len(sentiments)
            
            positive_count = sum(1 for s in sentiments if s["sentiment"] == "positive")
            negative_count = sum(1 for s in sentiments if s["sentiment"] == "negative")
            neutral_count = len(sentiments) - positive_count - negative_count
            
            # Determine overall sentiment
            if avg_score > 0.01:
                overall_sentiment = "positive"
            elif avg_score < -0.01:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
            
            # Calculate confidence based on number of articles and score consistency
            confidence = min(1.0, len(sentiments) / 10)
            
            return {
                "symbol": symbol,
                "crypto_name": crypto_name,
                "overall_sentiment": overall_sentiment,
                "sentiment_score": round(avg_score, 3),
                "confidence": round(confidence, 2),
                "total_articles": len(sentiments),
                "positive_articles": positive_count,
                "negative_articles": negative_count,
                "neutral_articles": neutral_count,
                "date_range": {
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat(),
                    "days": days
                },
                "recent_articles": article_summaries[:5],  # Top 5 most relevant
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching news sentiment for {symbol}: {e}")
            return self._get_neutral_sentiment(symbol)
    
    async def get_general_crypto_sentiment(self) -> Dict[str, Any]:
        """Get general cryptocurrency market sentiment"""
        try:
            # Search for general crypto market news
            to_date = datetime.now(timezone.utc)
            from_date = to_date - timedelta(days=3)
            
            params = {
                "q": "cryptocurrency bitcoin ethereum crypto market",
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "sortBy": "relevancy",
                "language": "en",
                "pageSize": 30
            }
            
            news_data = await self._make_newsapi_request("/everything", params)
            
            if not news_data or "articles" not in news_data:
                return {"overall_sentiment": "neutral", "confidence": 0}
            
            articles = news_data["articles"]
            sentiments = []
            
            for article in articles:
                title = article.get("title", "")
                description = article.get("description", "")
                text_to_analyze = f"{title} {description}".strip()
                
                if text_to_analyze:
                    sentiment_analysis = self._analyze_sentiment_simple(text_to_analyze)
                    sentiments.append(sentiment_analysis)
            
            if not sentiments:
                return {"overall_sentiment": "neutral", "confidence": 0}
            
            # Calculate overall market sentiment
            total_score = sum(s["score"] for s in sentiments)
            avg_score = total_score / len(sentiments)
            
            positive_count = sum(1 for s in sentiments if s["sentiment"] == "positive")
            negative_count = sum(1 for s in sentiments if s["sentiment"] == "negative")
            
            if avg_score > 0.01:
                overall_sentiment = "positive"
            elif avg_score < -0.01:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"
            
            confidence = min(1.0, len(sentiments) / 20)
            
            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": round(avg_score, 3),
                "confidence": round(confidence, 2),
                "total_articles": len(sentiments),
                "positive_articles": positive_count,
                "negative_articles": negative_count,
                "neutral_articles": len(sentiments) - positive_count - negative_count,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching general crypto sentiment: {e}")
            return {"overall_sentiment": "neutral", "confidence": 0}
    
    def _get_neutral_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Return neutral sentiment when no data is available"""
        return {
            "symbol": symbol,
            "crypto_name": self._extract_crypto_name(symbol),
            "overall_sentiment": "neutral",
            "sentiment_score": 0,
            "confidence": 0,
            "total_articles": 0,
            "positive_articles": 0,
            "negative_articles": 0,
            "neutral_articles": 0,
            "recent_articles": [],
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """Get crypto Fear & Greed Index (free API)"""
        try:
            # Alternative.me Fear & Greed Index API (free)
            response = await self.client.get("https://api.alternative.me/fng/")
            data = response.json()
            
            if "data" in data and data["data"]:
                current = data["data"][0]
                
                value = int(current["value"])
                classification = current["value_classification"]
                
                return {
                    "fear_greed_index": value,
                    "classification": classification,
                    "timestamp": current["timestamp"],
                    "interpretation": self._interpret_fear_greed(value),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
            return {}
    
    def _interpret_fear_greed(self, value: int) -> str:
        """Interpret Fear & Greed Index value"""
        if value >= 75:
            return "Extreme Greed - Market may be overvalued, consider taking profits"
        elif value >= 55:
            return "Greed - Bullish sentiment, but watch for reversal signs"
        elif value >= 45:
            return "Neutral - Balanced market sentiment"
        elif value >= 25:
            return "Fear - Bearish sentiment, potential buying opportunity"
        else:
            return "Extreme Fear - Market may be oversold, strong buying opportunity"
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 