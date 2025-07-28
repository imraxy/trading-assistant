"""
Market Data Service - Fetches and manages historical price data
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from decimal import Decimal

from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.database.models import MarketData, Position
from app.api.bybit_client import BybitClient
from app.config import get_settings
from app.services.progress_tracker import get_progress_tracker

logger = logging.getLogger(__name__)

class MarketDataService:
    """Service for fetching and managing market data"""
    
    def __init__(self):
        self.settings = get_settings()
        self.bybit_client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.bybit_client = BybitClient(
            api_key=self.settings.bybit.api_key,
            api_secret=self.settings.bybit.api_secret,
            testnet=self.settings.bybit.testnet
        )
        await self.bybit_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.bybit_client:
            await self.bybit_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def get_active_symbols(self, db: Session) -> List[str]:
        """Get all unique symbols from active positions (fetch fresh from Bybit with pagination)"""
        try:
            logger.info("Fetching ALL USDT-settled positions with pagination...")
            
            # Fetch ALL USDT positions with pagination (this will get all 190+ positions)
            all_positions = await self.bybit_client.get_positions(
                category="linear",
                settle_coin="USDT"
            )
            
            logger.info(f"Retrieved {len(all_positions)} total USDT positions")
            
            # Filter only positions with size > 0
            active_positions = [pos for pos in all_positions if float(pos.get("size", 0)) > 0]
            
            # Extract unique symbols
            symbols = list(set([pos["symbol"] for pos in active_positions]))
            
            logger.info(f"FINAL RESULT: {len(active_positions)} active positions across {len(symbols)} unique symbols")
            
            # Log first 20 symbols for verification
            if symbols:
                logger.info(f"Sample symbols: {symbols[:20]}")
                if len(symbols) > 20:
                    logger.info(f"... and {len(symbols) - 20} more symbols")
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error fetching active symbols from Bybit: {e}")
            # Fallback to database if API fails
            positions = db.query(Position).filter(Position.size > 0).all()
            symbols = list(set([pos.symbol for pos in positions]))
            logger.info(f"Fallback: Found {len(symbols)} symbols from database: {symbols}")
            return symbols
    
    async def fetch_market_data_for_symbol(
        self, 
        symbol: str, 
        interval: str = "1h",
        limit: int = 100,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """Fetch historical market data for a specific symbol"""
        try:
            # Calculate start time (days back from now)
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
            
            logger.info(f"Fetching {interval} data for {symbol} ({days_back} days)")
            
            klines = await self.bybit_client.get_kline_data(
                category="linear",
                symbol=symbol,
                interval=interval,
                start=start_time,
                end=end_time,
                limit=limit
            )
            
            logger.info(f"Retrieved {len(klines)} candles for {symbol}")
            return klines
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return []
    
    async def store_market_data(self, symbol: str, interval: str, klines: List[Dict[str, Any]], db: Session):
        """Store market data in database"""
        try:
            stored_count = 0
            for kline in klines:
                timestamp = datetime.fromtimestamp(int(kline['startTime']) / 1000)
                
                # Check if data already exists
                existing = db.query(MarketData).filter(
                    MarketData.symbol == symbol,
                    MarketData.timeframe == interval,
                    MarketData.timestamp == timestamp
                ).first()
                
                if not existing:
                    market_data = MarketData(
                        symbol=symbol,
                        timeframe=interval,
                        timestamp=timestamp,
                        open_price=Decimal(str(kline['open'])),
                        high_price=Decimal(str(kline['high'])),
                        low_price=Decimal(str(kline['low'])),
                        close_price=Decimal(str(kline['close'])),
                        volume=Decimal(str(kline['volume'])),
                        created_at=datetime.utcnow()
                    )
                    db.add(market_data)
                    stored_count += 1
            
            if stored_count > 0:
                db.commit()
                logger.info(f"Stored {stored_count} new candles for {symbol} ({interval})")
            else:
                logger.info(f"No new data to store for {symbol} ({interval})")
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing market data for {symbol}: {e}")
            raise
    
    async def fetch_and_store_all_symbols(
        self, 
        intervals: List[str] = ["1h", "4h", "1d"],
        days_back: int = 30,
        task_id: str = None
    ):
        """Fetch and store market data for all active symbols across multiple timeframes"""
        db = SessionLocal()
        tracker = get_progress_tracker()
        
        try:
            # Get active symbols from positions
            symbols = await self.get_active_symbols(db)
            
            if not symbols:
                logger.warning("No active symbols found in positions")
                if task_id:
                    tracker.error_task(task_id, "No active symbols found")
                return
            
            total_operations = len(symbols) * len(intervals)
            completed = 0
            
            # Start progress tracking
            if task_id:
                tracker.start_task(
                    task_id, 
                    f"Fetch Market Data ({len(symbols)} symbols, {len(intervals)} timeframes)",
                    total_operations
                )
            
            logger.info(f"Starting market data collection for {len(symbols)} symbols across {len(intervals)} timeframes")
            
            for symbol in symbols:
                for interval in intervals:
                    try:
                        # Update progress
                        if task_id:
                            progress = completed / total_operations
                            tracker.update_progress(
                                task_id,
                                f"Fetching {symbol} {interval}",
                                progress,
                                f"Processing {symbol} ({interval}) - {completed}/{total_operations}",
                                {"symbol": symbol, "interval": interval}
                            )
                        
                        # Fetch market data
                        klines = await self.fetch_market_data_for_symbol(
                            symbol=symbol,
                            interval=interval,
                            days_back=days_back
                        )
                        
                        # Store in database
                        if klines:
                            await self.store_market_data(symbol, interval, klines, db)
                        
                        completed += 1
                        logger.info(f"Progress: {completed}/{total_operations} completed ({symbol} {interval})")
                        
                        # Small delay to respect rate limits
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(f"Failed to process {symbol} {interval}: {e}")
                        completed += 1  # Still count as processed
                        continue
            
            # Mark as completed
            if task_id:
                tracker.complete_task(
                    task_id, 
                    f"Successfully collected data for {len(symbols)} symbols across {len(intervals)} timeframes"
                )
            
            logger.info(f"Market data collection completed: {completed}/{total_operations} successful")
            
        except Exception as e:
            logger.error(f"Error in fetch_and_store_all_symbols: {e}")
            if task_id:
                tracker.error_task(task_id, str(e))
            raise
        finally:
            db.close()
    
    async def get_latest_price(self, symbol: str) -> Optional[Decimal]:
        """Get the latest price for a symbol"""
        try:
            tickers = await self.bybit_client.get_tickers(category="linear", symbol=symbol)
            if tickers:
                return Decimal(str(tickers[0]['lastPrice']))
            return None
        except Exception as e:
            logger.error(f"Error getting latest price for {symbol}: {e}")
            return None
    
    def get_stored_market_data(
        self, 
        symbol: str, 
        interval: str, 
        limit: int = 100,
        db: Session = None
    ) -> List[MarketData]:
        """Get stored market data from database"""
        if db is None:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False
        
        try:
            market_data = db.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.timeframe == interval
            ).order_by(MarketData.timestamp.desc()).limit(limit).all()
            
            return market_data
        finally:
            if close_db:
                db.close()
    


# Global service instance
market_data_service = None

async def get_market_data_service() -> MarketDataService:
    """Get market data service instance"""
    global market_data_service
    if market_data_service is None:
        market_data_service = MarketDataService()
    return market_data_service 