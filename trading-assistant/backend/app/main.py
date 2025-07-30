"""
Main FastAPI application for the AI Trading Assistant.

Provides REST API endpoints for position monitoring, technical analysis,
and AI-powered trading recommendations.
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging
import asyncio

from app.config import get_settings
from app.database import get_db, create_tables
from app.api.bybit_client import create_bybit_client, BybitAPIError
from app.database.models import Account, Position, MarketData
from app.services.market_data_service import MarketDataService
from app.services.progress_tracker import get_progress_tracker
from app.services.position_analysis_service import PositionAnalysisService
from app.services.enhanced_position_analysis_service import EnhancedPositionAnalysisService
from app.services.portfolio_aggregation_service import PortfolioAggregationService
from app.services.portfolio_analytics_engine import PortfolioAnalyticsEngine
from app.services.realtime_update_service import (
    get_realtime_service, stop_realtime_service, UpdateType, UpdateMessage
)
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="AI Trading Assistant",
    description="Real-time AI-powered trading assistant for Bybit, 3Commas, and TradingView",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    logger.info("Starting AI Trading Assistant...")
    
    # Create database tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise
    
    logger.info("AI Trading Assistant started successfully!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down AI Trading Assistant...")
    
    # Stop real-time service
    try:
        await stop_realtime_service()
        logger.info("Real-time service stopped")
    except Exception as e:
        logger.error(f"Error stopping real-time service: {e}")


@app.get("/")
async def dashboard():
    """Serve the enhanced trading dashboard v2 with in-place updates"""
    return FileResponse("../frontend/enhanced-dashboard-v2.html")

@app.get("/v1")
async def dashboard_v1():
    """Serve the original enhanced trading dashboard"""
    return FileResponse("../frontend/enhanced-dashboard.html")

@app.get("/basic")
async def basic_dashboard():
    """Serve the basic trading dashboard"""
    return FileResponse("../frontend/index.html")


@app.get("/api")
async def api_root():
    """API root endpoint with basic info"""
    return {
        "message": "AI Trading Assistant API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected",  # TODO: Add actual database health check
        "bybit_api": "configured" if settings.bybit.api_key else "not_configured"
    }


@app.get("/api/v1/config")
async def get_config_status():
    """Get configuration status (without sensitive data)"""
    return {
        "bybit": {
            "configured": bool(settings.bybit.api_key),
            "testnet": settings.bybit.testnet,
            "base_url": settings.bybit.base_url
        },
        "openai": {
            "configured": bool(settings.openai.api_key),
            "model": settings.openai.model
        },
        "database": {
            "configured": bool(settings.database.url),
            "echo": settings.database.echo
        },
        "app": {
            "debug": settings.app.debug,
            "analysis_interval": settings.app.analysis_interval,
            "max_positions": settings.app.max_positions
        }
    }


@app.get("/api/v1/bybit/test")
async def test_bybit_connection():
    """Test Bybit API connection"""
    try:
        async with create_bybit_client() as client:
            # Test with public endpoint first
            tickers = await client.get_tickers(category="linear", symbol="BTCUSDT")
            
            # If we have credentials, test account info
            account_info = None
            if settings.bybit.api_key and settings.bybit.api_secret:
                try:
                    account_info = await client.get_account_info()
                except BybitAPIError as e:
                    if "api key" in str(e).lower():
                        return {
                            "status": "partial_success",
                            "message": "Public API works, but API credentials may be invalid",
                            "public_api": "working",
                            "authenticated_api": "failed",
                            "error": str(e),
                            "tickers_count": len(tickers)
                        }
                    raise
            
            return {
                "status": "success",
                "message": "Bybit API connection successful",
                "public_api": "working",
                "authenticated_api": "working" if account_info else "not_tested",
                "tickers_count": len(tickers),
                "account_info": bool(account_info)
            }
    
    except BybitAPIError as e:
        logger.error(f"Bybit API error: {e}")
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "message": "Bybit API connection failed",
            "error": str(e),
            "error_code": e.error_code
        })
    except Exception as e:
        logger.error(f"Unexpected error testing Bybit connection: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error", 
            "message": "Unexpected error testing Bybit connection",
            "error": str(e)
        })


@app.get("/api/v1/positions")
async def get_positions(
    symbol: Optional[str] = None,
    category: str = "linear",
    db: Session = Depends(get_db)
):
    """Get current positions from Bybit and store in database"""
    try:
        async with create_bybit_client() as client:
            if symbol:
                # If specific symbol requested, fetch it directly
                all_positions_data = await client.get_positions(category=category, symbol=symbol)
            else:
                # Fetch ALL USDT positions with pagination (this should get all 190+ positions)
                logger.info("Fetching ALL USDT-settled positions with pagination...")
                all_positions_data = await client.get_positions(
                    category=category,
                    settle_coin="USDT"
                )
            
            # Filter only positions with size > 0
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            logger.info(f"TOTAL ACTIVE POSITIONS: {len(active_positions)} (from {len(all_positions_data)} total)")
            
            # Log some sample positions for debugging
            if active_positions:
                logger.info(f"Sample positions: {[pos['symbol'] for pos in active_positions[:10]]}")
                if len(active_positions) > 10:
                    logger.info(f"... and {len(active_positions) - 10} more positions")
            else:
                logger.warning("No active positions found!")
            
            # Store positions in database (simplified for now)
            stored_positions = []
            for pos_data in active_positions:
                # TODO: Implement proper account management
                # For now, we'll create a default account if none exists
                account = db.query(Account).filter(Account.exchange == "bybit").first()
                if not account:
                    account = Account(
                        name="Default Bybit Account",
                        exchange="bybit",
                        is_testnet=settings.bybit.testnet
                    )
                    db.add(account)
                    db.commit()
                    db.refresh(account)
                
                # Store/update position
                position = db.query(Position).filter(
                    Position.account_id == account.id,
                    Position.symbol == pos_data["symbol"]
                ).first()
                
                if position:
                    # Update existing position
                    position.side = pos_data["side"]
                    position.size = float(pos_data["size"])
                    position.entry_price = float(pos_data["avgPrice"])
                    position.current_price = float(pos_data["markPrice"])
                    position.pnl_amount = float(pos_data["unrealisedPnl"])
                    position.pnl_percentage = float(pos_data["unrealisedPnl"]) / float(pos_data["positionValue"]) * 100 if float(pos_data["positionValue"]) > 0 else 0
                    position.leverage = int(float(pos_data["leverage"]))
                    position.last_updated = datetime.now(timezone.utc)
                else:
                    # Create new position
                    position = Position(
                        account_id=account.id,
                        symbol=pos_data["symbol"],
                        side=pos_data["side"],
                        size=float(pos_data["size"]),
                        entry_price=float(pos_data["avgPrice"]),
                        current_price=float(pos_data["markPrice"]),
                        pnl_amount=float(pos_data["unrealisedPnl"]),
                        pnl_percentage=float(pos_data["unrealisedPnl"]) / float(pos_data["positionValue"]) * 100 if float(pos_data["positionValue"]) > 0 else 0,
                        leverage=int(float(pos_data["leverage"]))
                    )
                    db.add(position)
                
                stored_positions.append({
                    "symbol": pos_data["symbol"],
                    "side": pos_data["side"],
                    "size": float(pos_data["size"]),
                    "entry_price": float(pos_data["avgPrice"]),
                    "current_price": float(pos_data["markPrice"]),
                    "pnl": float(pos_data["unrealisedPnl"]),
                    "pnl_percentage": float(pos_data["unrealisedPnl"]) / float(pos_data["positionValue"]) * 100 if float(pos_data["positionValue"]) > 0 else 0,
                    "leverage": int(float(pos_data["leverage"]))
                })
            
            db.commit()
            
            return {
                "status": "success",
                "positions_count": len(stored_positions),
                "positions": stored_positions,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    except BybitAPIError as e:
        logger.error(f"Bybit API error fetching positions: {e}")
        raise HTTPException(status_code=400, detail={
            "status": "error",
            "message": "Failed to fetch positions from Bybit",
            "error": str(e)
        })
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        })


@app.get("/api/v1/positions/progressive")
async def get_progressive_positions(
    background_tasks: BackgroundTasks,
    task_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get progressive position analysis results"""
    try:
        progress_tracker = get_progress_tracker()
        
        if task_id:
            # Return current progress for existing task
            task_progress = progress_tracker.get_task(task_id)
            if task_progress:
                partial_results = progress_tracker.get_latest_data(task_id, 'partial_results') or []
                final_results = progress_tracker.get_latest_data(task_id, 'final_results') or []
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "progress": task_progress,
                    "partial_results": partial_results,
                    "final_results": final_results if task_progress.status == 'completed' else []
                }
            else:
                return {"status": "error", "message": "Task not found"}
        
        else:
            # Start new progressive analysis
            new_task_id = str(uuid.uuid4())
            progress_tracker.start_task(new_task_id, "Progressive Position Analysis", total_steps=100)
            
            # Start background task
            background_tasks.add_task(progressive_analysis_task, new_task_id, db)
            
            return {
                "status": "success", 
                "task_id": new_task_id,
                "message": "Progressive analysis started"
            }
            
    except Exception as e:
        logger.error(f"Error in progressive positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def progressive_analysis_task(task_id: str, db: Session):
    """Background task for progressive position analysis"""
    try:
        progress_tracker = get_progress_tracker()
        progress_tracker.update_progress(task_id, "Fetching positions...", 0.1)
        
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            progress_tracker.update_progress(task_id, f"Found {len(active_positions)} active positions", 0.2)
            
            # Progressive analysis with partial results
            analyzed_positions = []
            total_positions = len(active_positions)
            
            # Process in small batches and update progress frequently
            batch_size = 5
            for i in range(0, len(active_positions), batch_size):
                batch = active_positions[i:i + batch_size]
                
                # Quick basic analysis for this batch
                for pos in batch:
                    try:
                        pnl_pct = float(pos.get("unrealisedPnl", 0)) / float(pos.get("positionValue", 1)) * 100 if float(pos.get("positionValue", 0)) > 0 else 0
                        leverage = int(float(pos.get("leverage", 1)))
                        
                        risk_score = 0
                        if pnl_pct < -10: risk_score += 40
                        elif pnl_pct < -5: risk_score += 20
                        if leverage >= 20: risk_score += 30
                        elif leverage >= 10: risk_score += 15
                        
                        risk_level = "CRITICAL" if risk_score >= 60 else "HIGH" if risk_score >= 40 else "MEDIUM" if risk_score >= 20 else "LOW"
                        
                        if pnl_pct < -10:
                            recommendation = {"action": "🚨 CLOSE POSITION", "urgency": "high", "reason": f"Heavy loss {pnl_pct:.1f}%", "confidence": 80}
                        elif pnl_pct > 15:
                            recommendation = {"action": "💰 TAKE PROFIT", "urgency": "medium", "reason": f"Good profit {pnl_pct:.1f}%", "confidence": 75}
                        elif pnl_pct < -5:
                            recommendation = {"action": "⚠️ MONITOR", "urgency": "medium", "reason": f"Losing {pnl_pct:.1f}%", "confidence": 60}
                        else:
                            recommendation = {"action": "👀 HOLD", "urgency": "none", "reason": "Position stable", "confidence": 50}
                        
                        position_value = float(pos.get("positionValue", 0))
                        analyzed_positions.append({
                            "symbol": pos.get("symbol", ""),
                            "side": pos.get("side", ""),
                            "size": float(pos.get("size", 0)),
                            "size_usd": round(position_value, 2),  # USD value of the position size
                            "entry_price": float(pos.get("avgPrice", 0)),
                            "current_price": float(pos.get("markPrice", 0)),
                            "pnl_amount": float(pos.get("unrealisedPnl", 0)),
                            "pnl_percentage": round(pnl_pct, 2),
                            "leverage": leverage,
                            "position_value": position_value,
                            "risk_score": risk_score,
                            "risk_level": risk_level,
                            "recommendation": recommendation,
                            "trend": {"direction": "analyzing...", "strength": "unknown", "confidence": "N/A"},
                            "key_levels": {
                                "stop_loss": "Calculating...",
                                "take_profit_1": "Calculating...",
                                "take_profit_2": "Calculating..."
                            },
                            "last_analyzed": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error analyzing {pos.get('symbol')}: {e}")
                
                # Update progress with partial results
                progress_percentage = min(0.9, 0.2 + (i + batch_size) / total_positions * 0.7)
                current_step = f"Analyzed {len(analyzed_positions)}/{total_positions} positions"
                
                # Store partial results in progress tracker
                progress_tracker.update_progress(
                    task_id, 
                    current_step,
                    progress_percentage, 
                    extra_data={"partial_results": analyzed_positions}
                )
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)
            
            # Complete the task with final results
            progress_tracker.update_progress(
                task_id,
                f"Analysis complete: {len(analyzed_positions)} positions",
                1.0,
                extra_data={"final_results": analyzed_positions}
            )
            progress_tracker.complete_task(task_id, f"Analysis complete: {len(analyzed_positions)} positions")
            
    except Exception as e:
        logger.error(f"Progressive analysis task failed: {e}")
        progress_tracker.error_task(task_id, f"Analysis failed: {str(e)}")


@app.get("/api/v1/positions/multi-source")
async def get_multi_source_positions(
    sort_by: str = "pnl_percentage",
    sort_order: str = "desc",
    filter_risk: Optional[str] = None,
    filter_side: Optional[str] = None,
    filter_symbol: Optional[str] = None,
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
    min_leverage: Optional[int] = None,
    max_leverage: Optional[int] = None,
    enable_technical_analysis: bool = True,
    enable_sentiment_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get enhanced positions with multi-source analysis (CoinGecko, Alpha Vantage, NewsAPI)"""
    try:
        async with create_bybit_client() as client:
            # Fetch fresh positions from Bybit
            logger.info("Fetching ALL USDT-settled positions for multi-source analysis...")
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            
            # Filter only positions with size > 0
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "total_positions": 0,
                    "filtered_positions": 0,
                    "positions": [],
                    "analysis_type": "multi-source",
                    "data_sources": {
                        "bybit": "positions",
                        "coingecko": "price_data", 
                        "alpha_vantage": "technical_indicators",
                        "news_api": "sentiment_analysis"
                    }
                }
            
            # Use enhanced multi-source analysis
            async with EnhancedPositionAnalysisService(
                client, db, enable_technical_analysis, enable_sentiment_analysis
            ) as analysis_service:
                analyzed_positions = await analysis_service.analyze_all_positions(active_positions)
            
            # Apply filters (same logic as before)
            filtered_positions = analyzed_positions
            
            if filter_risk:
                filtered_positions = [p for p in filtered_positions if p.get("risk_level") == filter_risk.upper()]
            
            if filter_side:
                filtered_positions = [p for p in filtered_positions if p.get("side").lower() == filter_side.lower()]
            
            if filter_symbol:
                filtered_positions = [p for p in filtered_positions if filter_symbol.upper() in p.get("symbol", "")]
            
            if min_pnl is not None:
                filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) >= min_pnl]
            
            if max_pnl is not None:
                filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) <= max_pnl]
            
            if min_leverage is not None:
                filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) >= min_leverage]
            
            if max_leverage is not None:
                filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) <= max_leverage]
            
            # Apply sorting
            sort_key = sort_by
            reverse_order = sort_order.lower() == "desc"
            
            if sort_key in ["pnl_percentage", "pnl_amount", "leverage", "position_value", "risk_score"]:
                filtered_positions.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse_order)
            elif sort_key == "symbol":
                filtered_positions.sort(key=lambda x: x.get("symbol", ""), reverse=reverse_order)
            elif sort_key == "urgency":
                urgency_order = {"immediate": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
                filtered_positions.sort(
                    key=lambda x: urgency_order.get(x.get("recommendation", {}).get("urgency", "none"), 0),
                    reverse=reverse_order
                )
            elif sort_key == "risk_level":
                risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
                filtered_positions.sort(
                    key=lambda x: risk_order.get(x.get("risk_level", "UNKNOWN"), 0),
                    reverse=reverse_order
                )
            
            # Calculate summary statistics
            total_pnl = sum(p.get("pnl_amount", 0) for p in filtered_positions)
            avg_leverage = sum(p.get("leverage", 1) for p in filtered_positions) / len(filtered_positions) if filtered_positions else 0
            risk_distribution = {}
            for p in filtered_positions:
                risk = p.get("risk_level", "UNKNOWN")
                risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
            
            return {
                "status": "success",
                "analysis_type": "multi-source",
                "total_positions": len(analyzed_positions),
                "filtered_positions": len(filtered_positions),
                "summary": {
                    "total_pnl": round(total_pnl, 2),
                    "avg_leverage": round(avg_leverage, 1),
                    "risk_distribution": risk_distribution
                },
                "positions": filtered_positions,
                "data_sources": {
                    "bybit": "✅ Positions only",
                    "coingecko": "✅ Price data (unlimited)",
                    "alpha_vantage": "⚠️ Technical indicators (500/day)" if enable_technical_analysis else "❌ Disabled",
                    "news_api": "⚠️ Sentiment analysis (1000/day)" if enable_sentiment_analysis else "❌ Disabled"
                },
                "filters_applied": {
                    "risk": filter_risk,
                    "side": filter_side,
                    "symbol": filter_symbol,
                    "pnl_range": [min_pnl, max_pnl],
                    "leverage_range": [min_leverage, max_leverage]
                },
                "sort": {"by": sort_by, "order": sort_order},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting multi-source positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get multi-source positions",
            "error": str(e)
        })
@app.get("/api/v1/positions/multi-source-progressive")
async def get_multi_source_positions_progressive(
    background_tasks: BackgroundTasks,
    task_id: Optional[str] = None,
    sort_by: str = "pnl_percentage",
    sort_order: str = "desc",
    filter_risk: Optional[str] = None,
    filter_side: Optional[str] = None,
    filter_symbol: Optional[str] = None,
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
    min_leverage: Optional[int] = None,
    max_leverage: Optional[int] = None,
    enable_technical_analysis: bool = True,
    enable_sentiment_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get enhanced positions with progressive multi-source analysis"""
    try:
        progress_tracker = get_progress_tracker()
        
        if task_id:
            # Return current progress for existing task
            task_progress = progress_tracker.get_task(task_id)
            if task_progress:
                partial_results = progress_tracker.get_latest_data(task_id, 'partial_results') or []
                final_results = progress_tracker.get_latest_data(task_id, 'final_results') or []
                
                # Apply filters to partial results
                filtered_partial = apply_position_filters(
                    partial_results, filter_risk, filter_side, filter_symbol, 
                    min_pnl, max_pnl, min_leverage, max_leverage
                )
                
                # Apply sorting
                sorted_partial = apply_position_sorting(filtered_partial, sort_by, sort_order)
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "progress": task_progress,
                    "partial_results": sorted_partial,
                    "final_results": final_results if task_progress.status == 'completed' else [],
                    "analysis_type": "multi-source-progressive",
                    "data_sources": {
                        "bybit": "✅ Positions",
                        "coingecko": "✅ Price data (unlimited)",
                        "alpha_vantage": "⚠️ Technical indicators (500/day)" if enable_technical_analysis else "❌ Disabled",
                        "news_api": "⚠️ Sentiment analysis (1000/day)" if enable_sentiment_analysis else "❌ Disabled"
                    }
                }
            else:
                return {"status": "error", "message": "Task not found"}
        
        else:
            # Start new progressive multi-source analysis
            new_task_id = str(uuid.uuid4())
            progress_tracker.start_task(new_task_id, "Progressive Multi-Source Analysis", total_steps=100)
            
            # Start background task
            background_tasks.add_task(
                progressive_multi_source_analysis_task, 
                new_task_id, 
                db, 
                enable_technical_analysis, 
                enable_sentiment_analysis
            )
            
            return {
                "status": "success", 
                "task_id": new_task_id,
                "message": "Progressive multi-source analysis started",
                "analysis_type": "multi-source-progressive"
            }
            
    except Exception as e:
        logger.error(f"Error in progressive multi-source positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def progressive_multi_source_analysis_task(
    task_id: str, 
    db: Session, 
    enable_technical_analysis: bool, 
    enable_sentiment_analysis: bool
):
    """Background task for progressive multi-source position analysis"""
    try:
        progress_tracker = get_progress_tracker()
        progress_tracker.update_progress(task_id, "Fetching positions...", 0.1)
        
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            progress_tracker.update_progress(task_id, f"Found {len(active_positions)} active positions", 0.2)
            
            if not active_positions:
                progress_tracker.complete_task(task_id, "No active positions found")
                return
            
            # Progressive analysis callback
            async def progress_callback(analyzed_positions, progress, message):
                progress_tracker.update_progress(
                    task_id,
                    message,
                    0.2 + (progress * 0.8),  # Scale progress from 0.2 to 1.0
                    extra_data={"partial_results": analyzed_positions}
                )
            
            # Use enhanced multi-source analysis with progress callback
            async with EnhancedPositionAnalysisService(
                client, db, enable_technical_analysis, enable_sentiment_analysis
            ) as analysis_service:
                analyzed_positions = await analysis_service.analyze_all_positions(
                    active_positions, progress_callback
                )
            
            # Complete the task with final results
            progress_tracker.update_progress(
                task_id,
                f"Multi-source analysis complete: {len(analyzed_positions)} positions",
                1.0,
                extra_data={"final_results": analyzed_positions}
            )
            progress_tracker.complete_task(task_id, f"Multi-source analysis complete: {len(analyzed_positions)} positions")
            
    except Exception as e:
        logger.error(f"Progressive multi-source analysis task failed: {e}")
        progress_tracker.error_task(task_id, f"Multi-source analysis failed: {str(e)}")


def apply_position_filters(positions, filter_risk, filter_side, filter_symbol, min_pnl, max_pnl, min_leverage, max_leverage):
    """Apply filters to position list"""
    filtered_positions = positions
    
    if filter_risk:
        filtered_positions = [p for p in filtered_positions if p.get("risk_level") == filter_risk.upper()]
    
    if filter_side:
        filtered_positions = [p for p in filtered_positions if p.get("side", "").lower() == filter_side.lower()]
    
    if filter_symbol:
        filtered_positions = [p for p in filtered_positions if filter_symbol.upper() in p.get("symbol", "")]
    
    if min_pnl is not None:
        filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) >= min_pnl]
    
    if max_pnl is not None:
        filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) <= max_pnl]
    
    if min_leverage is not None:
        filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) >= min_leverage]
    
    if max_leverage is not None:
        filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) <= max_leverage]
    
    return filtered_positions


def apply_position_sorting(positions, sort_by, sort_order):
    """Apply sorting to position list"""
    sort_key = sort_by
    reverse_order = sort_order.lower() == "desc"
    
    if sort_key in ["pnl_percentage", "pnl_amount", "leverage", "position_value", "risk_score", "size_usd"]:
        positions.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse_order)
    elif sort_key == "symbol":
        positions.sort(key=lambda x: x.get("symbol", ""), reverse=reverse_order)
    elif sort_key == "urgency":
        urgency_order = {"immediate": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
        positions.sort(
            key=lambda x: urgency_order.get(x.get("recommendation", {}).get("urgency", "none"), 0),
            reverse=reverse_order
        )
    elif sort_key == "risk_level":
        risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        positions.sort(
            key=lambda x: risk_order.get(x.get("risk_level", "UNKNOWN"), 0),
            reverse=reverse_order
        )
    
    return positions


@app.get("/api/v1/debug/positions")
async def debug_positions():
    """Debug endpoint to test position fetching with detailed information"""
    try:
        async with create_bybit_client() as client:
            debug_info = {}
            
            # Test 1: Try to get all positions without any filter
            try:
                logger.info("🔍 DEBUG: Fetching ALL positions (no filter)")
                all_positions_raw = await client.get_positions(category="linear")
                active_all = [pos for pos in all_positions_raw if float(pos.get("size", 0)) > 0]
                
                debug_info["all_positions"] = {
                    "total": len(all_positions_raw),
                    "active": len(active_all),
                    "sample_active": [pos["symbol"] for pos in active_all[:10]]
                }
                logger.info(f"🔍 DEBUG: All positions - Total: {len(all_positions_raw)}, Active: {len(active_all)}")
                
            except Exception as e:
                debug_info["all_positions"] = {"error": str(e)}
                logger.error(f"🔍 DEBUG: Failed to fetch all positions: {e}")
            
            # Test 2: Try to get USDT positions specifically
            try:
                logger.info("🔍 DEBUG: Fetching USDT-settled positions")
                usdt_positions_raw = await client.get_positions(category="linear", settle_coin="USDT")
                active_usdt = [pos for pos in usdt_positions_raw if float(pos.get("size", 0)) > 0]
                
                debug_info["usdt_positions"] = {
                    "total": len(usdt_positions_raw),
                    "active": len(active_usdt),
                    "sample_active": [pos["symbol"] for pos in active_usdt[:10]]
                }
                logger.info(f"🔍 DEBUG: USDT positions - Total: {len(usdt_positions_raw)}, Active: {len(active_usdt)}")
                
            except Exception as e:
                debug_info["usdt_positions"] = {"error": str(e)}
                logger.error(f"🔍 DEBUG: Failed to fetch USDT positions: {e}")
            
            # Test 3: Get account info
            try:
                logger.info("🔍 DEBUG: Fetching account info")
                account_info = await client.get_account_info()
                debug_info["account_info"] = {
                    "accountType": account_info.get("accountType"),
                    "marginMode": account_info.get("marginMode"),
                    "dcpStatus": account_info.get("dcpStatus")
                }
                logger.info(f"🔍 DEBUG: Account type: {account_info.get('accountType')}")
                
            except Exception as e:
                debug_info["account_info"] = {"error": str(e)}
                logger.error(f"🔍 DEBUG: Failed to fetch account info: {e}")
            
            return {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "debug_info": debug_info
            }
            
    except Exception as e:
        logger.error(f"🔍 DEBUG: Debug endpoint failed: {e}")
        return {"error": f"Debug failed: {str(e)}"}, 500


@app.get("/api/v1/positions/enhanced")
async def get_enhanced_positions(
    sort_by: str = "pnl_percentage",
    sort_order: str = "desc",
    filter_risk: Optional[str] = None,
    filter_side: Optional[str] = None,
    filter_symbol: Optional[str] = None,
    min_pnl: Optional[float] = None,
    max_pnl: Optional[float] = None,
    min_leverage: Optional[int] = None,
    max_leverage: Optional[int] = None,
    enable_trend_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get enhanced positions with analysis, filters, and sorting"""
    try:
        async with create_bybit_client() as client:
            # Fetch fresh positions from Bybit
            logger.info("Fetching ALL USDT-settled positions for enhanced analysis...")
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            
            # Filter only positions with size > 0
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "total_positions": 0,
                    "filtered_positions": 0,
                    "positions": [],
                    "filters_applied": {
                        "risk": filter_risk,
                        "side": filter_side,
                        "symbol": filter_symbol,
                        "pnl_range": [min_pnl, max_pnl],
                        "leverage_range": [min_leverage, max_leverage]
                    },
                    "sort": {"by": sort_by, "order": sort_order}
                }
            
            # Choose analysis service based on request
            if enable_trend_analysis:
                # Use legacy Bybit-based analysis (limited by rate limits)
                analysis_service = PositionAnalysisService(client, db, enable_trend_analysis)
                analyzed_positions = await analysis_service.analyze_all_positions(active_positions)
            else:
                # Use FAST basic analysis without any external API calls
                analyzed_positions = []
                for pos in active_positions:
                    try:
                        # Quick basic analysis without external API calls
                        pnl_pct = float(pos.get("unrealisedPnl", 0)) / float(pos.get("positionValue", 1)) * 100 if float(pos.get("positionValue", 0)) > 0 else 0
                        leverage = int(float(pos.get("leverage", 1)))
                        
                        # Quick risk assessment
                        risk_score = 0
                        if pnl_pct < -10: risk_score += 40
                        elif pnl_pct < -5: risk_score += 20
                        if leverage >= 20: risk_score += 30
                        elif leverage >= 10: risk_score += 15
                        
                        risk_level = "CRITICAL" if risk_score >= 60 else "HIGH" if risk_score >= 40 else "MEDIUM" if risk_score >= 20 else "LOW"
                        
                        # Quick recommendation
                        if pnl_pct < -10:
                            recommendation = {"action": "🚨 CLOSE POSITION", "urgency": "high", "reason": f"Heavy loss {pnl_pct:.1f}%", "confidence": 80}
                        elif pnl_pct > 15:
                            recommendation = {"action": "💰 TAKE PROFIT", "urgency": "medium", "reason": f"Good profit {pnl_pct:.1f}%", "confidence": 75}
                        elif pnl_pct < -5:
                            recommendation = {"action": "⚠️ MONITOR", "urgency": "medium", "reason": f"Losing {pnl_pct:.1f}%", "confidence": 60}
                        else:
                            recommendation = {"action": "👀 HOLD", "urgency": "none", "reason": "Position stable", "confidence": 50}
                        
                        position_value = float(pos.get("positionValue", 0))
                        analyzed_positions.append({
                            "symbol": pos.get("symbol", ""),
                            "side": pos.get("side", ""),
                            "size": float(pos.get("size", 0)),
                            "size_usd": round(position_value, 2),  # USD value of the position size
                            "entry_price": float(pos.get("avgPrice", 0)),
                            "current_price": float(pos.get("markPrice", 0)),
                            "pnl_amount": float(pos.get("unrealisedPnl", 0)),
                            "pnl_percentage": round(pnl_pct, 2),
                            "leverage": leverage,
                            "position_value": position_value,
                            "risk_score": risk_score,
                            "risk_level": risk_level,
                            "recommendation": recommendation,
                            "trend": {"direction": "unknown", "strength": "unknown"},
                            "last_analyzed": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error in basic analysis for {pos.get('symbol')}: {e}")
                        continue
            
            # Apply filters
            filtered_positions = analyzed_positions
            
            if filter_risk:
                filtered_positions = [p for p in filtered_positions if p.get("risk_level") == filter_risk.upper()]
            
            if filter_side:
                filtered_positions = [p for p in filtered_positions if p.get("side").lower() == filter_side.lower()]
            
            if filter_symbol:
                filtered_positions = [p for p in filtered_positions if filter_symbol.upper() in p.get("symbol", "")]
            
            if min_pnl is not None:
                filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) >= min_pnl]
            
            if max_pnl is not None:
                filtered_positions = [p for p in filtered_positions if p.get("pnl_percentage", 0) <= max_pnl]
            
            if min_leverage is not None:
                filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) >= min_leverage]
            
            if max_leverage is not None:
                filtered_positions = [p for p in filtered_positions if p.get("leverage", 0) <= max_leverage]
            
            # Apply sorting
            sort_key = sort_by
            reverse_order = sort_order.lower() == "desc"
            
            if sort_key in ["pnl_percentage", "pnl_amount", "leverage", "position_value", "risk_score"]:
                filtered_positions.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse_order)
            elif sort_key == "symbol":
                filtered_positions.sort(key=lambda x: x.get("symbol", ""), reverse=reverse_order)
            elif sort_key == "urgency":
                urgency_order = {"immediate": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
                filtered_positions.sort(
                    key=lambda x: urgency_order.get(x.get("recommendation", {}).get("urgency", "none"), 0),
                    reverse=reverse_order
                )
            elif sort_key == "risk_level":
                risk_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
                filtered_positions.sort(
                    key=lambda x: risk_order.get(x.get("risk_level", "UNKNOWN"), 0),
                    reverse=reverse_order
                )
            
            # Calculate summary statistics
            total_pnl = sum(p.get("pnl_amount", 0) for p in filtered_positions)
            avg_leverage = sum(p.get("leverage", 1) for p in filtered_positions) / len(filtered_positions) if filtered_positions else 0
            risk_distribution = {}
            for p in filtered_positions:
                risk = p.get("risk_level", "UNKNOWN")
                risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
            
            return {
                "status": "success",
                "total_positions": len(analyzed_positions),
                "filtered_positions": len(filtered_positions),
                "summary": {
                    "total_pnl": round(total_pnl, 2),
                    "avg_leverage": round(avg_leverage, 1),
                    "risk_distribution": risk_distribution
                },
                "positions": filtered_positions,
                "filters_applied": {
                    "risk": filter_risk,
                    "side": filter_side,
                    "symbol": filter_symbol,
                    "pnl_range": [min_pnl, max_pnl],
                    "leverage_range": [min_leverage, max_leverage]
                },
                "sort": {"by": sort_by, "order": sort_order},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting enhanced positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get enhanced positions",
            "error": str(e)
        })


@app.get("/api/v1/positions/db")
async def get_stored_positions(db: Session = Depends(get_db)):
    """Get positions stored in the database"""
    try:
        positions = db.query(Position).filter(Position.is_active == True).all()
        
        return {
            "status": "success",
            "positions_count": len(positions),
            "positions": [
                {
                    "id": pos.id,
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "size": float(pos.size),
                    "entry_price": float(pos.entry_price),
                    "current_price": float(pos.current_price),
                    "pnl_amount": float(pos.pnl_amount) if pos.pnl_amount else 0,
                    "pnl_percentage": float(pos.pnl_percentage) if pos.pnl_percentage else 0,
                    "leverage": pos.leverage,
                    "last_updated": pos.last_updated.isoformat() if pos.last_updated else None
                }
                for pos in positions
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching stored positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to fetch stored positions",
            "error": str(e)
        })


# Portfolio Aggregation & Analytics Endpoints

@app.get("/api/v1/portfolio/comprehensive")
async def get_comprehensive_portfolio(
    include_analysis: bool = True,
    validate_results: bool = True,
    enable_technical_analysis: bool = True,
    enable_sentiment_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get comprehensive portfolio view with aggregation and analytics"""
    try:
        async with create_bybit_client() as client:
            logger.info("Fetching comprehensive portfolio data...")
            
            # Fetch all active positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "message": "No active positions found",
                    "portfolio_summary": {},
                    "analytics": {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Initialize aggregation service
            aggregation_service = PortfolioAggregationService(client, db, validation_tolerance=0.01)
            
            # Get comprehensive portfolio summary
            portfolio_summary = await aggregation_service.aggregate_portfolio(
                active_positions,
                include_analysis=include_analysis,
                validate_results=validate_results
            )
            
            # Initialize analytics engine
            analytics_engine = PortfolioAnalyticsEngine(client, db)
            
            # Calculate analytics
            analytics = await analytics_engine.calculate_comprehensive_analytics(active_positions)
            
            return {
                "status": "success",
                "portfolio_summary": {
                    "total_positions": portfolio_summary.total_positions,
                    "active_positions": portfolio_summary.active_positions,
                    "total_unrealized_pnl": float(portfolio_summary.total_unrealized_pnl),
                    "total_realized_pnl": float(portfolio_summary.total_realized_pnl),
                    "net_exposure": float(portfolio_summary.net_exposure),
                    "total_exposure": float(portfolio_summary.total_exposure),
                    "portfolio_value": float(portfolio_summary.portfolio_value),
                    "avg_leverage": portfolio_summary.avg_leverage,
                    "portfolio_risk_score": portfolio_summary.portfolio_risk_score,
                    "long_summary": {
                        "count": portfolio_summary.long_summary.count,
                        "total_value": float(portfolio_summary.long_summary.total_value),
                        "unrealized_pnl": float(portfolio_summary.long_summary.unrealized_pnl),
                        "avg_leverage": portfolio_summary.long_summary.avg_leverage,
                        "risk_distribution": portfolio_summary.long_summary.risk_distribution,
                        "top_positions": portfolio_summary.long_summary.top_positions[:5]
                    },
                    "short_summary": {
                        "count": portfolio_summary.short_summary.count,
                        "total_value": float(portfolio_summary.short_summary.total_value),
                        "unrealized_pnl": float(portfolio_summary.short_summary.unrealized_pnl),
                        "avg_leverage": portfolio_summary.short_summary.avg_leverage,
                        "risk_distribution": portfolio_summary.short_summary.risk_distribution,
                        "top_positions": portfolio_summary.short_summary.top_positions[:5]
                    },
                    "net_exposure_data": {
                        "long_exposure": float(portfolio_summary.net_exposure_data.long_exposure),
                        "short_exposure": float(portfolio_summary.net_exposure_data.short_exposure),
                        "net_exposure": float(portfolio_summary.net_exposure_data.net_exposure),
                        "net_ratio": portfolio_summary.net_exposure_data.net_ratio,
                        "exposure_balance": portfolio_summary.net_exposure_data.exposure_balance
                    },
                    "symbol_allocation": portfolio_summary.symbol_allocation,
                    "validation_status": {
                        "is_valid": portfolio_summary.validation_status.is_valid,
                        "validation_score": portfolio_summary.validation_status.validation_score,
                        "discrepancies_count": len(portfolio_summary.validation_status.discrepancies),
                        "warnings": portfolio_summary.validation_status.validation_warnings
                    }
                },
                "analytics": {
                    "performance_metrics": {
                        "sharpe_ratio": analytics.performance_metrics.sharpe_ratio,
                        "max_drawdown": analytics.performance_metrics.max_drawdown,
                        "win_rate": analytics.performance_metrics.win_rate,
                        "profit_factor": analytics.performance_metrics.profit_factor,
                        "total_trades": analytics.performance_metrics.total_trades,
                        "profitable_trades": analytics.performance_metrics.profitable_trades
                    },
                    "risk_metrics": {
                        "value_at_risk_95": analytics.risk_metrics.value_at_risk_95,
                        "concentration_index": analytics.risk_metrics.concentration_index,
                        "leverage_risk_score": analytics.risk_metrics.leverage_risk_score,
                        "correlation_risk_score": analytics.risk_metrics.correlation_risk_score
                    },
                    "correlation_matrix": analytics.correlation_matrix,
                    "sector_allocation": analytics.sector_allocation,
                    "trend_analysis": analytics.trend_analysis,
                    "recommendations": analytics.recommendations
                },
                "calculation_time": {
                    "portfolio_duration": portfolio_summary.calculation_duration,
                    "analytics_duration": analytics.calculation_duration
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting comprehensive portfolio: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get comprehensive portfolio",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/long-positions")
async def get_long_positions(
    include_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get aggregated long positions with detailed analysis"""
    try:
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            # Filter long positions
            long_positions = [pos for pos in active_positions if pos.get("side", "").lower() in ["buy", "long"]]
            
            if not long_positions:
                return {
                    "status": "success",
                    "message": "No long positions found",
                    "long_summary": {},
                    "positions": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Initialize services
            aggregation_service = PortfolioAggregationService(client, db)
            
            # Enrich with analysis if requested
            if include_analysis:
                async with EnhancedPositionAnalysisService(
                    client, db, enable_technical_analysis=True, enable_sentiment_analysis=True
                ) as analysis_service:
                    long_positions = await analysis_service.analyze_all_positions(long_positions)
            
            # Create long summary
            long_summary = await aggregation_service._create_direction_summary(long_positions, "long")
            
            return {
                "status": "success",
                "long_summary": {
                    "count": long_summary.count,
                    "total_value": float(long_summary.total_value),
                    "unrealized_pnl": float(long_summary.unrealized_pnl),
                    "avg_leverage": long_summary.avg_leverage,
                    "weighted_avg_leverage": long_summary.weighted_avg_leverage,
                    "risk_distribution": long_summary.risk_distribution,
                    "pnl_distribution": long_summary.pnl_distribution,
                    "total_margin": float(long_summary.total_margin)
                },
                "positions": long_positions,
                "metadata": {
                    "analysis_included": include_analysis,
                    "calculation_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting long positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get long positions",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/short-positions")
async def get_short_positions(
    include_analysis: bool = True,
    db: Session = Depends(get_db)
):
    """Get aggregated short positions with detailed analysis"""
    try:
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            # Filter short positions
            short_positions = [pos for pos in active_positions if pos.get("side", "").lower() in ["sell", "short"]]
            
            if not short_positions:
                return {
                    "status": "success",
                    "message": "No short positions found",
                    "short_summary": {},
                    "positions": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Initialize services
            aggregation_service = PortfolioAggregationService(client, db)
            
            # Enrich with analysis if requested
            if include_analysis:
                async with EnhancedPositionAnalysisService(
                    client, db, enable_technical_analysis=True, enable_sentiment_analysis=True
                ) as analysis_service:
                    short_positions = await analysis_service.analyze_all_positions(short_positions)
            
            # Create short summary
            short_summary = await aggregation_service._create_direction_summary(short_positions, "short")
            
            return {
                "status": "success",
                "short_summary": {
                    "count": short_summary.count,
                    "total_value": float(short_summary.total_value),
                    "unrealized_pnl": float(short_summary.unrealized_pnl),
                    "avg_leverage": short_summary.avg_leverage,
                    "weighted_avg_leverage": short_summary.weighted_avg_leverage,
                    "risk_distribution": short_summary.risk_distribution,
                    "pnl_distribution": short_summary.pnl_distribution,
                    "total_margin": float(short_summary.total_margin)
                },
                "positions": short_positions,
                "metadata": {
                    "analysis_included": include_analysis,
                    "calculation_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting short positions: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get short positions",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/analytics")
async def get_portfolio_analytics(
    historical_days: int = 30,
    db: Session = Depends(get_db)
):
    """Get advanced portfolio analytics and correlations"""
    try:
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "message": "No positions for analytics",
                    "analytics": {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Initialize analytics engine
            analytics_engine = PortfolioAnalyticsEngine(client, db)
            
            # Calculate comprehensive analytics
            analytics = await analytics_engine.calculate_comprehensive_analytics(
                active_positions, historical_days
            )
            
            # Get historical performance
            historical_performance = await analytics_engine.get_historical_performance(historical_days)
            
            return {
                "status": "success",
                "analytics": {
                    "performance_metrics": {
                        "sharpe_ratio": analytics.performance_metrics.sharpe_ratio,
                        "max_drawdown": analytics.performance_metrics.max_drawdown,
                        "win_rate": analytics.performance_metrics.win_rate,
                        "profit_factor": analytics.performance_metrics.profit_factor,
                        "avg_trade_duration": analytics.performance_metrics.avg_trade_duration,
                        "total_trades": analytics.performance_metrics.total_trades,
                        "profitable_trades": analytics.performance_metrics.profitable_trades,
                        "largest_win": analytics.performance_metrics.largest_win,
                        "largest_loss": analytics.performance_metrics.largest_loss,
                        "volatility": analytics.performance_metrics.volatility
                    },
                    "risk_metrics": {
                        "value_at_risk_95": analytics.risk_metrics.value_at_risk_95,
                        "value_at_risk_99": analytics.risk_metrics.value_at_risk_99,
                        "expected_shortfall": analytics.risk_metrics.expected_shortfall,
                        "maximum_drawdown": analytics.risk_metrics.maximum_drawdown,
                        "sortino_ratio": analytics.risk_metrics.sortino_ratio,
                        "concentration_index": analytics.risk_metrics.concentration_index,
                        "leverage_risk_score": analytics.risk_metrics.leverage_risk_score,
                        "correlation_risk_score": analytics.risk_metrics.correlation_risk_score
                    },
                    "correlation_matrix": analytics.correlation_matrix,
                    "sector_allocation": analytics.sector_allocation,
                    "risk_adjusted_returns": analytics.risk_adjusted_returns,
                    "trend_analysis": analytics.trend_analysis,
                    "recommendations": analytics.recommendations
                },
                "historical_performance": historical_performance,
                "metadata": {
                    "calculation_duration": analytics.calculation_duration,
                    "historical_days": historical_days,
                    "last_calculated": analytics.last_calculated.isoformat()
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting portfolio analytics: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get portfolio analytics",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/validation")
async def validate_portfolio_calculations(db: Session = Depends(get_db)):
    """Validate portfolio calculations and return discrepancy report"""
    try:
        async with create_bybit_client() as client:
            # Fetch positions
            all_positions_data = await client.get_positions(category="linear", settle_coin="USDT")
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "message": "No positions to validate",
                    "validation_results": {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Initialize aggregation service with strict validation
            aggregation_service = PortfolioAggregationService(client, db, validation_tolerance=0.005)
            
            # Perform aggregation with validation
            portfolio_summary = await aggregation_service.aggregate_portfolio(
                active_positions,
                include_analysis=False,  # Skip analysis for faster validation
                validate_results=True
            )
            
            # Get detailed validation results
            validation_status = portfolio_summary.validation_status
            
            return {
                "status": "success",
                "validation_results": {
                    "is_valid": validation_status.is_valid,
                    "validation_score": validation_status.validation_score,
                    "total_checks": validation_status.total_checks,
                    "passed_checks": validation_status.passed_checks,
                    "discrepancies": [
                        {
                            "field": d.field,
                            "expected": d.expected,
                            "actual": d.actual,
                            "difference": d.difference,
                            "severity": d.severity,
                            "description": d.description
                        } for d in validation_status.discrepancies
                    ],
                    "warnings": validation_status.validation_warnings,
                    "last_validated": validation_status.last_validated.isoformat()
                },
                "summary_stats": {
                    "total_positions_checked": len(active_positions),
                    "critical_issues": len([d for d in validation_status.discrepancies if d.severity == "critical"]),
                    "warnings": len([d for d in validation_status.discrepancies if d.severity == "warning"]),
                    "errors": len([d for d in validation_status.discrepancies if d.severity == "error"])
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error validating portfolio: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to validate portfolio calculations",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/correlation/{symbol1}/{symbol2}")
async def get_position_correlation(
    symbol1: str,
    symbol2: str,
    timeframe: str = "30d",
    db: Session = Depends(get_db)
):
    """Get correlation data between two specific symbols"""
    try:
        async with create_bybit_client() as client:
            analytics_engine = PortfolioAnalyticsEngine(client, db)
            
            # Get stored correlation data
            correlation_data = await analytics_engine.get_correlation_data(symbol1, symbol2, timeframe)
            
            if correlation_data:
                return {
                    "status": "success",
                    "correlation_data": {
                        "symbol_1": correlation_data.symbol_1,
                        "symbol_2": correlation_data.symbol_2,
                        "correlation_coefficient": correlation_data.correlation_coefficient,
                        "correlation_strength": correlation_data.correlation_strength,
                        "data_points": correlation_data.data_points,
                        "timeframe": correlation_data.timeframe,
                        "statistical_significance": correlation_data.p_value
                    },
                    "interpretation": {
                        "direction": "positive" if correlation_data.correlation_coefficient > 0 else "negative",
                        "strength_description": {
                            "STRONG": "These assets move very similarly",
                            "MODERATE": "These assets show some correlation",
                            "WEAK": "These assets show minimal correlation"
                        }.get(correlation_data.correlation_strength, "Correlation strength unknown")
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "status": "success",
                    "message": f"No correlation data found for {symbol1}-{symbol2}",
                    "correlation_data": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
    except Exception as e:
        logger.error(f"Error getting correlation for {symbol1}-{symbol2}: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": f"Failed to get correlation data for {symbol1}-{symbol2}",
            "error": str(e)
        })


@app.get("/api/v1/portfolio/historical")
async def get_historical_portfolio_performance(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get historical portfolio performance data"""
    try:
        async with create_bybit_client() as client:
            analytics_engine = PortfolioAnalyticsEngine(client, db)
            
            # Get historical performance data
            historical_data = await analytics_engine.get_historical_performance(days)
            
            return {
                "status": "success",
                "historical_data": historical_data,
                "metadata": {
                    "days_requested": days,
                    "data_points": len(historical_data.get("portfolio_value_timeline", [])),
                    "performance_points": len(historical_data.get("performance_timeline", []))
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting historical portfolio performance: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get historical portfolio performance",
            "error": str(e)
        })


# Debug Endpoints

@app.get("/api/v1/debug/positions")
async def debug_positions():
    """Debug endpoint to see exactly what positions we're getting from Bybit"""
    try:
        async with create_bybit_client() as client:
            debug_info = {}
            
            # Test 1: All positions without any filter
            try:
                all_positions = await client.get_positions(category="linear")
                active_all = [pos for pos in all_positions if float(pos.get("size", 0)) > 0]
                debug_info["all_positions"] = {
                    "total": len(all_positions),
                    "active": len(active_all),
                    "sample_active": [pos['symbol'] for pos in active_all[:10]] if active_all else []
                }
            except Exception as e:
                debug_info["all_positions"] = {"error": str(e)}
            
            # Test 2: USDT settled positions
            try:
                usdt_positions = await client.get_positions(category="linear", settle_coin="USDT")
                active_usdt = [pos for pos in usdt_positions if float(pos.get("size", 0)) > 0]
                debug_info["usdt_positions"] = {
                    "total": len(usdt_positions),
                    "active": len(active_usdt),
                    "sample_active": [pos['symbol'] for pos in active_usdt[:10]] if active_usdt else []
                }
            except Exception as e:
                debug_info["usdt_positions"] = {"error": str(e)}
            
            # Test 3: BTC settled positions
            try:
                btc_positions = await client.get_positions(category="linear", settle_coin="BTC")
                active_btc = [pos for pos in btc_positions if float(pos.get("size", 0)) > 0]
                debug_info["btc_positions"] = {
                    "total": len(btc_positions),
                    "active": len(active_btc),
                    "sample_active": [pos['symbol'] for pos in active_btc[:10]] if active_btc else []
                }
            except Exception as e:
                debug_info["btc_positions"] = {"error": str(e)}
            
            # Test 4: Check account info for context
            try:
                account_info = await client.get_account_info()
                debug_info["account_info"] = {
                    "accountType": account_info.get("accountType", "unknown"),
                    "marginMode": account_info.get("marginMode", "unknown"),
                    "updatedTime": account_info.get("updatedTime", "unknown")
                }
            except Exception as e:
                debug_info["account_info"] = {"error": str(e)}
            
            return {
                "status": "success",
                "debug_info": debug_info,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Debug positions error: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to debug positions",
            "error": str(e)
        })


# Market Data Endpoints

@app.post("/api/v1/market-data/fetch")
async def fetch_market_data(
    background_tasks: BackgroundTasks,
    intervals: List[str] = ["1h", "4h", "1d"],
    days_back: int = 30
):
    """Fetch and store market data for all active symbols"""
    task_id = f"market_data_{uuid.uuid4().hex[:8]}"
    
    async def fetch_data():
        try:
            async with MarketDataService() as service:
                await service.fetch_and_store_all_symbols(
                    intervals=intervals,
                    days_back=days_back,
                    task_id=task_id
                )
        except Exception as e:
            logger.error(f"Background market data fetch failed: {e}")
            tracker = get_progress_tracker()
            tracker.error_task(task_id, str(e))
    
    # Start background task
    background_tasks.add_task(fetch_data)
    
    return {
        "status": "started",
        "message": "Market data fetch started in background",
        "task_id": task_id,
        "intervals": intervals,
        "days_back": days_back,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/market-data/symbols")
async def get_active_symbols(db: Session = Depends(get_db)):
    """Get all symbols from active positions"""
    try:
        async with MarketDataService() as service:
            symbols = await service.get_active_symbols(db)
            return {
                "status": "success",
                "symbols_count": len(symbols),
                "symbols": symbols,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting active symbols: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": "Failed to get active symbols",
            "error": str(e)
        })


@app.get("/api/v1/market-data/{symbol}")
async def get_market_data(
    symbol: str,
    interval: str = "1h",
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get stored market data for a specific symbol"""
    try:
        service = MarketDataService()
        market_data = service.get_stored_market_data(
            symbol=symbol.upper(),
            interval=interval,
            limit=limit,
            db=db
        )
        
        # Convert to response format
        data_points = []
        for data in market_data:
            data_points.append({
                "timestamp": data.timestamp.isoformat(),
                "open": float(data.open_price),
                "high": float(data.high_price),
                "low": float(data.low_price),
                "close": float(data.close_price),
                "volume": float(data.volume)
            })
        
        return {
            "status": "success",
            "symbol": symbol.upper(),
            "interval": interval,
            "data_count": len(data_points),
            "data": data_points,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": f"Failed to get market data for {symbol}",
            "error": str(e)
        })


@app.get("/api/v1/market-data/{symbol}/latest-price")
async def get_latest_price(symbol: str):
    """Get the latest price for a symbol from Bybit"""
    try:
        async with MarketDataService() as service:
            price = await service.get_latest_price(symbol.upper())
            
            if price is None:
                raise HTTPException(status_code=404, detail={
                    "status": "error",
                    "message": f"Price not found for {symbol}",
                    "symbol": symbol.upper()
                })
            
            return {
                "status": "success",
                "symbol": symbol.upper(),
                "price": float(price),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail={
            "status": "error",
            "message": f"Failed to get latest price for {symbol}",
            "error": str(e)
        })


@app.post("/api/v1/market-data/update")
async def update_market_data(background_tasks: BackgroundTasks):
    """Update market data for current positions (shorter timeframe)"""
    task_id = f"update_{uuid.uuid4().hex[:8]}"
    
    async def update_data():
        try:
            async with MarketDataService() as service:
                await service.fetch_and_store_all_symbols(
                    intervals=["1h", "4h", "1d"],
                    days_back=7,  # Shorter period for updates
                    task_id=task_id
                )
        except Exception as e:
            logger.error(f"Background market data update failed: {e}")
            tracker = get_progress_tracker()
            tracker.error_task(task_id, str(e))
    
    # Start background task
    background_tasks.add_task(update_data)
    
    return {
        "status": "started",
        "message": "Market data update started in background",
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Progress Tracking Endpoints

@app.get("/api/v1/progress")
async def get_all_progress():
    """Get progress for all tasks"""
    tracker = get_progress_tracker()
    return {
        "status": "success",
        "data": tracker.to_dict(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/progress/{task_id}")
async def get_task_progress(task_id: str):
    """Get progress for a specific task"""
    tracker = get_progress_tracker()
    task = tracker.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail={
            "status": "error",
            "message": f"Task {task_id} not found"
        })
    
    return {
        "status": "success",
        "data": tracker.to_dict(task_id),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/progress/{task_id}/updates")
async def get_task_updates(task_id: str, limit: int = 10):
    """Get recent updates for a specific task"""
    tracker = get_progress_tracker()
    updates = tracker.get_recent_updates(task_id, limit)
    
    return {
        "status": "success",
        "task_id": task_id,
        "updates": [
            {
                "step": update.step,
                "progress": update.progress,
                "message": update.message,
                "timestamp": update.timestamp,
                "details": update.details
            }
            for update in updates
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level=settings.app.log_level.lower()
    ) 