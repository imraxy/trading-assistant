"""
Portfolio API Routes
Comprehensive portfolio analysis and validation endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from ...services.portfolio_service import portfolio_service
from ...database.database import SessionLocal
from ...database import models as db_models
from sqlalchemy import select, func
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/comprehensive")
async def get_comprehensive_portfolio(
    include_analysis: bool = Query(True, description="Include performance and risk analytics"),
    validate_results: bool = Query(False, description="Validate mathematical calculations")
) -> Dict[str, Any]:
    """
    Get comprehensive portfolio analysis with all metrics
    
    This endpoint provides:
    - Portfolio summary (value, P&L, positions)
    - Long/Short position breakdowns
    - Net exposure analysis
    - Risk scoring and distribution
    - Performance analytics (optional)
    - Risk metrics (optional)
    - Sector allocation (optional)
    - Correlation matrix (optional)
    - AI recommendations (optional)
    - Mathematical validation (optional)
    """
    try:
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=include_analysis,
            validate_results=validate_results
        )
        
        if result["status"] == "success":
            return result
        else:
            logger.error(f"Portfolio analysis failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Portfolio analysis failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in comprehensive portfolio analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation")
async def validate_portfolio() -> Dict[str, Any]:
    """
    Validate portfolio calculations for mathematical accuracy
    
    This endpoint performs comprehensive validation of:
    - Position value calculations
    - P&L calculations
    - Leverage calculations
    - Net exposure calculations
    - Risk metric calculations
    
    Returns validation results with discrepancy details
    """
    try:
        # Get portfolio data with validation
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=False,
            validate_results=True
        )
        
        if result["status"] == "success":
            validation_results = result.get("validation_results")
            if validation_results:
                return {
                    "status": "success",
                    "validation_results": validation_results,
                    "timestamp": result.get("timestamp")
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Validation results not available"
                )
        else:
            logger.error(f"Portfolio validation failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Portfolio validation failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in portfolio validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_portfolio_summary() -> Dict[str, Any]:
    """
    Get basic portfolio summary without detailed analytics
    
    This is a lightweight endpoint that provides:
    - Total portfolio value
    - Total unrealized P&L
    - Active positions count
    - Average leverage
    - Basic risk score
    """
    try:
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=False,
            validate_results=False
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "portfolio_summary": result.get("portfolio_summary"),
                "timestamp": result.get("timestamp")
            }
        else:
            logger.error(f"Portfolio summary failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Portfolio summary failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_portfolio_analytics() -> Dict[str, Any]:
    """
    Get detailed portfolio analytics only
    
    This endpoint provides:
    - Performance metrics (Sharpe ratio, win rate, etc.)
    - Risk metrics (VaR, concentration, etc.)
    - Sector allocation
    - Correlation matrix
    - AI recommendations
    """
    try:
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=True,
            validate_results=False
        )
        
        if result["status"] == "success":
            analytics = result.get("analytics")
            if analytics:
                return {
                    "status": "success",
                    "analytics": analytics,
                    "timestamp": result.get("timestamp")
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Analytics not available"
                )
        else:
            logger.error(f"Portfolio analytics failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Portfolio analytics failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in portfolio analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/changes")
async def get_changes(symbol: str | None = None) -> Dict[str, Any]:
    """Get change in PnL%/value over last 1h/1d/1w using stored snapshots."""
    try:
        db = SessionLocal()
        now = func.now()
        rows = {}
        windows = {
            "1h": func.datetime(func.datetime(now, '-0 second'), '-1 hour'),
            "1d": func.datetime(func.datetime(now, '-0 second'), '-1 day'),
            "1w": func.datetime(func.datetime(now, '-0 second'), '-7 day'),
        }
        for label, since in windows.items():
            stmt = select(db_models.PositionSnapshot).where(db_models.PositionSnapshot.captured_at >= since)
            if symbol:
                stmt = stmt.where(db_models.PositionSnapshot.symbol == symbol)
            stmt = stmt.order_by(db_models.PositionSnapshot.captured_at.desc())
            result = db.execute(stmt).scalars().all()
            # Compute deltas by symbol comparing first vs last in window
            symbol_to_rows = {}
            for r in result:
                symbol_to_rows.setdefault(r.symbol, []).append(r)
            deltas = {}
            for sym, items in symbol_to_rows.items():
                if len(items) < 2:
                    continue
                latest, oldest = items[0], items[-1]
                deltas[sym] = {
                    "pnl_pct_change": (latest.pnl_percentage - oldest.pnl_percentage),
                    "pnl_usd_change": (latest.unrealized_pnl - oldest.unrealized_pnl),
                    "price_change": (latest.current_price - oldest.current_price),
                }
            rows[label] = deltas
        return {"status": "success", "data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.get("/risk-assessment")
async def get_risk_assessment() -> Dict[str, Any]:
    """
    Get detailed risk assessment
    
    This endpoint focuses on risk metrics:
    - Portfolio risk score
    - Risk distribution
    - Leverage analysis
    - Concentration risk
    - Value at Risk (VaR)
    - Risk recommendations
    """
    try:
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=True,
            validate_results=False
        )
        
        if result["status"] == "success":
            portfolio_summary = result.get("portfolio_summary", {})
            analytics = result.get("analytics", {})
            
            # Extract risk-related data
            risk_data = {
                "portfolio_risk_score": portfolio_summary.get("portfolio_risk_score", 0),
                "avg_leverage": portfolio_summary.get("avg_leverage", 0),
                "long_risk_distribution": portfolio_summary.get("long_summary", {}).get("risk_distribution", {}),
                "short_risk_distribution": portfolio_summary.get("short_summary", {}).get("risk_distribution", {}),
                "risk_metrics": analytics.get("risk_metrics", {}),
                "risk_recommendations": [
                    rec for rec in analytics.get("recommendations", [])
                    if rec.get("type") == "RISK_MANAGEMENT"
                ]
            }
            
            return {
                "status": "success",
                "risk_assessment": risk_data,
                "timestamp": result.get("timestamp")
            }
        else:
            logger.error(f"Risk assessment failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Risk assessment failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in risk assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_recommendations() -> Dict[str, Any]:
    """
    Get AI-powered portfolio recommendations
    
    This endpoint provides:
    - Risk management recommendations
    - Diversification suggestions
    - Performance improvement tips
    - Correlation warnings
    - General portfolio advice
    """
    try:
        result = await portfolio_service.get_comprehensive_analysis(
            include_analysis=True,
            validate_results=False
        )
        
        if result["status"] == "success":
            analytics = result.get("analytics", {})
            recommendations = analytics.get("recommendations", [])
            
            # Categorize recommendations
            categorized = {
                "risk_management": [],
                "diversification": [],
                "performance": [],
                "correlation": [],
                "general": []
            }
            
            for rec in recommendations:
                rec_type = rec.get("type", "GENERAL").lower()
                if rec_type == "risk_management":
                    categorized["risk_management"].append(rec)
                elif rec_type == "diversification":
                    categorized["diversification"].append(rec)
                elif rec_type == "performance":
                    categorized["performance"].append(rec)
                elif rec_type == "correlation":
                    categorized["correlation"].append(rec)
                else:
                    categorized["general"].append(rec)
            
            return {
                "status": "success",
                "recommendations": {
                    "all": recommendations,
                    "by_category": categorized,
                    "total_count": len(recommendations),
                    "high_priority_count": len([r for r in recommendations if r.get("priority") == "HIGH"])
                },
                "timestamp": result.get("timestamp")
            }
        else:
            logger.error(f"Recommendations failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Recommendations failed: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error in recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))