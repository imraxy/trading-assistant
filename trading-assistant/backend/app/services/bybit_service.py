"""
Bybit API Service
Real-time integration with Bybit exchange for position and market data
"""

import os
import time
import hmac
import hashlib
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from ..core.config import get_settings
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class BybitService:
    """Service for interacting with Bybit API"""
    
    def __init__(self):
        settings = get_settings()
        # Prefer settings (loads .env) with env fallbacks for compatibility
        self.api_key = settings.BYBIT_API_KEY or os.getenv('BYBIT_API_KEY')
        self.api_secret = settings.BYBIT_API_SECRET or os.getenv('BYBIT_API_SECRET')
        
        # Support both BYBIT_TESTNET and BYBIT_USE_TESTNET flags
        testnet_flag = os.getenv('BYBIT_USE_TESTNET') or os.getenv('BYBIT_TESTNET')
        if isinstance(testnet_flag, str):
            self.testnet = testnet_flag.lower() in ("true", "1", "yes", "on")
        elif testnet_flag is not None:
            self.testnet = bool(testnet_flag)
        else:
            self.testnet = bool(settings.BYBIT_TESTNET)
        
        # Base URL resolution with overrides
        explicit_base = os.getenv('BYBIT_BASE_URL')
        testnet_url = os.getenv('BYBIT_TESTNET_URL') or "https://api-testnet.bybit.com"
        mainnet_url = os.getenv('BYBIT_MAINNET_URL') or "https://api.bybit.com"
        if explicit_base:
            self.base_url = explicit_base
        else:
            self.base_url = testnet_url if self.testnet else mainnet_url
        
        self.recv_window = 5000
        self.client = httpx.AsyncClient(timeout=30.0)
        
    def _generate_signature(self, params: str, timestamp: str) -> str:
        """Generate signature for Bybit API authentication"""
        if not self.api_secret:
            raise ValueError("API secret not configured")
            
        payload = f"{timestamp}{self.api_key}{self.recv_window}{params}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self, params: str = "") -> Dict[str, str]:
        """Get authenticated headers for API requests"""
        if not self.api_key:
            raise ValueError("API key not configured")
            
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(params, timestamp)
        
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json",
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test API connection and credentials"""
        try:
            # Sign GET with empty params
            query_string = urlencode(sorted({"accountType": "UNIFIED"}.items()))
            headers = self._get_headers(query_string)
            response = await self.client.get(
                f"{self.base_url}/v5/account/wallet-balance",
                headers=headers,
                params={"accountType": "UNIFIED"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success" if data.get("retCode") == 0 else "error",
                    "connected": data.get("retCode") == 0,
                    "testnet": self.testnet,
                    "account_type": "UNIFIED",
                    "message": "Connection successful" if data.get("retCode") == 0 else data.get("retMsg")
                }
            else:
                return {
                    "status": "error",
                    "connected": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Bybit connection test failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }
    
    async def get_positions(self) -> Dict[str, Any]:
        """Get all active positions from Bybit"""
        try:
            all_positions: List[Dict[str, Any]] = []
            
            # Linear (USDT/USDC) and Inverse (coin-margined)
            queries: List[Dict[str, Any]] = []
            for settle in ["USDT", "USDC"]:
                queries.append({"category": "linear", "settleCoin": settle})
            queries.append({"category": "inverse"})
            
            for base_params in queries:
                category = base_params["category"]
                cursor: Optional[str] = None
                while True:
                    params_dict: Dict[str, Any] = {k: v for k, v in base_params.items() if v is not None}
                    if cursor:
                        params_dict["cursor"] = cursor
                    
                    query_string = urlencode(sorted(params_dict.items()))
                    headers = self._get_headers(query_string)
                    response = await self.client.get(
                        f"{self.base_url}/v5/position/list",
                        headers=headers,
                        params=params_dict,
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"HTTP error for {category} {base_params.get('settleCoin', '')}: {response.status_code} {response.text}")
                        break
                    
                    data = response.json()
                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit API error for {category} {base_params.get('settleCoin', '')}: {data.get('retMsg')} (code {data.get('retCode')})")
                        break
                    
                    items = data.get("result", {}).get("list", []) or []
                    all_positions.extend(items)
                    
                    cursor = data.get("result", {}).get("nextPageCursor")
                    if not cursor:
                        break
            
            active_positions = [pos for pos in all_positions if float(pos.get("size", 0) or 0) > 0]
            
            formatted_positions: List[Dict[str, Any]] = []
            for pos in active_positions:
                try:
                    size = float(pos.get("size", 0) or 0)
                    entry_price = float(pos.get("avgPrice", 0) or 0)
                    mark_price = float(pos.get("markPrice", 0) or 0)
                    unrealized_pnl = float(pos.get("unrealisedPnl", 0) or 0)
                    leverage = float(pos.get("leverage", 1) or 1)
                    position_value = size * mark_price
                    pnl_percentage = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
                    formatted_positions.append({
                        "symbol": pos.get("symbol"),
                        "side": pos.get("side"),
                        "size": size,
                        "entry_price": entry_price,
                        "current_price": mark_price,
                        "position_value": position_value,
                        "unrealized_pnl": unrealized_pnl,
                        "pnl_percentage": pnl_percentage,
                        "leverage": leverage,
                        "category": pos.get("category", "linear"),
                        "created_time": pos.get("createdTime"),
                        "updated_time": pos.get("updatedTime"),
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error formatting position {pos.get('symbol')}: {e}")
                    continue
            
            return {
                "status": "success",
                "positions": formatted_positions,
                "total_positions": len(formatted_positions),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {
                "status": "error",
                "error": str(e),
                "positions": [],
                "total_positions": 0,
            }
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information and wallet balance"""
        try:
            params = {"accountType": "UNIFIED"}
            query_string = urlencode(sorted(params.items()))
            headers = self._get_headers(query_string)
            response = await self.client.get(
                f"{self.base_url}/v5/account/wallet-balance",
                headers=headers,
                params=params,
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("retCode") == 0:
                    wallet_data = data.get("result", {}).get("list", [])
                    if wallet_data:
                        account = wallet_data[0]
                        coins = account.get("coin", [])
                        usdt_balance = 0
                        for coin in coins:
                            if coin.get("coin") == "USDT":
                                usdt_balance = float(coin.get("walletBalance", 0))
                                break
                        return {
                            "status": "success",
                            "account_type": account.get("accountType"),
                            "total_wallet_balance": usdt_balance,
                            "available_balance": usdt_balance,
                            "coins": coins,
                        }
            return {"status": "error", "error": "Failed to get account info"}
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Get market data for specified symbols"""
        try:
            market_data = {}
            
            for symbol in symbols:
                response = await self.client.get(
                    f"{self.base_url}/v5/market/tickers",
                    params={
                        "category": "linear",
                        "symbol": symbol
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("retCode") == 0:
                        tickers = data.get("result", {}).get("list", [])
                        if tickers:
                            ticker = tickers[0]
                            market_data[symbol] = {
                                "symbol": ticker.get("symbol"),
                                "last_price": float(ticker.get("lastPrice", 0)),
                                "price_24h_change": float(ticker.get("price24hPcnt", 0)) * 100,
                                "volume_24h": float(ticker.get("volume24h", 0)),
                                "high_24h": float(ticker.get("highPrice24h", 0)),
                                "low_24h": float(ticker.get("lowPrice24h", 0))
                            }
            
            return {
                "status": "success",
                "market_data": market_data,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return {
                "status": "error",
                "error": str(e),
                "market_data": {}
            }
    
    async def get_closed_positions(self, start_time_ms: Optional[int] = None, end_time_ms: Optional[int] = None, limit: int = 200) -> Dict[str, Any]:
        """Fetch closed PnL records across categories with pagination.
        Returns realized PnL and fees per close event.
        """
        try:
            all_closed: List[Dict[str, Any]] = []
            queries: List[Dict[str, Any]] = [
                {"category": "linear", "symbol": None},
                {"category": "inverse", "symbol": None},
            ]
            for base_params in queries:
                cursor: Optional[str] = None
                while True:
                    params: Dict[str, Any] = {
                        "category": base_params["category"],
                        "limit": limit,
                    }
                    if start_time_ms:
                        params["startTime"] = start_time_ms
                    if end_time_ms:
                        params["endTime"] = end_time_ms
                    if cursor:
                        params["cursor"] = cursor
                    
                    query_string = urlencode(sorted(params.items()))
                    headers = self._get_headers(query_string)
                    response = await self.client.get(
                        f"{self.base_url}/v5/position/closed-pnl",
                        headers=headers,
                        params=params,
                    )
                    if response.status_code != 200:
                        logger.error(f"HTTP error closed-pnl {base_params['category']}: {response.status_code} {response.text}")
                        break
                    data = response.json()
                    if data.get("retCode") != 0:
                        logger.warning(f"Bybit API error closed-pnl {base_params['category']}: {data.get('retMsg')}")
                        break
                    items = data.get("result", {}).get("list", []) or []
                    all_closed.extend(items)
                    cursor = data.get("result", {}).get("nextPageCursor")
                    if not cursor:
                        break
            
            # Normalize
            normalized: List[Dict[str, Any]] = []
            for item in all_closed:
                try:
                    normalized.append({
                        "symbol": item.get("symbol"),
                        "category": item.get("category"),
                        "side": item.get("side"),
                        "closed_size": float(item.get("closedSize", 0) or 0),
                        "avg_entry_price": float(item.get("avgEntryPrice", 0) or 0),
                        "avg_exit_price": float(item.get("avgExitPrice", 0) or 0),
                        "closed_pnl": float(item.get("closedPnl", 0) or 0),
                        "fee": float(item.get("fee", 0) or 0),
                        "order_id": item.get("orderId"),
                        "created_time": item.get("createdTime"),
                    })
                except Exception as e:
                    logger.warning(f"Error normalizing closed pnl record: {e}")
            return {
                "status": "success",
                "closed": normalized,
                "total": len(normalized),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get closed positions: {e}")
            return {"status": "error", "error": str(e), "closed": [], "total": 0}
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Global instance
bybit_service = BybitService()