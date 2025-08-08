"""
Market Data API Routes
Mock implementation for market data
"""

from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter()


@router.get("/market-data/symbols")
async def get_symbols() -> Dict[str, Any]:
    """Get available trading symbols"""
    mock_symbols = [
        "BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT",
        "BNBUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT", "EOSUSDT"
    ]
    
    return {
        "status": "success",
        "symbols": mock_symbols
    }


@router.post("/market-data/fetch")
async def fetch_market_data() -> Dict[str, Any]:
    """Start market data fetching task"""
    return {
        "status": "started",
        "task_id": "mock_task_123",
        "message": "Market data fetch started"
    }


@router.get("/progress/{task_id}")
async def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Get task progress"""
    return {
        "status": "success",
        "data": {
            "name": "Market Data Fetch",
            "status": "completed",
            "progress": 1.0,
            "current_step": "Completed",
            "completed_steps": 10,
            "total_steps": 10,
            "started_at": "2025-01-30T12:00:00Z"
        }
    }


@router.get("/market-data/{symbol}")
async def get_market_data(symbol: str, limit: int = 20) -> Dict[str, Any]:
    """Get market data for a specific symbol"""
    mock_data = [
        {
            "timestamp": "2025-01-30T12:00:00Z",
            "open": 45000.0,
            "high": 45500.0,
            "low": 44800.0,
            "close": 45200.0,
            "volume": 1234.56
        }
    ]
    
    return {
        "status": "success",
        "data": mock_data
    }