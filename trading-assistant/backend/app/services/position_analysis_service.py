from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.models import Position, MarketData
from app.api.bybit_client import BybitClient
from app.config import get_settings

logger = logging.getLogger(__name__)

class PositionAnalysisService:
    """Service for analyzing trading positions and providing actionable insights"""
    
    def __init__(self, bybit_client: BybitClient, db: Session, enable_trend_analysis: bool = True):
        self.bybit_client = bybit_client
        self.db = db
        self.settings = get_settings()
        self.enable_trend_analysis = enable_trend_analysis
        # Cache for kline data to avoid duplicate API calls
        self._kline_cache = {}
    
    async def analyze_position(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single position and provide actionable insights"""
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
            
            # Get recent market data for trend analysis (if enabled)
            if self.enable_trend_analysis:
                trend_analysis = await self._analyze_trend(symbol, current_price)
            else:
                # Skip trend analysis to avoid rate limits
                trend_analysis = {"direction": "unknown", "strength": "weak", "confidence": 0}
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(
                pnl_percentage, leverage, position_value, trend_analysis
            )
            
            # Generate recommendation
            recommendation = self._generate_recommendation(
                pnl_percentage, risk_score, trend_analysis, leverage
            )
            
            # Calculate key levels
            key_levels = self._calculate_key_levels(entry_price, current_price, side)
            
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
                "trend": trend_analysis,
                "recommendation": recommendation,
                "key_levels": key_levels,
                "last_analyzed": datetime.now(timezone.utc).isoformat()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing position {position_data.get('symbol')}: {e}")
            return self._get_basic_analysis(position_data)
    
    async def _analyze_trend(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """Analyze trend using recent price data with caching"""
        try:
            # Check cache first to avoid duplicate API calls
            cache_key = f"{symbol}_1h_24"
            if cache_key in self._kline_cache:
                logger.debug(f"Using cached kline data for {symbol}")
                klines = self._kline_cache[cache_key]
            else:
                # Get recent kline data from API
                logger.debug(f"Fetching fresh kline data for {symbol}")
                klines = await self.bybit_client.get_kline(
                    symbol=symbol,
                    interval="1h",
                    limit=24  # Last 24 hours
                )
                # Cache the result
                self._kline_cache[cache_key] = klines
            
            if not klines or len(klines) < 10:
                return {"direction": "unknown", "strength": "weak", "confidence": 0}
            
            # Calculate simple trend metrics
            prices = [float(k[4]) for k in klines]  # Close prices
            volumes = [float(k[5]) for k in klines]  # Volumes
            
            # Simple moving averages
            short_ma = sum(prices[-5:]) / 5  # 5-period MA
            long_ma = sum(prices[-10:]) / 10  # 10-period MA
            
            # Price momentum
            price_momentum = (prices[-1] - prices[-5]) / prices[-5] * 100
            
            # Volume trend
            recent_vol = sum(volumes[-5:]) / 5
            older_vol = sum(volumes[-10:-5]) / 5
            volume_change = (recent_vol - older_vol) / older_vol * 100 if older_vol > 0 else 0
            
            # Determine trend direction
            if short_ma > long_ma and price_momentum > 1:
                direction = "bullish"
                strength = "strong" if abs(price_momentum) > 3 else "moderate"
            elif short_ma < long_ma and price_momentum < -1:
                direction = "bearish"
                strength = "strong" if abs(price_momentum) > 3 else "moderate"
            else:
                direction = "sideways"
                strength = "weak"
            
            # Confidence based on volume
            confidence = min(100, 50 + abs(volume_change))
            
            return {
                "direction": direction,
                "strength": strength,
                "confidence": round(confidence),
                "momentum": round(price_momentum, 2),
                "volume_trend": "increasing" if volume_change > 10 else "decreasing" if volume_change < -10 else "stable"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trend for {symbol}: {e}")
            return {"direction": "unknown", "strength": "weak", "confidence": 0}
    
    def _calculate_risk_score(self, pnl_pct: float, leverage: float, position_value: float, trend: Dict) -> int:
        """Calculate risk score from 0-100 (higher = more risky)"""
        risk_score = 0
        
        # P&L risk (30 points max)
        if pnl_pct < -10:
            risk_score += 30
        elif pnl_pct < -5:
            risk_score += 20
        elif pnl_pct < -2:
            risk_score += 10
        elif pnl_pct > 20:
            risk_score += 15  # High profit can be risky too (should take profit)
        
        # Leverage risk (25 points max)
        if leverage >= 20:
            risk_score += 25
        elif leverage >= 10:
            risk_score += 15
        elif leverage >= 5:
            risk_score += 8
        
        # Position size risk (20 points max)
        if position_value > 10000:
            risk_score += 20
        elif position_value > 5000:
            risk_score += 12
        elif position_value > 1000:
            risk_score += 5
        
        # Trend risk (25 points max)
        if trend.get("direction") == "unknown":
            risk_score += 15
        elif trend.get("strength") == "strong":
            # Strong trend opposite to position increases risk
            if trend.get("confidence", 0) > 70:
                risk_score += 10
        
        return min(100, risk_score)
    
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
    
    def _generate_recommendation(self, pnl_pct: float, risk_score: int, trend: Dict, leverage: float) -> Dict[str, Any]:
        """Generate actionable recommendation based on analysis"""
        
        # Critical situations first
        if risk_score >= 70:
            if pnl_pct < -10:
                return {
                    "action": "🚨 EMERGENCY CLOSE",
                    "urgency": "immediate",
                    "reason": f"Critical loss {pnl_pct:.1f}% with high risk score",
                    "confidence": 95
                }
            elif leverage >= 20 and pnl_pct < -5:
                return {
                    "action": "❌ CLOSE POSITION",
                    "urgency": "high",
                    "reason": f"High leverage {leverage}x with negative P&L",
                    "confidence": 90
                }
        
        # High profit situations
        if pnl_pct > 20:
            return {
                "action": "💰 TAKE PROFIT",
                "urgency": "medium",
                "reason": f"Strong profit {pnl_pct:.1f}% - secure gains",
                "confidence": 85
            }
        elif pnl_pct > 10:
            return {
                "action": "📈 PARTIAL PROFIT",
                "urgency": "low",
                "reason": f"Good profit {pnl_pct:.1f}% - consider partial exit",
                "confidence": 70
            }
        
        # Loss situations
        if pnl_pct < -5:
            if trend.get("direction") == "bearish" and trend.get("confidence", 0) > 70:
                return {
                    "action": "❌ CLOSE POSITION",
                    "urgency": "high",
                    "reason": f"Loss {pnl_pct:.1f}% with strong bearish trend",
                    "confidence": 80
                }
            else:
                return {
                    "action": "⚠️ REDUCE SIZE",
                    "urgency": "medium",
                    "reason": f"Managing loss {pnl_pct:.1f}%",
                    "confidence": 65
                }
        
        # High leverage situations
        if leverage >= 15:
            return {
                "action": "⚠️ REDUCE LEVERAGE",
                "urgency": "medium",
                "reason": f"High leverage {leverage}x increases risk",
                "confidence": 75
            }
        
        # Trend-based recommendations
        if trend.get("direction") == "bullish" and trend.get("confidence", 0) > 80:
            if pnl_pct > 0:
                return {
                    "action": "✅ HOLD STRONG",
                    "urgency": "none",
                    "reason": "Strong bullish trend with profit",
                    "confidence": 80
                }
            else:
                return {
                    "action": "🔄 CONSIDER ADD",
                    "urgency": "low",
                    "reason": "Strong bullish trend - potential opportunity",
                    "confidence": 60
                }
        
        # Default recommendation
        return {
            "action": "👀 MONITOR",
            "urgency": "none",
            "reason": "Position within normal parameters",
            "confidence": 50
        }
    
    def _calculate_key_levels(self, entry_price: float, current_price: float, side: str) -> Dict[str, float]:
        """Calculate key support/resistance levels"""
        
        # Simple key levels based on entry price
        if side.lower() == "buy":
            # For long positions
            stop_loss = entry_price * 0.95  # 5% below entry
            take_profit_1 = entry_price * 1.05  # 5% above entry
            take_profit_2 = entry_price * 1.10  # 10% above entry
        else:
            # For short positions
            stop_loss = entry_price * 1.05  # 5% above entry
            take_profit_1 = entry_price * 0.95  # 5% below entry
            take_profit_2 = entry_price * 0.90  # 10% below entry
        
        return {
            "stop_loss": round(stop_loss, 6),
            "take_profit_1": round(take_profit_1, 6),
            "take_profit_2": round(take_profit_2, 6),
            "support": round(min(entry_price, current_price) * 0.98, 6),
            "resistance": round(max(entry_price, current_price) * 1.02, 6)
        }
    
    def _get_basic_analysis(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return basic analysis when full analysis fails"""
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
            "trend": {"direction": "unknown"},
            "recommendation": {"action": "❓ ANALYZE", "urgency": "none", "reason": "Analysis unavailable"},
            "last_analyzed": datetime.now(timezone.utc).isoformat()
        }

    async def analyze_all_positions(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple positions efficiently with rate limiting"""
        analyzed_positions = []
        
        # Clear cache for fresh analysis
        self._kline_cache.clear()
        
        logger.info(f"Starting analysis of {len(positions)} positions...")
        
        # Much smaller batch size to respect rate limits
        batch_size = 3
        for i in range(0, len(positions), batch_size):
            batch = positions[i:i + batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(positions) + batch_size - 1)//batch_size} ({len(batch)} positions)")
            
            # Process batch sequentially to avoid rate limit hits
            batch_results = []
            for pos in batch:
                try:
                    result = await self.analyze_position(pos)
                    batch_results.append(result)
                    # Small delay between individual position analysis
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.error(f"Error analyzing position {pos.get('symbol')}: {e}")
                    # Add basic analysis even if trend analysis fails
                    batch_results.append(self._get_basic_analysis(pos))
            
            analyzed_positions.extend(batch_results)
            
            # Longer delay between batches to respect rate limits
            if i + batch_size < len(positions):
                logger.info(f"Completed batch {i//batch_size + 1}, waiting before next batch...")
                await asyncio.sleep(2.0)  # 2 second delay between batches
        
        logger.info(f"Completed analysis of {len(analyzed_positions)} positions")
        return analyzed_positions 