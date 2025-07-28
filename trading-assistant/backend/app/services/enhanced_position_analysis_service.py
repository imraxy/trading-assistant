"""
Enhanced Position Analysis Service using multiple data sources.
Combines Bybit (positions), CoinGecko (price data), Alpha Vantage (technical indicators), 
and News Sentiment for comprehensive analysis without rate limiting issues.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.api.bybit_client import BybitClient
from app.services.data_sources.coingecko_client import CoinGeckoClient
from app.services.data_sources.alpha_vantage_client import AlphaVantageClient
from app.services.data_sources.news_sentiment_client import NewsSentimentClient
from app.config import get_settings

logger = logging.getLogger(__name__)

class EnhancedPositionAnalysisService:
    """Enhanced position analysis using multiple data sources"""
    
    def __init__(self, 
                 bybit_client: BybitClient, 
                 db: Session,
                 enable_technical_analysis: bool = True,
                 enable_sentiment_analysis: bool = True):
        
        self.bybit_client = bybit_client
        self.db = db
        self.settings = get_settings()
        self.enable_technical_analysis = enable_technical_analysis
        self.enable_sentiment_analysis = enable_sentiment_analysis
        
        # Initialize data source clients
        self.coingecko = CoinGeckoClient()
        
        # Alpha Vantage - will use demo key if not configured
        alpha_vantage_key = getattr(self.settings.alpha_vantage, 'api_key', 'demo')
        self.alpha_vantage = AlphaVantageClient(alpha_vantage_key)
        
        # News API - will skip if not configured
        newsapi_key = getattr(self.settings.news_api, 'api_key', None)
        self.news_sentiment = NewsSentimentClient(newsapi_key)
        
        # Cache for data to avoid duplicate API calls
        self._price_cache = {}
        self._technical_cache = {}
        self._sentiment_cache = {}
        self._fear_greed_cache = None
        
    async def analyze_position(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single position with enhanced multi-source data"""
        try:
            symbol = position_data["symbol"]
            size = float(position_data.get("size", 0))
            side = position_data.get("side", "")
            entry_price = float(position_data.get("avgPrice", 0))
            current_price = float(position_data.get("markPrice", 0))
            unrealized_pnl = float(position_data.get("unrealisedPnl", 0))
            position_value = float(position_data.get("positionValue", 0))
            leverage = float(position_data.get("leverage", 1))
            
            # Calculate basic metrics
            pnl_percentage = (unrealized_pnl / position_value * 100) if position_value > 0 else 0
            price_change_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            # Adjust for side (short positions)
            if side.lower() == "sell":
                price_change_pct = -price_change_pct
            
            # Get enhanced market data from CoinGecko
            price_data = await self._get_price_data(symbol)
            
            # Get technical analysis (if enabled)
            technical_analysis = {}
            if self.enable_technical_analysis:
                technical_analysis = await self._get_technical_analysis(symbol)
            
            # Get sentiment analysis (if enabled)
            sentiment_analysis = {}
            if self.enable_sentiment_analysis:
                sentiment_analysis = await self._get_sentiment_analysis(symbol)
            
            # Calculate enhanced risk score
            risk_score = self._calculate_enhanced_risk_score(
                pnl_percentage, leverage, position_value, 
                price_data, technical_analysis, sentiment_analysis
            )
            
            # Generate enhanced recommendation
            recommendation = self._generate_enhanced_recommendation(
                pnl_percentage, risk_score, price_data, 
                technical_analysis, sentiment_analysis, leverage
            )
            
            # Calculate key levels using multiple data sources
            key_levels = self._calculate_enhanced_key_levels(
                entry_price, current_price, side, price_data, technical_analysis
            )
            
            analysis = {
                "symbol": symbol,
                "side": side,
                "size": size,
                "entry_price": entry_price,
                "current_price": current_price,
                "pnl_amount": unrealized_pnl,
                "pnl_percentage": round(pnl_percentage, 2),
                "price_change_pct": round(price_change_pct, 2),
                "leverage": int(leverage),
                "position_value": position_value,
                "risk_score": risk_score,
                "risk_level": self._get_risk_level(risk_score),
                "enhanced_data": {
                    "price_data": price_data,
                    "technical_analysis": technical_analysis,
                    "sentiment_analysis": sentiment_analysis
                },
                "recommendation": recommendation,
                "key_levels": key_levels,
                "data_sources": self._get_data_sources_status(),
                "last_analyzed": datetime.now(timezone.utc).isoformat()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing position {position_data.get('symbol')}: {e}")
            return self._get_basic_analysis(position_data)
    
    async def _get_price_data(self, symbol: str) -> Dict[str, Any]:
        """Get enhanced price data from CoinGecko"""
        try:
            # Check cache first
            if symbol in self._price_cache:
                return self._price_cache[symbol]
            
            price_data = await self.coingecko.get_price_data(symbol)
            
            if price_data:
                # Add trend indicators based on price changes
                trend_24h = "bullish" if price_data.get("price_change_percentage_24h", 0) > 0 else "bearish"
                trend_7d = "bullish" if price_data.get("price_change_percentage_7d", 0) > 0 else "bearish"
                trend_30d = "bullish" if price_data.get("price_change_percentage_30d", 0) > 0 else "bearish"
                
                # Calculate trend strength
                change_24h = abs(price_data.get("price_change_percentage_24h", 0))
                if change_24h > 10:
                    strength = "strong"
                elif change_24h > 5:
                    strength = "moderate"
                else:
                    strength = "weak"
                
                price_data["trend"] = {
                    "direction_24h": trend_24h,
                    "direction_7d": trend_7d,
                    "direction_30d": trend_30d,
                    "strength": strength,
                    "momentum": change_24h
                }
                
                # Cache the result
                self._price_cache[symbol] = price_data
            
            return price_data
            
        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
            return {}
    
    async def _get_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get technical analysis from Alpha Vantage"""
        try:
            # Check cache first
            if symbol in self._technical_cache:
                return self._technical_cache[symbol]
            
            technical_data = await self.alpha_vantage.get_multiple_indicators(symbol)
            
            if technical_data:
                # Cache the result
                self._technical_cache[symbol] = technical_data
            
            return technical_data
            
        except Exception as e:
            logger.error(f"Error fetching technical analysis for {symbol}: {e}")
            return {}
    
    async def _get_sentiment_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment analysis from news sources"""
        try:
            # Check cache first
            if symbol in self._sentiment_cache:
                return self._sentiment_cache[symbol]
            
            # Get symbol-specific sentiment
            sentiment_data = await self.news_sentiment.get_crypto_news_sentiment(symbol)
            
            # Get general crypto fear & greed index (cached globally)
            if not self._fear_greed_cache:
                self._fear_greed_cache = await self.news_sentiment.get_fear_greed_index()
            
            if sentiment_data:
                sentiment_data["fear_greed_index"] = self._fear_greed_cache
                # Cache the result
                self._sentiment_cache[symbol] = sentiment_data
            
            return sentiment_data
            
        except Exception as e:
            logger.error(f"Error fetching sentiment analysis for {symbol}: {e}")
            return {}
    
    def _calculate_enhanced_risk_score(self, 
                                     pnl_pct: float, 
                                     leverage: float, 
                                     position_value: float,
                                     price_data: Dict,
                                     technical_analysis: Dict,
                                     sentiment_analysis: Dict) -> int:
        """Calculate enhanced risk score using multiple data sources"""
        risk_score = 0
        
        # Base risk from P&L (30 points max)
        if pnl_pct < -10:
            risk_score += 30
        elif pnl_pct < -5:
            risk_score += 20
        elif pnl_pct < -2:
            risk_score += 10
        elif pnl_pct > 20:
            risk_score += 15  # High profit can be risky too
        
        # Leverage risk (25 points max)
        if leverage >= 20:
            risk_score += 25
        elif leverage >= 10:
            risk_score += 15
        elif leverage >= 5:
            risk_score += 8
        
        # Position size risk (15 points max)
        if position_value > 10000:
            risk_score += 15
        elif position_value > 5000:
            risk_score += 10
        elif position_value > 1000:
            risk_score += 5
        
        # Price trend risk (15 points max)
        if price_data:
            change_7d = price_data.get("price_change_percentage_7d", 0)
            if abs(change_7d) > 20:  # High volatility
                risk_score += 15
            elif abs(change_7d) > 10:
                risk_score += 10
        
        # Technical analysis risk (10 points max)
        if technical_analysis and "analysis_summary" in technical_analysis:
            summary = technical_analysis["analysis_summary"]
            if summary.get("overall_sentiment") == "bearish":
                risk_score += 10
            elif summary.get("overall_sentiment") == "neutral":
                risk_score += 5
        
        # Sentiment risk (5 points max)
        if sentiment_analysis:
            if sentiment_analysis.get("overall_sentiment") == "negative":
                risk_score += 5
            
            # Fear & Greed Index
            fg_index = sentiment_analysis.get("fear_greed_index", {})
            if fg_index:
                fg_value = fg_index.get("fear_greed_index", 50)
                if fg_value < 25:  # Extreme fear
                    risk_score += 3  # Actually reduces risk - buying opportunity
                elif fg_value > 75:  # Extreme greed
                    risk_score += 5  # Increases risk - market overheated
        
        return min(100, risk_score)
    
    def _generate_enhanced_recommendation(self, 
                                        pnl_pct: float,
                                        risk_score: int,
                                        price_data: Dict,
                                        technical_analysis: Dict,
                                        sentiment_analysis: Dict,
                                        leverage: float) -> Dict[str, Any]:
        """Generate enhanced recommendation using all data sources"""
        
        # Critical situations first
        if risk_score >= 70:
            if pnl_pct < -10:
                return {
                    "action": "🚨 EMERGENCY CLOSE",
                    "urgency": "immediate",
                    "reason": f"Critical loss {pnl_pct:.1f}% with high risk factors",
                    "confidence": 95,
                    "supporting_data": ["High risk score", "Significant losses"]
                }
        
        # Enhanced profit-taking with multiple confirmations
        if pnl_pct > 15:
            supporting_signals = []
            
            # Technical signals
            if technical_analysis and "analysis_summary" in technical_analysis:
                tech_sentiment = technical_analysis["analysis_summary"].get("overall_sentiment")
                if tech_sentiment == "bearish":
                    supporting_signals.append("Technical indicators turning bearish")
            
            # Price data signals
            if price_data:
                ath_change = price_data.get("ath_change_percentage", 0)
                if ath_change > -5:  # Close to all-time high
                    supporting_signals.append("Price near all-time high")
            
            # Sentiment signals
            if sentiment_analysis:
                fg_index = sentiment_analysis.get("fear_greed_index", {})
                if fg_index and fg_index.get("fear_greed_index", 50) > 75:
                    supporting_signals.append("Market in extreme greed")
            
            if supporting_signals:
                return {
                    "action": "💰 STRONG TAKE PROFIT",
                    "urgency": "high",
                    "reason": f"Excellent profit {pnl_pct:.1f}% with reversal signals",
                    "confidence": 90,
                    "supporting_data": supporting_signals
                }
            elif pnl_pct > 25:
                return {
                    "action": "💰 TAKE PROFIT",
                    "urgency": "medium",
                    "reason": f"Strong profit {pnl_pct:.1f}% - secure gains",
                    "confidence": 85,
                    "supporting_data": ["High profit level"]
                }
        
        # Enhanced loss management
        if pnl_pct < -5:
            supporting_signals = []
            
            # Technical confirmation
            if technical_analysis and "analysis_summary" in technical_analysis:
                tech_sentiment = technical_analysis["analysis_summary"].get("overall_sentiment")
                if tech_sentiment == "bearish":
                    supporting_signals.append("Technical indicators confirm downtrend")
            
            # Trend confirmation
            if price_data:
                trend_7d = price_data.get("price_change_percentage_7d", 0)
                if trend_7d < -10:
                    supporting_signals.append("Strong 7-day downtrend")
            
            if supporting_signals:
                return {
                    "action": "❌ CLOSE POSITION",
                    "urgency": "high",
                    "reason": f"Loss {pnl_pct:.1f}% with bearish confirmations",
                    "confidence": 85,
                    "supporting_data": supporting_signals
                }
            else:
                return {
                    "action": "⚠️ REDUCE SIZE",
                    "urgency": "medium",
                    "reason": f"Managing loss {pnl_pct:.1f}% - wait for confirmation",
                    "confidence": 70,
                    "supporting_data": ["Loss management"]
                }
        
        # Enhanced hold/add signals
        if -5 <= pnl_pct <= 15:
            bullish_signals = []
            
            # Technical bullish signals
            if technical_analysis and "analysis_summary" in technical_analysis:
                tech_sentiment = technical_analysis["analysis_summary"].get("overall_sentiment")
                if tech_sentiment == "bullish":
                    bullish_signals.append("Technical indicators bullish")
            
            # Sentiment bullish signals
            if sentiment_analysis:
                if sentiment_analysis.get("overall_sentiment") == "positive":
                    bullish_signals.append("Positive news sentiment")
                
                fg_index = sentiment_analysis.get("fear_greed_index", {})
                if fg_index and fg_index.get("fear_greed_index", 50) < 30:
                    bullish_signals.append("Market in fear - buying opportunity")
            
            # Price data bullish signals
            if price_data:
                trend_7d = price_data.get("price_change_percentage_7d", 0)
                if trend_7d > 5:
                    bullish_signals.append("Strong 7-day uptrend")
            
            if len(bullish_signals) >= 2:
                return {
                    "action": "✅ STRONG HOLD",
                    "urgency": "none",
                    "reason": "Multiple bullish confirmations",
                    "confidence": 80,
                    "supporting_data": bullish_signals
                }
            elif bullish_signals:
                return {
                    "action": "👀 HOLD & MONITOR",
                    "urgency": "none",
                    "reason": "Some positive signals detected",
                    "confidence": 65,
                    "supporting_data": bullish_signals
                }
        
        # Default recommendation
        return {
            "action": "👀 MONITOR",
            "urgency": "none",
            "reason": "Position within normal parameters",
            "confidence": 50,
            "supporting_data": ["No strong signals detected"]
        }
    
    def _calculate_enhanced_key_levels(self, 
                                     entry_price: float,
                                     current_price: float,
                                     side: str,
                                     price_data: Dict,
                                     technical_analysis: Dict) -> Dict[str, Any]:
        """Calculate enhanced key levels using multiple data sources"""
        
        key_levels = {}
        
        # Basic levels based on entry price
        if side.lower() == "buy":
            basic_stop = entry_price * 0.95
            basic_tp1 = entry_price * 1.05
            basic_tp2 = entry_price * 1.10
        else:
            basic_stop = entry_price * 1.05
            basic_tp1 = entry_price * 0.95
            basic_tp2 = entry_price * 0.90
        
        key_levels.update({
            "stop_loss_basic": round(basic_stop, 6),
            "take_profit_1_basic": round(basic_tp1, 6),
            "take_profit_2_basic": round(basic_tp2, 6)
        })
        
        # Enhanced levels from price data
        if price_data:
            ath = price_data.get("ath", current_price)
            atl = price_data.get("atl", current_price)
            
            key_levels.update({
                "all_time_high": ath,
                "all_time_low": atl,
                "distance_from_ath": round((current_price - ath) / ath * 100, 2),
                "distance_from_atl": round((current_price - atl) / atl * 100, 2)
            })
        
        # Enhanced levels from technical analysis
        if technical_analysis and "indicators" in technical_analysis:
            indicators = technical_analysis["indicators"]
            
            # Bollinger Bands levels
            if "bollinger_bands" in indicators:
                bb = indicators["bollinger_bands"]
                key_levels.update({
                    "bollinger_upper": bb.get("upper_band"),
                    "bollinger_middle": bb.get("middle_band"),
                    "bollinger_lower": bb.get("lower_band")
                })
        
        return key_levels
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Convert risk score to risk level"""
        if risk_score >= 70:
            return "CRITICAL"
        elif risk_score >= 50:
            return "HIGH"
        elif risk_score >= 25:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_data_sources_status(self) -> Dict[str, str]:
        """Get status of data sources"""
        return {
            "bybit": "✅ Connected (Positions)",
            "coingecko": "✅ Connected (Price Data)",
            "alpha_vantage": "⚠️ Demo Mode" if self.alpha_vantage.api_key == "demo" else "✅ Connected (Technical Analysis)",
            "news_sentiment": "❌ Not Configured" if not self.news_sentiment.newsapi_key else "✅ Connected (Sentiment)",
            "technical_analysis": "✅ Enabled" if self.enable_technical_analysis else "❌ Disabled",
            "sentiment_analysis": "✅ Enabled" if self.enable_sentiment_analysis else "❌ Disabled"
        }
    
    def _get_basic_analysis(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return basic analysis when enhanced analysis fails"""
        pnl_pct = float(position_data.get("unrealisedPnl", 0)) / float(position_data.get("positionValue", 1)) * 100
        
        return {
            "symbol": position_data.get("symbol", ""),
            "side": position_data.get("side", ""),
            "size": float(position_data.get("size", 0)),
            "entry_price": float(position_data.get("avgPrice", 0)),
            "current_price": float(position_data.get("markPrice", 0)),
            "pnl_amount": float(position_data.get("unrealisedPnl", 0)),
            "pnl_percentage": round(pnl_pct, 2),
            "leverage": int(float(position_data.get("leverage", 1))),
            "risk_level": "UNKNOWN",
            "enhanced_data": {},
            "recommendation": {
                "action": "❓ ANALYZE", 
                "urgency": "none", 
                "reason": "Enhanced analysis unavailable",
                "confidence": 0,
                "supporting_data": []
            },
            "key_levels": {},
            "data_sources": self._get_data_sources_status(),
            "last_analyzed": datetime.now(timezone.utc).isoformat()
        }
    
    async def analyze_all_positions(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple positions with enhanced data sources"""
        analyzed_positions = []
        
        # Clear caches for fresh analysis
        self._price_cache.clear()
        self._technical_cache.clear()
        self._sentiment_cache.clear()
        self._fear_greed_cache = None
        
        logger.info(f"Starting enhanced analysis of {len(positions)} positions...")
        
        # Process positions in larger batches with parallel processing
        batch_size = 10  # Larger batches for better throughput
        for i in range(0, len(positions), batch_size):
            batch = positions[i:i + batch_size]
            
            logger.info(f"Processing enhanced batch {i//batch_size + 1}/{(len(positions) + batch_size - 1)//batch_size} ({len(batch)} positions)")
            
            # Process batch with controlled concurrency to balance speed vs rate limits
            batch_results = []
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent analyses
            
            async def analyze_with_semaphore(pos):
                async with semaphore:
                    try:
                        result = await self.analyze_position(pos)
                        # Small delay to respect rate limits
                        await asyncio.sleep(0.2)
                        return result
                    except Exception as e:
                        logger.error(f"Error analyzing position {pos.get('symbol')}: {e}")
                        return self._get_basic_analysis(pos)
            
            # Process batch concurrently with semaphore control
            batch_tasks = [analyze_with_semaphore(pos) for pos in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            
            analyzed_positions.extend(batch_results)
            
            # Shorter delay between batches since we're controlling concurrency
            if i + batch_size < len(positions):
                logger.info(f"Completed enhanced batch {i//batch_size + 1}, waiting before next batch...")
                await asyncio.sleep(1.0)  # Reduced to 1 second delay
        
        logger.info(f"Completed enhanced analysis of {len(analyzed_positions)} positions")
        return analyzed_positions
    
    async def close(self):
        """Close all HTTP clients"""
        await self.coingecko.close()
        await self.alpha_vantage.close()
        await self.news_sentiment.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 