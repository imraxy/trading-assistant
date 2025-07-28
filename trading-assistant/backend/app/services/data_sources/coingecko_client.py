"""
CoinGecko API Client for price data and crypto metrics.
Free tier: Unlimited requests, excellent crypto coverage.
"""

import httpx
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

class CoinGeckoClient:
    """CoinGecko API client for crypto price data and metrics"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.client = httpx.AsyncClient(timeout=30.0)
        self._symbol_mapping = {}  # Cache for symbol ID mapping
        
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to CoinGecko API"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            # Add small delay to be respectful to free API
            await asyncio.sleep(0.1)
            
            response = await self.client.get(url, params=params or {})
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"CoinGecko API error: {e}")
            return {}
    
    async def _get_coin_id(self, symbol: str) -> Optional[str]:
        """Map trading symbol to CoinGecko coin ID"""
        try:
            # Remove common suffixes to get base symbol
            clean_symbol = symbol.replace("USDT", "").replace("USD", "").replace("PERP", "").lower()
            
            # Handle special cases
            symbol_mapping = {
                "btc": "bitcoin",
                "eth": "ethereum", 
                "sol": "solana",
                "ada": "cardano",
                "dot": "polkadot",
                "link": "chainlink",
                "matic": "polygon",
                "avax": "avalanche-2",
                "luna": "terra-luna-2",
                "atom": "cosmos",
                "near": "near",
                "ftm": "fantom",
                "one": "harmony",
                "algo": "algorand",
                "xlm": "stellar",
                "vet": "vechain",
                "fil": "filecoin",
                "icp": "internet-computer",
                "flow": "flow",
                "egld": "elrond-erd-2",
                "hbar": "hedera-hashgraph",
                "waves": "waves",
                "klay": "klaytn",
                "celo": "celo",
                "neo": "neo",
                "iota": "iota",
                "miota": "iota",
                "qtum": "qtum",
                "zil": "zilliqa",
                "ont": "ontology",
                "icx": "icon",
                "zrx": "0x",
                "bat": "basic-attention-token",
                "enj": "enjincoin",
                "mana": "decentraland",
                "sand": "the-sandbox",
                "gala": "gala",
                "chz": "chiliz",
                "lrc": "loopring",
                "imx": "immutable-x",
                "gmt": "stepn",
                "apt": "aptos",
                "op": "optimism",
                "arb": "arbitrum",
                "sui": "sui",
                "pepe": "pepe",
                "shib": "shiba-inu",
                "doge": "dogecoin",
                "wif": "dogwifcoin",
                "bonk": "bonk",
                "floki": "floki",
                "tao": "bittensor"
            }
            
            if clean_symbol in symbol_mapping:
                return symbol_mapping[clean_symbol]
            
            # Try to find coin by symbol search
            if clean_symbol not in self._symbol_mapping:
                search_result = await self._make_request("/search", {"query": clean_symbol})
                coins = search_result.get("coins", [])
                
                for coin in coins:
                    if coin.get("symbol", "").lower() == clean_symbol:
                        self._symbol_mapping[clean_symbol] = coin["id"]
                        return coin["id"]
                
                # If not found, store as None to avoid repeated searches
                self._symbol_mapping[clean_symbol] = None
            
            return self._symbol_mapping.get(clean_symbol)
            
        except Exception as e:
            logger.error(f"Error mapping symbol {symbol} to CoinGecko ID: {e}")
            return None
    
    async def get_price_data(self, symbol: str) -> Dict[str, Any]:
        """Get current price and basic metrics for a symbol"""
        try:
            coin_id = await self._get_coin_id(symbol)
            if not coin_id:
                return {}
            
            data = await self._make_request(
                f"/coins/{coin_id}",
                {
                    "localization": "false",
                    "tickers": "false", 
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false"
                }
            )
            
            if not data or "market_data" not in data:
                return {}
            
            market_data = data["market_data"]
            
            return {
                "symbol": symbol,
                "coin_id": coin_id,
                "name": data.get("name", ""),
                "current_price": market_data.get("current_price", {}).get("usd", 0),
                "price_change_24h": market_data.get("price_change_24h", 0),
                "price_change_percentage_24h": market_data.get("price_change_percentage_24h", 0),
                "price_change_percentage_7d": market_data.get("price_change_percentage_7d", 0),
                "price_change_percentage_30d": market_data.get("price_change_percentage_30d", 0),
                "market_cap": market_data.get("market_cap", {}).get("usd", 0),
                "market_cap_rank": market_data.get("market_cap_rank", 0),
                "volume_24h": market_data.get("total_volume", {}).get("usd", 0),
                "circulating_supply": market_data.get("circulating_supply", 0),
                "total_supply": market_data.get("total_supply", 0),
                "ath": market_data.get("ath", {}).get("usd", 0),
                "ath_change_percentage": market_data.get("ath_change_percentage", {}).get("usd", 0),
                "ath_date": market_data.get("ath_date", {}).get("usd", ""),
                "atl": market_data.get("atl", {}).get("usd", 0),
                "atl_change_percentage": market_data.get("atl_change_percentage", {}).get("usd", 0),
                "last_updated": market_data.get("last_updated", ""),
                "sentiment_votes_up_percentage": data.get("sentiment_votes_up_percentage", 50),
                "sentiment_votes_down_percentage": data.get("sentiment_votes_down_percentage", 50)
            }
            
        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {e}")
            return {}
    
    async def get_historical_prices(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical price data"""
        try:
            coin_id = await self._get_coin_id(symbol)
            if not coin_id:
                return []
            
            data = await self._make_request(
                f"/coins/{coin_id}/market_chart",
                {
                    "vs_currency": "usd",
                    "days": days,
                    "interval": "hourly" if days <= 7 else "daily"
                }
            )
            
            if not data or "prices" not in data:
                return []
            
            prices = data["prices"]
            volumes = data.get("total_volumes", [])
            
            historical_data = []
            for i, price_point in enumerate(prices):
                timestamp, price = price_point
                volume = volumes[i][1] if i < len(volumes) else 0
                
                historical_data.append({
                    "timestamp": int(timestamp),
                    "date": datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                    "price": price,
                    "volume": volume
                })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    async def get_market_overview(self) -> Dict[str, Any]:
        """Get global market overview"""
        try:
            data = await self._make_request("/global")
            
            if not data or "data" not in data:
                return {}
            
            global_data = data["data"]
            
            return {
                "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
                "total_volume_24h_usd": global_data.get("total_volume", {}).get("usd", 0),
                "bitcoin_dominance": global_data.get("market_cap_percentage", {}).get("btc", 0),
                "ethereum_dominance": global_data.get("market_cap_percentage", {}).get("eth", 0),
                "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
                "markets": global_data.get("markets", 0),
                "market_cap_change_percentage_24h": global_data.get("market_cap_change_percentage_24h_usd", 0),
                "updated_at": global_data.get("updated_at", 0)
            }
            
        except Exception as e:
            logger.error(f"Error fetching market overview: {e}")
            return {}
    
    async def get_trending_coins(self) -> List[Dict[str, Any]]:
        """Get trending/popular coins"""
        try:
            data = await self._make_request("/search/trending")
            
            if not data or "coins" not in data:
                return []
            
            trending = []
            for coin_data in data["coins"]:
                coin = coin_data.get("item", {})
                trending.append({
                    "id": coin.get("id", ""),
                    "name": coin.get("name", ""),
                    "symbol": coin.get("symbol", ""),
                    "market_cap_rank": coin.get("market_cap_rank", 0),
                    "price_btc": coin.get("price_btc", 0),
                    "score": coin.get("score", 0)
                })
            
            return trending
            
        except Exception as e:
            logger.error(f"Error fetching trending coins: {e}")
            return []
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 