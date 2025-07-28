"""
Alpha Vantage API Client for professional technical indicators.
Free tier: 500 requests/day, excellent technical analysis functions.
"""

import httpx
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

class AlphaVantageClient:
    """Alpha Vantage API client for technical indicators"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.base_url = "https://www.alphavantage.co/query"
        self.api_key = api_key or "demo"  # Demo key for testing
        self.client = httpx.AsyncClient(timeout=30.0)
        self.request_count = 0
        self.max_requests_per_day = 500
        
    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Alpha Vantage API"""
        try:
            if self.request_count >= self.max_requests_per_day:
                logger.warning("Alpha Vantage daily request limit reached")
                return {}
            
            # Add API key to parameters
            params["apikey"] = self.api_key
            
            # Add delay to respect rate limits (5 requests per minute)
            await asyncio.sleep(12)  # 12 seconds between requests
            
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API error messages
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                return {}
            
            if "Note" in data:
                logger.warning(f"Alpha Vantage API note: {data['Note']}")
                return {}
            
            self.request_count += 1
            return data
            
        except Exception as e:
            logger.error(f"Alpha Vantage API error: {e}")
            return {}
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert crypto trading symbol to Alpha Vantage format"""
        # Remove USDT suffix and convert to uppercase
        if symbol.endswith("USDT"):
            return symbol.replace("USDT", "")
        return symbol.replace("USD", "")
    
    async def get_rsi(self, symbol: str, interval: str = "1hour", time_period: int = 14) -> Dict[str, Any]:
        """Get RSI (Relative Strength Index) indicator"""
        try:
            converted_symbol = self._convert_symbol(symbol)
            
            params = {
                "function": "RSI",
                "symbol": converted_symbol,
                "interval": interval,
                "time_period": time_period,
                "series_type": "close"
            }
            
            data = await self._make_request(params)
            
            if not data or "Technical Analysis: RSI" not in data:
                return {}
            
            rsi_data = data["Technical Analysis: RSI"]
            metadata = data.get("Meta Data", {})
            
            # Get the most recent RSI values
            recent_values = []
            for timestamp, values in list(rsi_data.items())[:10]:  # Last 10 values
                recent_values.append({
                    "timestamp": timestamp,
                    "rsi": float(values["RSI"])
                })
            
            if recent_values:
                current_rsi = recent_values[0]["rsi"]
                
                # Determine RSI signal
                if current_rsi > 70:
                    signal = "overbought"
                elif current_rsi < 30:
                    signal = "oversold"
                else:
                    signal = "neutral"
                
                return {
                    "symbol": symbol,
                    "indicator": "RSI",
                    "current_value": current_rsi,
                    "signal": signal,
                    "period": time_period,
                    "interval": interval,
                    "recent_values": recent_values,
                    "metadata": metadata,
                    "interpretation": self._interpret_rsi(current_rsi),
                    "last_updated": recent_values[0]["timestamp"]
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching RSI for {symbol}: {e}")
            return {}
    
    async def get_macd(self, symbol: str, interval: str = "1hour") -> Dict[str, Any]:
        """Get MACD (Moving Average Convergence Divergence) indicator"""
        try:
            converted_symbol = self._convert_symbol(symbol)
            
            params = {
                "function": "MACD",
                "symbol": converted_symbol,
                "interval": interval,
                "series_type": "close"
            }
            
            data = await self._make_request(params)
            
            if not data or "Technical Analysis: MACD" not in data:
                return {}
            
            macd_data = data["Technical Analysis: MACD"]
            metadata = data.get("Meta Data", {})
            
            # Get the most recent MACD values
            recent_values = []
            for timestamp, values in list(macd_data.items())[:10]:  # Last 10 values
                recent_values.append({
                    "timestamp": timestamp,
                    "macd": float(values["MACD"]),
                    "signal": float(values["MACD_Signal"]),
                    "histogram": float(values["MACD_Hist"])
                })
            
            if recent_values:
                current = recent_values[0]
                
                # Determine MACD signal
                if current["macd"] > current["signal"]:
                    if current["histogram"] > 0:
                        signal = "bullish"
                    else:
                        signal = "bullish_weakening"
                else:
                    if current["histogram"] < 0:
                        signal = "bearish"
                    else:
                        signal = "bearish_weakening"
                
                return {
                    "symbol": symbol,
                    "indicator": "MACD",
                    "macd": current["macd"],
                    "signal_line": current["signal"],
                    "histogram": current["histogram"],
                    "signal": signal,
                    "interval": interval,
                    "recent_values": recent_values,
                    "metadata": metadata,
                    "interpretation": self._interpret_macd(current),
                    "last_updated": current["timestamp"]
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching MACD for {symbol}: {e}")
            return {}
    
    async def get_bollinger_bands(self, symbol: str, interval: str = "1hour", time_period: int = 20) -> Dict[str, Any]:
        """Get Bollinger Bands indicator"""
        try:
            converted_symbol = self._convert_symbol(symbol)
            
            params = {
                "function": "BBANDS",
                "symbol": converted_symbol,
                "interval": interval,
                "time_period": time_period,
                "series_type": "close"
            }
            
            data = await self._make_request(params)
            
            if not data or "Technical Analysis: BBANDS" not in data:
                return {}
            
            bb_data = data["Technical Analysis: BBANDS"]
            metadata = data.get("Meta Data", {})
            
            # Get the most recent Bollinger Bands values
            recent_values = []
            for timestamp, values in list(bb_data.items())[:10]:  # Last 10 values
                recent_values.append({
                    "timestamp": timestamp,
                    "upper_band": float(values["Real Upper Band"]),
                    "middle_band": float(values["Real Middle Band"]),
                    "lower_band": float(values["Real Lower Band"])
                })
            
            if recent_values:
                current = recent_values[0]
                
                return {
                    "symbol": symbol,
                    "indicator": "Bollinger Bands",
                    "upper_band": current["upper_band"],
                    "middle_band": current["middle_band"],
                    "lower_band": current["lower_band"],
                    "period": time_period,
                    "interval": interval,
                    "recent_values": recent_values,
                    "metadata": metadata,
                    "bandwidth": (current["upper_band"] - current["lower_band"]) / current["middle_band"] * 100,
                    "last_updated": current["timestamp"]
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching Bollinger Bands for {symbol}: {e}")
            return {}
    
    async def get_stochastic(self, symbol: str, interval: str = "1hour") -> Dict[str, Any]:
        """Get Stochastic Oscillator indicator"""
        try:
            converted_symbol = self._convert_symbol(symbol)
            
            params = {
                "function": "STOCH",
                "symbol": converted_symbol,
                "interval": interval
            }
            
            data = await self._make_request(params)
            
            if not data or "Technical Analysis: STOCH" not in data:
                return {}
            
            stoch_data = data["Technical Analysis: STOCH"]
            metadata = data.get("Meta Data", {})
            
            # Get the most recent Stochastic values
            recent_values = []
            for timestamp, values in list(stoch_data.items())[:10]:  # Last 10 values
                recent_values.append({
                    "timestamp": timestamp,
                    "slowk": float(values["SlowK"]),
                    "slowd": float(values["SlowD"])
                })
            
            if recent_values:
                current = recent_values[0]
                
                # Determine Stochastic signal
                if current["slowk"] > 80 and current["slowd"] > 80:
                    signal = "overbought"
                elif current["slowk"] < 20 and current["slowd"] < 20:
                    signal = "oversold"
                elif current["slowk"] > current["slowd"]:
                    signal = "bullish"
                else:
                    signal = "bearish"
                
                return {
                    "symbol": symbol,
                    "indicator": "Stochastic",
                    "slowk": current["slowk"],
                    "slowd": current["slowd"],
                    "signal": signal,
                    "interval": interval,
                    "recent_values": recent_values,
                    "metadata": metadata,
                    "interpretation": self._interpret_stochastic(current),
                    "last_updated": current["timestamp"]
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching Stochastic for {symbol}: {e}")
            return {}
    
    async def get_multiple_indicators(self, symbol: str, interval: str = "1hour") -> Dict[str, Any]:
        """Get multiple technical indicators for comprehensive analysis"""
        try:
            logger.info(f"Fetching multiple indicators for {symbol}")
            
            # Fetch indicators with delays to respect rate limits
            indicators = {}
            
            # RSI
            rsi_data = await self.get_rsi(symbol, interval)
            if rsi_data:
                indicators["rsi"] = rsi_data
            
            # MACD  
            macd_data = await self.get_macd(symbol, interval)
            if macd_data:
                indicators["macd"] = macd_data
            
            # Bollinger Bands
            bb_data = await self.get_bollinger_bands(symbol, interval)
            if bb_data:
                indicators["bollinger_bands"] = bb_data
            
            # Stochastic
            stoch_data = await self.get_stochastic(symbol, interval)
            if stoch_data:
                indicators["stochastic"] = stoch_data
            
            return {
                "symbol": symbol,
                "interval": interval,
                "indicators": indicators,
                "analysis_summary": self._create_indicator_summary(indicators),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching multiple indicators for {symbol}: {e}")
            return {}
    
    def _interpret_rsi(self, rsi: float) -> str:
        """Interpret RSI value"""
        if rsi > 80:
            return "Extremely overbought - strong sell signal"
        elif rsi > 70:
            return "Overbought - consider selling"
        elif rsi > 50:
            return "Bullish momentum"
        elif rsi > 30:
            return "Bearish momentum"
        elif rsi > 20:
            return "Oversold - consider buying"
        else:
            return "Extremely oversold - strong buy signal"
    
    def _interpret_macd(self, macd_data: Dict) -> str:
        """Interpret MACD values"""
        macd = macd_data["macd"]
        signal = macd_data["signal"]
        histogram = macd_data["histogram"]
        
        if macd > signal and histogram > 0:
            return "Strong bullish signal - upward momentum"
        elif macd > signal and histogram < 0:
            return "Bullish but weakening momentum"
        elif macd < signal and histogram < 0:
            return "Strong bearish signal - downward momentum"
        else:
            return "Bearish but weakening momentum"
    
    def _interpret_stochastic(self, stoch_data: Dict) -> str:
        """Interpret Stochastic values"""
        slowk = stoch_data["slowk"]
        slowd = stoch_data["slowd"]
        
        if slowk > 80:
            return "Overbought territory - potential reversal"
        elif slowk < 20:
            return "Oversold territory - potential bounce"
        elif slowk > slowd:
            return "Bullish crossover - upward momentum"
        else:
            return "Bearish crossover - downward momentum"
    
    def _create_indicator_summary(self, indicators: Dict) -> Dict[str, Any]:
        """Create a summary of all indicators"""
        try:
            signals = []
            
            # Collect signals from each indicator
            if "rsi" in indicators:
                rsi_value = indicators["rsi"]["current_value"]
                if rsi_value > 70:
                    signals.append(("bearish", "RSI overbought"))
                elif rsi_value < 30:
                    signals.append(("bullish", "RSI oversold"))
                else:
                    signals.append(("neutral", "RSI neutral"))
            
            if "macd" in indicators:
                macd_signal = indicators["macd"]["signal"]
                if "bullish" in macd_signal:
                    signals.append(("bullish", f"MACD {macd_signal}"))
                elif "bearish" in macd_signal:
                    signals.append(("bearish", f"MACD {macd_signal}"))
                else:
                    signals.append(("neutral", "MACD neutral"))
            
            if "stochastic" in indicators:
                stoch_signal = indicators["stochastic"]["signal"]
                if stoch_signal in ["oversold", "bullish"]:
                    signals.append(("bullish", f"Stochastic {stoch_signal}"))
                elif stoch_signal in ["overbought", "bearish"]:
                    signals.append(("bearish", f"Stochastic {stoch_signal}"))
                else:
                    signals.append(("neutral", "Stochastic neutral"))
            
            # Calculate overall sentiment
            bullish_count = sum(1 for signal, _ in signals if signal == "bullish")
            bearish_count = sum(1 for signal, _ in signals if signal == "bearish")
            
            if bullish_count > bearish_count:
                overall_sentiment = "bullish"
            elif bearish_count > bullish_count:
                overall_sentiment = "bearish"
            else:
                overall_sentiment = "neutral"
            
            return {
                "overall_sentiment": overall_sentiment,
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "neutral_signals": len(signals) - bullish_count - bearish_count,
                "signal_details": signals,
                "confidence": abs(bullish_count - bearish_count) / len(signals) if signals else 0
            }
            
        except Exception as e:
            logger.error(f"Error creating indicator summary: {e}")
            return {"overall_sentiment": "unknown", "confidence": 0}
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 