"""
Real-time Update Service

Manages real-time position updates, WebSocket connections, and error handling
for the comprehensive trading dashboard.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import weakref

from app.api.bybit_client import BybitClient, BybitAPIError
from app.services.portfolio_aggregation_service import PortfolioAggregationService
from app.services.portfolio_analytics_engine import PortfolioAnalyticsEngine
from app.config import get_settings
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class UpdateType(Enum):
    """Types of real-time updates"""
    POSITION_UPDATE = "position_update"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    ANALYTICS_UPDATE = "analytics_update"
    VALIDATION_RESULT = "validation_result"
    ERROR_NOTIFICATION = "error_notification"
    CONNECTION_STATUS = "connection_status"

@dataclass
class UpdateMessage:
    """Real-time update message structure"""
    type: UpdateType
    data: Dict[str, Any]
    timestamp: datetime
    client_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

@dataclass
class ConnectionState:
    """Client connection state"""
    client_id: str
    connected_at: datetime
    last_heartbeat: datetime
    subscriptions: List[UpdateType]
    error_count: int = 0
    last_error: Optional[str] = None

class RealtimeUpdateService:
    """Manages real-time updates and client connections"""
    
    def __init__(self, bybit_client: BybitClient, db: Session):
        self.bybit_client = bybit_client
        self.db = db
        self.settings = get_settings()
        
        # Client management
        self.connections: Dict[str, ConnectionState] = {}
        self.update_callbacks: Dict[str, Callable] = {}
        
        # Services
        self.aggregation_service = None
        self.analytics_engine = None
        
        # Update state
        self.last_portfolio_update = None
        self.last_analytics_update = None
        self.update_queue: asyncio.Queue = asyncio.Queue()
        
        # Error handling
        self.max_retry_attempts = 3
        self.retry_delay_base = 2  # seconds
        self.connection_timeout = 30  # seconds
        
        # Background tasks
        self._update_task = None
        self._heartbeat_task = None
        self._cleanup_task = None
        
    async def start(self):
        """Start the real-time update service"""
        try:
            logger.info("Starting real-time update service...")
            
            # Initialize services
            self.aggregation_service = PortfolioAggregationService(
                self.bybit_client, self.db, validation_tolerance=0.01
            )
            self.analytics_engine = PortfolioAnalyticsEngine(self.bybit_client, self.db)
            
            # Start background tasks
            self._update_task = asyncio.create_task(self._update_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("Real-time update service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start real-time update service: {e}")
            raise
    
    async def stop(self):
        """Stop the real-time update service"""
        try:
            logger.info("Stopping real-time update service...")
            
            # Cancel background tasks
            for task in [self._update_task, self._heartbeat_task, self._cleanup_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Notify all clients of shutdown
            await self._broadcast_message(UpdateMessage(
                type=UpdateType.CONNECTION_STATUS,
                data={"status": "service_shutdown", "message": "Service is shutting down"},
                timestamp=datetime.now(timezone.utc)
            ))
            
            # Clear connections
            self.connections.clear()
            self.update_callbacks.clear()
            
            logger.info("Real-time update service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping real-time update service: {e}")
    
    def register_client(self, client_id: str, 
                       subscriptions: List[UpdateType],
                       callback: Callable[[UpdateMessage], None]) -> bool:
        """Register a new client for real-time updates"""
        try:
            if client_id in self.connections:
                logger.warning(f"Client {client_id} already registered, updating...")
            
            self.connections[client_id] = ConnectionState(
                client_id=client_id,
                connected_at=datetime.now(timezone.utc),
                last_heartbeat=datetime.now(timezone.utc),
                subscriptions=subscriptions
            )
            
            # Store callback using weak reference to prevent memory leaks
            self.update_callbacks[client_id] = callback
            
            logger.info(f"Client {client_id} registered with subscriptions: {[s.value for s in subscriptions]}")
            
            # Send initial connection confirmation
            asyncio.create_task(self._send_to_client(client_id, UpdateMessage(
                type=UpdateType.CONNECTION_STATUS,
                data={"status": "connected", "client_id": client_id, "subscriptions": [s.value for s in subscriptions]},
                timestamp=datetime.now(timezone.utc)
            )))
            
            return True
            
        except Exception as e:
            logger.error(f"Error registering client {client_id}: {e}")
            return False
    
    def unregister_client(self, client_id: str) -> bool:
        """Unregister a client from real-time updates"""
        try:
            if client_id in self.connections:
                del self.connections[client_id]
                logger.info(f"Client {client_id} unregistered")
            
            if client_id in self.update_callbacks:
                del self.update_callbacks[client_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering client {client_id}: {e}")
            return False
    
    async def heartbeat(self, client_id: str) -> bool:
        """Update client heartbeat"""
        try:
            if client_id in self.connections:
                self.connections[client_id].last_heartbeat = datetime.now(timezone.utc)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating heartbeat for {client_id}: {e}")
            return False
    
    async def request_portfolio_update(self, client_id: Optional[str] = None, 
                                     include_analytics: bool = True) -> bool:
        """Request immediate portfolio update"""
        try:
            message = UpdateMessage(
                type=UpdateType.PORTFOLIO_SUMMARY,
                data={"request_type": "immediate", "include_analytics": include_analytics},
                timestamp=datetime.now(timezone.utc),
                client_id=client_id
            )
            
            await self.update_queue.put(message)
            logger.info(f"Portfolio update requested by client {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error requesting portfolio update: {e}")
            return False
    
    async def _update_loop(self):
        """Main update loop that processes real-time updates"""
        logger.info("Starting update loop...")
        
        while True:
            try:
                # Process update queue
                try:
                    message = await asyncio.wait_for(self.update_queue.get(), timeout=1.0)
                    await self._process_update_message(message)
                except asyncio.TimeoutError:
                    pass
                
                # Periodic portfolio updates (every 30 seconds)
                now = datetime.now(timezone.utc)
                if (not self.last_portfolio_update or 
                    (now - self.last_portfolio_update).total_seconds() >= 30):
                    
                    await self._fetch_and_broadcast_portfolio_update()
                    self.last_portfolio_update = now
                
                # Periodic analytics updates (every 5 minutes)
                if (not self.last_analytics_update or 
                    (now - self.last_analytics_update).total_seconds() >= 300):
                    
                    await self._fetch_and_broadcast_analytics_update()
                    self.last_analytics_update = now
                
                await asyncio.sleep(0.1)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _process_update_message(self, message: UpdateMessage):
        """Process individual update message"""
        try:
            if message.type == UpdateType.PORTFOLIO_SUMMARY:
                await self._fetch_and_broadcast_portfolio_update(
                    client_id=message.client_id,
                    include_analytics=message.data.get("include_analytics", True)
                )
            elif message.type == UpdateType.ANALYTICS_UPDATE:
                await self._fetch_and_broadcast_analytics_update(client_id=message.client_id)
            elif message.type == UpdateType.VALIDATION_RESULT:
                await self._fetch_and_broadcast_validation_result(client_id=message.client_id)
            
        except Exception as e:
            logger.error(f"Error processing update message: {e}")
            await self._send_error_notification(
                message.client_id, 
                f"Failed to process update: {str(e)}"
            )
    
    async def _fetch_and_broadcast_portfolio_update(self, 
                                                   client_id: Optional[str] = None,
                                                   include_analytics: bool = False):
        """Fetch fresh portfolio data and broadcast to clients"""
        try:
            # Fetch positions from Bybit
            all_positions_data = await self.bybit_client.get_positions(
                category="linear", settle_coin="USDT"
            )
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if not active_positions:
                update_data = {
                    "portfolio_summary": {},
                    "message": "No active positions found",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                # Get portfolio summary
                portfolio_summary = await self.aggregation_service.aggregate_portfolio(
                    active_positions, 
                    include_analysis=include_analytics,
                    validate_results=True
                )
                
                update_data = {
                    "portfolio_summary": {
                        "total_positions": portfolio_summary.total_positions,
                        "active_positions": portfolio_summary.active_positions,
                        "total_unrealized_pnl": float(portfolio_summary.total_unrealized_pnl),
                        "net_exposure": float(portfolio_summary.net_exposure),
                        "portfolio_value": float(portfolio_summary.portfolio_value),
                        "avg_leverage": portfolio_summary.avg_leverage,
                        "portfolio_risk_score": portfolio_summary.portfolio_risk_score,
                        "long_summary": {
                            "count": portfolio_summary.long_summary.count,
                            "total_value": float(portfolio_summary.long_summary.total_value),
                            "unrealized_pnl": float(portfolio_summary.long_summary.unrealized_pnl),
                            "avg_leverage": portfolio_summary.long_summary.avg_leverage,
                            "risk_distribution": portfolio_summary.long_summary.risk_distribution
                        },
                        "short_summary": {
                            "count": portfolio_summary.short_summary.count,
                            "total_value": float(portfolio_summary.short_summary.total_value),
                            "unrealized_pnl": float(portfolio_summary.short_summary.unrealized_pnl),
                            "avg_leverage": portfolio_summary.short_summary.avg_leverage,
                            "risk_distribution": portfolio_summary.short_summary.risk_distribution
                        },
                        "net_exposure_data": {
                            "long_exposure": float(portfolio_summary.net_exposure_data.long_exposure),
                            "short_exposure": float(portfolio_summary.net_exposure_data.short_exposure),
                            "net_exposure": float(portfolio_summary.net_exposure_data.net_exposure),
                            "net_ratio": portfolio_summary.net_exposure_data.net_ratio,
                            "exposure_balance": portfolio_summary.net_exposure_data.exposure_balance
                        },
                        "validation_status": {
                            "is_valid": portfolio_summary.validation_status.is_valid,
                            "validation_score": portfolio_summary.validation_status.validation_score,
                            "discrepancies_count": len(portfolio_summary.validation_status.discrepancies)
                        }
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "calculation_duration": portfolio_summary.calculation_duration
                }
            
            message = UpdateMessage(
                type=UpdateType.PORTFOLIO_SUMMARY,
                data=update_data,
                timestamp=datetime.now(timezone.utc),
                client_id=client_id
            )
            
            if client_id:
                await self._send_to_client(client_id, message)
            else:
                await self._broadcast_message(message, [UpdateType.PORTFOLIO_SUMMARY])
            
            logger.debug("Portfolio update broadcasted successfully")
            
        except BybitAPIError as e:
            logger.error(f"Bybit API error during portfolio update: {e}")
            await self._send_error_notification(
                client_id, 
                f"API Error: {str(e)}", 
                recoverable=True
            )
        except Exception as e:
            logger.error(f"Error fetching portfolio update: {e}")
            await self._send_error_notification(
                client_id, 
                f"Portfolio update failed: {str(e)}"
            )
    
    async def _fetch_and_broadcast_analytics_update(self, client_id: Optional[str] = None):
        """Fetch analytics and broadcast to clients"""
        try:
            # Fetch current positions for analytics
            all_positions_data = await self.bybit_client.get_positions(
                category="linear", settle_coin="USDT"
            )
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if active_positions:
                # Calculate analytics
                analytics = await self.analytics_engine.calculate_comprehensive_analytics(
                    active_positions, historical_days=30
                )
                
                update_data = {
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
                        "sector_allocation": analytics.sector_allocation,
                        "recommendations": analytics.recommendations
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "calculation_duration": analytics.calculation_duration
                }
            else:
                update_data = {
                    "analytics": {},
                    "message": "No positions for analytics",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            message = UpdateMessage(
                type=UpdateType.ANALYTICS_UPDATE,
                data=update_data,
                timestamp=datetime.now(timezone.utc),
                client_id=client_id
            )
            
            if client_id:
                await self._send_to_client(client_id, message)
            else:
                await self._broadcast_message(message, [UpdateType.ANALYTICS_UPDATE])
            
            logger.debug("Analytics update broadcasted successfully")
            
        except Exception as e:
            logger.error(f"Error fetching analytics update: {e}")
            await self._send_error_notification(
                client_id, 
                f"Analytics update failed: {str(e)}"
            )
    
    async def _fetch_and_broadcast_validation_result(self, client_id: Optional[str] = None):
        """Fetch validation results and broadcast to clients"""
        try:
            # Fetch positions for validation
            all_positions_data = await self.bybit_client.get_positions(
                category="linear", settle_coin="USDT"
            )
            active_positions = [pos for pos in all_positions_data if float(pos.get("size", 0)) > 0]
            
            if active_positions:
                # Perform validation
                portfolio_summary = await self.aggregation_service.aggregate_portfolio(
                    active_positions, 
                    include_analysis=False,
                    validate_results=True
                )
                
                validation_status = portfolio_summary.validation_status
                
                update_data = {
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
                        "warnings": validation_status.validation_warnings
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                update_data = {
                    "validation_results": {},
                    "message": "No positions to validate",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            message = UpdateMessage(
                type=UpdateType.VALIDATION_RESULT,
                data=update_data,
                timestamp=datetime.now(timezone.utc),
                client_id=client_id
            )
            
            if client_id:
                await self._send_to_client(client_id, message)
            else:
                await self._broadcast_message(message, [UpdateType.VALIDATION_RESULT])
            
            logger.debug("Validation result broadcasted successfully")
            
        except Exception as e:
            logger.error(f"Error fetching validation result: {e}")
            await self._send_error_notification(
                client_id, 
                f"Validation failed: {str(e)}"
            )
    
    async def _send_error_notification(self, 
                                     client_id: Optional[str], 
                                     error_message: str,
                                     recoverable: bool = False):
        """Send error notification to client(s)"""
        try:
            error_data = {
                "error": error_message,
                "recoverable": recoverable,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "retry_suggested": recoverable
            }
            
            message = UpdateMessage(
                type=UpdateType.ERROR_NOTIFICATION,
                data=error_data,
                timestamp=datetime.now(timezone.utc),
                client_id=client_id,
                error=error_message
            )
            
            if client_id:
                await self._send_to_client(client_id, message)
                # Update error count for client
                if client_id in self.connections:
                    self.connections[client_id].error_count += 1
                    self.connections[client_id].last_error = error_message
            else:
                await self._broadcast_message(message, [UpdateType.ERROR_NOTIFICATION])
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    async def _send_to_client(self, client_id: str, message: UpdateMessage):
        """Send message to specific client"""
        try:
            if client_id in self.update_callbacks:
                callback = self.update_callbacks[client_id]
                # Execute callback in a separate task to prevent blocking
                asyncio.create_task(self._execute_callback(callback, message))
            else:
                logger.warning(f"No callback found for client {client_id}")
                
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
    
    async def _broadcast_message(self, 
                                message: UpdateMessage, 
                                subscription_filter: Optional[List[UpdateType]] = None):
        """Broadcast message to all subscribed clients"""
        try:
            for client_id, connection in self.connections.items():
                # Check if client is subscribed to this update type
                if (subscription_filter is None or 
                    any(sub_type in connection.subscriptions for sub_type in subscription_filter)):
                    
                    await self._send_to_client(client_id, message)
                    
        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")
    
    async def _execute_callback(self, callback: Callable, message: UpdateMessage):
        """Execute client callback safely"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error(f"Error executing client callback: {e}")
    
    async def _heartbeat_loop(self):
        """Monitor client heartbeats and disconnect stale connections"""
        logger.info("Starting heartbeat loop...")
        
        while True:
            try:
                now = datetime.now(timezone.utc)
                stale_clients = []
                
                for client_id, connection in self.connections.items():
                    time_since_heartbeat = (now - connection.last_heartbeat).total_seconds()
                    
                    if time_since_heartbeat > self.connection_timeout:
                        stale_clients.append(client_id)
                        logger.warning(f"Client {client_id} heartbeat timeout ({time_since_heartbeat}s)")
                
                # Remove stale clients
                for client_id in stale_clients:
                    self.unregister_client(client_id)
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(10)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of resources"""
        logger.info("Starting cleanup loop...")
        
        while True:
            try:
                # Clean up old queue messages (older than 5 minutes)
                # Note: This is a simplified approach, in production you might want a more sophisticated queue
                
                # Log current state
                logger.debug(f"Active connections: {len(self.connections)}")
                logger.debug(f"Queue size: {self.update_queue.qsize()}")
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "service_running": self._update_task and not self._update_task.done(),
            "active_connections": len(self.connections),
            "last_portfolio_update": self.last_portfolio_update.isoformat() if self.last_portfolio_update else None,
            "last_analytics_update": self.last_analytics_update.isoformat() if self.last_analytics_update else None,
            "queue_size": self.update_queue.qsize(),
            "connections": {
                client_id: {
                    "connected_at": conn.connected_at.isoformat(),
                    "last_heartbeat": conn.last_heartbeat.isoformat(),
                    "subscriptions": [s.value for s in conn.subscriptions],
                    "error_count": conn.error_count
                }
                for client_id, conn in self.connections.items()
            }
        }

# Global service instance
_realtime_service: Optional[RealtimeUpdateService] = None

async def get_realtime_service(bybit_client: BybitClient, db: Session) -> RealtimeUpdateService:
    """Get or create global realtime service instance"""
    global _realtime_service
    
    if _realtime_service is None:
        _realtime_service = RealtimeUpdateService(bybit_client, db)
        await _realtime_service.start()
    
    return _realtime_service

async def stop_realtime_service():
    """Stop global realtime service"""
    global _realtime_service
    
    if _realtime_service:
        await _realtime_service.stop()
        _realtime_service = None