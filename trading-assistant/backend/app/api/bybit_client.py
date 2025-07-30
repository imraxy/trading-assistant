"""
Standalone Bybit API Client

Direct integration with Bybit's REST API without external dependencies.
Handles authentication, rate limiting, and error handling.
"""

import asyncio
import time
import hmac
import hashlib
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


class BybitAPIError(Exception):
    """Custom exception for Bybit API errors"""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class BybitClient:
    """
    Standalone Bybit API client for trading assistant.
    
    Supports both testnet and mainnet environments.
    Implements proper authentication, rate limiting, and error handling.
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = None):
        self.settings = get_settings()
        
        # Use provided credentials or fall back to config
        self.api_key = api_key or self.settings.bybit.api_key
        self.api_secret = api_secret or self.settings.bybit.api_secret
        
        # Determine environment - use provided testnet param, or fall back to config
        if testnet is not None:
            self.use_testnet = testnet
        else:
            self.use_testnet = self.settings.bybit.use_testnet
        
        # Set URLs based on environment
        self.base_url = self.settings.bybit.get_base_url() if testnet is None else (
            self.settings.bybit.testnet_url if testnet else self.settings.bybit.mainnet_url
        )
        self.fallback_url = self.settings.bybit.get_fallback_url() if testnet is None else (
            self.settings.bybit.testnet_fallback_url if testnet else self.settings.bybit.mainnet_fallback_url
        )
        
        self.recv_window = 5000  # 5 seconds
        
        # Enhanced rate limiting from config
        self.rate_limit_calls = []
        self.max_calls_per_minute = self.settings.bybit.rate_limit_requests
        self.rate_limit_window = self.settings.bybit.rate_limit_window
        
        # Connection and error handling settings
        self.max_retries = self.settings.bybit.max_retries
        self.retry_delay = self.settings.bybit.retry_delay
        self.connection_errors = 0
        self.max_connection_errors = self.settings.bybit.max_connection_errors
        self.connection_error_cooldown = self.settings.bybit.connection_error_cooldown
        self.circuit_breaker_active = False
        self.last_error_time = 0
        
        # Initialize HTTP client with enhanced settings
        self.client = httpx.AsyncClient(
            timeout=self.settings.bybit.request_timeout,
            limits=httpx.Limits(
                max_keepalive_connections=self.settings.bybit.connection_pool_size,
                max_connections=self.settings.bybit.connection_pool_size * 2
            ),
            verify=self.settings.bybit.verify_ssl
        )
        
        logger.info(f"BybitClient initialized for {self.settings.bybit.get_environment_name()} environment")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Fallback URL: {self.fallback_url}")
    
    def _generate_signature(self, timestamp: str, params: str) -> str:
        """Generate HMAC SHA256 signature for Bybit API"""
        if not self.api_secret:
            raise BybitAPIError("API secret not configured")
        
        param_str = timestamp + self.api_key + self.recv_window.__str__() + params
        signature = hmac.new(
            bytes(self.api_secret, "utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def _check_rate_limit(self):
        """Enhanced rate limiting with configurable window"""
        now = time.time()
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            if now - self.last_error_time < self.connection_error_cooldown:
                raise BybitAPIError(
                    f"Circuit breaker active. Cooldown period: {self.connection_error_cooldown}s",
                    status_code=503
                )
            else:
                # Reset circuit breaker
                self.circuit_breaker_active = False
                self.connection_errors = 0
                logger.info("Circuit breaker reset - resuming operations")
        
        # Remove calls older than the configured window
        window = self.rate_limit_window
        self.rate_limit_calls = [call_time for call_time in self.rate_limit_calls if now - call_time < window]
        
        if len(self.rate_limit_calls) >= self.max_calls_per_minute:
            sleep_time = window - (now - self.rate_limit_calls[0])
            logger.warning(f"Rate limit reached ({len(self.rate_limit_calls)}/{self.max_calls_per_minute}), sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.rate_limit_calls.append(now)
        
        # Add small delay between all requests to be extra conservative
        await asyncio.sleep(0.1)
    
    async def _handle_connection_error(self, error: Exception):
        """Handle connection errors with circuit breaker pattern"""
        self.connection_errors += 1
        self.last_error_time = time.time()
        
        logger.error(f"Connection error #{self.connection_errors}: {error}")
        
        if (self.settings.bybit.enable_circuit_breaker and
            self.connection_errors >= self.max_connection_errors):
            self.circuit_breaker_active = True
            logger.error(f"Circuit breaker activated after {self.connection_errors} errors")
            raise BybitAPIError(
                f"Circuit breaker activated after {self.connection_errors} consecutive errors. "
                f"Cooldown period: {self.connection_error_cooldown}s",
                status_code=503
            )
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Dict[str, Any] = None, 
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make HTTP request to Bybit API"""
        
        await self._check_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": self.api_key if self.api_key else "",
        }
        
        # Prepare parameters
        if params is None:
            params = {}
        
        # Add timestamp for signed requests
        if signed:
            if not self.api_key or not self.api_secret:
                raise BybitAPIError("API credentials not configured for signed request")
            
            timestamp = str(int(time.time() * 1000))
            headers["X-BAPI-TIMESTAMP"] = timestamp
            headers["X-BAPI-RECV-WINDOW"] = str(self.recv_window)
            
            # Create query string for signature
            if method.upper() == "GET":
                # Properly encode parameters for signature generation
                query_string = urlencode(sorted(params.items()))
                signature = self._generate_signature(timestamp, query_string)
                headers["X-BAPI-SIGN"] = signature
                
                logger.debug(f"Signature params: {query_string}")
                
                # For GET requests, params go in URL
                response = await self.client.get(url, params=params, headers=headers)
            else:
                # For POST requests, params go in body
                json_params = json.dumps(params) if params else ""
                signature = self._generate_signature(timestamp, json_params)
                headers["X-BAPI-SIGN"] = signature
                
                response = await self.client.post(url, json=params, headers=headers)
        else:
            # Unsigned request
            if method.upper() == "GET":
                response = await self.client.get(url, params=params, headers=headers)
            else:
                response = await self.client.post(url, json=params, headers=headers)
        
        # Handle response
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise BybitAPIError(f"Invalid JSON response: {response.text}", response.status_code)
        
        # Check for API errors
        if response.status_code != 200:
            error_msg = data.get("retMsg", f"HTTP {response.status_code}")
            error_code = data.get("retCode", response.status_code)
            raise BybitAPIError(error_msg, response.status_code, error_code)
        
        # Check Bybit-specific error codes
        if data.get("retCode") != 0:
            error_msg = data.get("retMsg", "Unknown error")
            error_code = data.get("retCode")
            raise BybitAPIError(error_msg, error_code=error_code)
        
        return data
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            response = await self._make_request("GET", "/v5/account/info", signed=True)
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            raise
    
    async def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Get wallet balance for specified account type"""
        try:
            params = {"accountType": account_type}
            response = await self._make_request("GET", "/v5/account/wallet-balance", params, signed=True)
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Error fetching wallet balance: {e}")
            raise
    
    async def get_positions(self, category: str = "linear", symbol: str = None, settle_coin: str = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Get current positions with pagination support"""
        try:
            all_positions = []
            cursor = None
            page = 1
            
            while True:
                params = {
                    "category": category,
                    "limit": limit  # Maximum positions per page
                }
                
                if symbol:
                    params["symbol"] = symbol
                elif settle_coin:
                    params["settleCoin"] = settle_coin
                
                if cursor:
                    params["cursor"] = cursor
                
                logger.info(f"Fetching positions page {page} (limit: {limit})")
                
                try:
                    response = await self._make_request("GET", "/v5/position/list", params, signed=True)
                    result = response.get("result", {})
                    positions = result.get("list", [])
                    
                    if not positions:
                        logger.info(f"No more positions found on page {page}")
                        break
                    
                    all_positions.extend(positions)
                    logger.info(f"Page {page}: Got {len(positions)} positions (total so far: {len(all_positions)})")
                    
                    # Check if there's a next page
                    next_page_cursor = result.get("nextPageCursor")
                    if not next_page_cursor or next_page_cursor == cursor:
                        logger.info(f"Reached last page {page}")
                        break
                    
                    cursor = next_page_cursor
                    page += 1
                    
                    # Safety limit to prevent infinite loops
                    if page > 50:  # Max 50 pages = 10,000 positions max
                        logger.warning(f"Reached maximum page limit (50)")
                        break
                    
                    # Small delay between pages to respect rate limits
                    await asyncio.sleep(0.1)
                    
                except Exception as page_error:
                    logger.error(f"Failed to fetch page {page}: {page_error}")
                    
                    # If we got some positions already, return them
                    if all_positions:
                        logger.warning(f"Pagination failed on page {page}, but returning {len(all_positions)} positions from previous pages")
                        break
                    else:
                        # If this is the first page and it failed, re-raise the error
                        raise
            
            logger.info(f"PAGINATION COMPLETE: Retrieved {len(all_positions)} total positions across {page} pages")
            return all_positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise
    
    async def get_tickers(self, category: str = "linear", symbol: str = None) -> List[Dict[str, Any]]:
        """Get ticker information"""
        try:
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol
            
            response = await self._make_request("GET", "/v5/market/tickers", params)
            result = response.get("result", {})
            return result.get("list", [])
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            raise
    
    async def get_kline_data(
        self, 
        category: str = "linear",
        symbol: str = None,
        interval: str = "D",
        start: int = None,
        end: int = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Get historical candlestick data"""
        try:
            params = {
                "category": category,
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            
            response = await self._make_request("GET", "/v5/market/kline", params)
            result = response.get("result", {})
            
            # Convert kline data to more readable format with Decimal precision
            klines = []
            for kline in result.get("list", []):
                klines.append({
                    "timestamp": int(kline[0]),
                    "open": Decimal(kline[1]),
                    "high": Decimal(kline[2]),
                    "low": Decimal(kline[3]),
                    "close": Decimal(kline[4]),
                    "volume": Decimal(kline[5]),
                    "turnover": Decimal(kline[6]) if len(kline) > 6 else None
                })
            
            return klines
        except Exception as e:
            logger.error(f"Error fetching kline data: {e}")
            raise
    
    async def get_order_book(self, category: str = "linear", symbol: str = None, limit: int = 25) -> Dict[str, Any]:
        """Get order book depth"""
        try:
            params = {
                "category": category,
                "symbol": symbol,
                "limit": limit
            }
            
            response = await self._make_request("GET", "/v5/market/orderbook", params)
            return response.get("result", {})
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            raise
    
    async def get_instruments_info(self, category: str = "linear", symbol: str = None) -> List[Dict[str, Any]]:
        """Get trading instruments information"""
        try:
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol
            
            response = await self._make_request("GET", "/v5/market/instruments-info", params)
            result = response.get("result", {})
            return result.get("list", [])
        except Exception as e:
            logger.error(f"Error fetching instruments info: {e}")
            raise
    
    async def get_kline(self, symbol: str, interval: str = "1h", limit: int = 24) -> List[List]:
        """Get kline data in simplified format for analysis (alias for get_kline_data)"""
        try:
            # Call the existing get_kline_data method
            kline_data = await self.get_kline_data(
                symbol=symbol,
                interval=interval,
                limit=limit,
                category="linear"
            )
            
            # Convert to simple list format expected by analysis service
            # Each kline: [timestamp, open, high, low, close, volume]
            simple_klines = []
            for kline in kline_data:
                simple_klines.append([
                    kline["timestamp"],  # 0: timestamp
                    float(kline["open"]),      # 1: open
                    float(kline["high"]),      # 2: high  
                    float(kline["low"]),       # 3: low
                    float(kline["close"]),     # 4: close
                    float(kline["volume"])     # 5: volume
                ])
            
            return simple_klines
            
        except Exception as e:
            logger.error(f"Error fetching kline data for {symbol}: {e}")
            return []  # Return empty list on error so analysis can continue

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Helper function to create client with settings
def create_bybit_client(api_key: str = None, api_secret: str = None, testnet: bool = None) -> BybitClient:
    """Create a Bybit client with enhanced configuration from settings"""
    settings = get_settings()
    
    return BybitClient(
        api_key=api_key or settings.bybit.api_key,
        api_secret=api_secret or settings.bybit.api_secret,
        testnet=testnet if testnet is not None else settings.bybit.use_testnet
    )