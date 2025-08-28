"""
Positions API Routes
Real Bybit integration for trading positions
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ...services.bybit_service import bybit_service
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/positions")
async def get_positions() -> Dict[str, Any]:
    """Get real trading positions from Bybit"""
    try:
        result = await bybit_service.get_positions()
        
        if result["status"] == "success":
            return result
        else:
            logger.error(f"Failed to get positions: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch positions: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in get_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bybit/test")
async def test_bybit_connection() -> Dict[str, Any]:
    """Test Bybit API connection"""
    try:
        result = await bybit_service.test_connection()
        return result
    except Exception as e:
        logger.error(f"Error testing Bybit connection: {e}")
        return {
            "status": "error",
            "connected": False,
            "error": str(e)
        }

@router.get("/bybit/debug")
async def debug_bybit_env() -> Dict[str, Any]:
    """
    Debug current Bybit env binding and client configuration (sanitized).
    Does not expose secrets. Used to diagnose 401 causes.
    """
    try:
        key_env = os.getenv("BYBIT_API_KEY") or ""
        base_env = os.getenv("BYBIT_BASE_URL") or ""
        use_tn_env = os.getenv("BYBIT_USE_TESTNET")
        tn_env = os.getenv("BYBIT_TESTNET")
        recv_window_env = os.getenv("BYBIT_RECV_WINDOW")

        info = {
            "env": {
                "BYBIT_API_KEY_prefix": (key_env[:4] + "...") if key_env else "unset",
                "BYBIT_BASE_URL": base_env or "unset",
                "BYBIT_USE_TESTNET": use_tn_env if use_tn_env is not None else "unset",
                "BYBIT_TESTNET": tn_env if tn_env is not None else "unset",
                "BYBIT_RECV_WINDOW": recv_window_env if recv_window_env is not None else "unset",
            },
            "client": {
                "base_url": getattr(bybit_service, "base_url", "unknown"),
                "testnet": getattr(bybit_service, "testnet", None),
                "recv_window": getattr(bybit_service, "recv_window", None),
                "api_key_prefix": (bybit_service.api_key[:4] + "...") if getattr(bybit_service, "api_key", None) else "unset",
            }
        }
        return {"status": "success", "data": info}
    except Exception as e:
        logger.error(f"Error in debug_bybit_env: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/account")
async def get_account_info() -> Dict[str, Any]:
    """Get Bybit account information"""
    try:
        result = await bybit_service.get_account_info()
        
        if result["status"] == "success":
            return result
        else:
            logger.error(f"Failed to get account info: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account info: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in get_account_info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/positions")
async def debug_positions() -> Dict[str, Any]:
    """Debug positions endpoint with real data summary"""
    try:
        positions_result = await bybit_service.get_positions()
        account_result = await bybit_service.get_account_info()
        
        if positions_result["status"] == "success":
            positions = positions_result["positions"]
            
            # Calculate debug statistics
            total_positions = len(positions)
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]
            usdt_positions = [p for p in positions if "USDT" in p.get("symbol", "")]
            
            sample_symbols = [p["symbol"] for p in active_positions[:5]]
            
            return {
                "status": "success",
                "debug_info": {
                    "all_positions": {
                        "total": total_positions,
                        "active": len(active_positions),
                        "sample_active": sample_symbols
                    },
                    "usdt_positions": {
                        "total": len(usdt_positions),
                        "active": len([p for p in usdt_positions if float(p.get("size", 0)) > 0]),
                        "sample_active": [p["symbol"] for p in usdt_positions[:3]]
                    },
                    "account_info": {
                        "accountType": account_result.get("account_type", "UNIFIED"),
                        "marginMode": "CROSS",
                        "connected": True,
                        "testnet": bybit_service.testnet
                    },
                    "api_status": {
                        "positions_api": "connected",
                        "account_api": account_result["status"]
                    }
                }
            }
        else:
            return {
                "status": "error",
                "error": positions_result.get("error"),
                "debug_info": {
                    "api_status": {
                        "positions_api": "failed",
                        "account_api": account_result.get("status", "unknown")
                    }
                }
            }
            
    except Exception as e:
        logger.error(f"Error in debug_positions: {e}")
        return {
            "status": "error",
            "error": str(e),
            "debug_info": {
                "api_status": {
                    "positions_api": "error",
                    "account_api": "error"
                }
            }
        }


@router.get("/positions/closed")
async def get_closed_positions() -> Dict[str, Any]:
    """Get closed position PnL records from Bybit"""
    try:
        result = await bybit_service.get_closed_positions()
        if result["status"] == "success":
            return result
        else:
            logger.error(f"Failed to get closed positions: {result.get('error')}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch closed positions: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error in get_closed_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/all")
async def get_all_positions() -> Dict[str, Any]:
    """Get both open and closed positions for full history view"""
    try:
        open_result = await bybit_service.get_positions()
        closed_result = await bybit_service.get_closed_positions()
        if open_result.get("status") == "success" and closed_result.get("status") == "success":
            return {
                "status": "success",
                "open": open_result.get("positions", []),
                "closed": closed_result.get("closed", []),
                "counts": {
                    "open": open_result.get("total_positions", 0),
                    "closed": closed_result.get("total", 0)
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            err = open_result.get("error") or closed_result.get("error")
            raise HTTPException(status_code=500, detail=f"Failed to load positions: {err}")
    except Exception as e:
        logger.error(f"Error in get_all_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))