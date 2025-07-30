"""
Portfolio Analytics Engine

Advanced analytics and correlation analysis for comprehensive portfolio insights.
Calculates performance metrics, risk analysis, and position correlations.
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.database.models import (
    MarketData, PositionCorrelation, PortfolioMetrics, 
    RealizedPnL, PortfolioSnapshot, Position
)
from app.api.bybit_client import BybitClient
from app.config import get_settings

logger = logging.getLogger(__name__)

@dataclass
class CorrelationData:
    """Position correlation analysis results"""
    symbol_1: str
    symbol_2: str
    correlation_coefficient: float
    correlation_strength: str
    p_value: float
    data_points: int
    timeframe: str

@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics"""
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_trade_duration: float
    total_trades: int
    profitable_trades: int
    largest_win: float
    largest_loss: float
    avg_win: float
    avg_loss: float
    volatility: float
    beta: float
    alpha: float

@dataclass
class RiskMetrics:
    """Portfolio risk analysis"""
    value_at_risk_95: float
    value_at_risk_99: float
    expected_shortfall: float
    maximum_drawdown: float
    downside_deviation: float
    sortino_ratio: float
    concentration_index: float
    leverage_risk_score: int
    correlation_risk_score: int

@dataclass
class PortfolioAnalytics:
    """Complete portfolio analytics"""
    performance_metrics: PerformanceMetrics
    risk_metrics: RiskMetrics
    correlation_matrix: Dict[str, Dict[str, float]]
    sector_allocation: Dict[str, float]
    risk_adjusted_returns: Dict[str, float]
    trend_analysis: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    last_calculated: datetime
    calculation_duration: float

class PortfolioAnalyticsEngine:
    """Advanced portfolio analytics and correlation analysis"""
    
    def __init__(self, bybit_client: BybitClient, db: Session):
        self.bybit_client = bybit_client
        self.db = db
        self.settings = get_settings()
        
    async def calculate_comprehensive_analytics(self, 
                                              positions: List[Dict[str, Any]],
                                              historical_days: int = 30) -> PortfolioAnalytics:
        """Calculate comprehensive portfolio analytics"""
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting comprehensive analytics calculation for {len(positions)} positions")
            
            # Get historical data for analysis
            symbols = list(set(pos.get("symbol", "") for pos in positions))
            historical_data = await self._fetch_historical_data(symbols, historical_days)
            
            # Calculate performance metrics
            performance_metrics = await self._calculate_performance_metrics(positions, historical_data)
            
            # Calculate risk metrics
            risk_metrics = await self._calculate_risk_metrics(positions, historical_data)
            
            # Calculate correlation matrix
            correlation_matrix = await self._calculate_correlation_matrix(symbols, historical_data)
            
            # Calculate sector allocation (simplified - by symbol prefix)
            sector_allocation = self._calculate_sector_allocation(positions)
            
            # Calculate risk-adjusted returns
            risk_adjusted_returns = await self._calculate_risk_adjusted_returns(positions, historical_data)
            
            # Perform trend analysis
            trend_analysis = await self._perform_trend_analysis(positions, historical_data)
            
            # Generate recommendations
            recommendations = await self._generate_analytics_recommendations(
                positions, performance_metrics, risk_metrics, correlation_matrix
            )
            
            analytics = PortfolioAnalytics(
                performance_metrics=performance_metrics,
                risk_metrics=risk_metrics,
                correlation_matrix=correlation_matrix,
                sector_allocation=sector_allocation,
                risk_adjusted_returns=risk_adjusted_returns,
                trend_analysis=trend_analysis,
                recommendations=recommendations,
                last_calculated=datetime.now(timezone.utc),
                calculation_duration=(datetime.now() - start_time).total_seconds()
            )
            
            # Store analytics in database
            await self._store_analytics(analytics, positions)
            
            logger.info(f"Analytics calculation completed in {analytics.calculation_duration:.2f}s")
            return analytics
            
        except Exception as e:
            logger.error(f"Error calculating comprehensive analytics: {e}")
            return await self._create_fallback_analytics(positions, str(e))
    
    async def _fetch_historical_data(self, 
                                   symbols: List[str], 
                                   days: int) -> Dict[str, pd.DataFrame]:
        """Fetch historical market data for symbols"""
        historical_data = {}
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            for symbol in symbols:
                # Get data from database first
                market_data = self.db.query(MarketData).filter(
                    and_(
                        MarketData.symbol == symbol,
                        MarketData.timeframe == "1h",
                        MarketData.timestamp >= cutoff_date
                    )
                ).order_by(MarketData.timestamp).all()
                
                if market_data:
                    df_data = []
                    for data in market_data:
                        df_data.append({
                            'timestamp': data.timestamp,
                            'open': float(data.open),
                            'high': float(data.high),
                            'low': float(data.low),
                            'close': float(data.close),
                            'volume': float(data.volume)
                        })
                    
                    df = pd.DataFrame(df_data)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    df['returns'] = df['close'].pct_change()
                    
                    historical_data[symbol] = df
                else:
                    logger.warning(f"No historical data found for {symbol}")
            
            logger.info(f"Fetched historical data for {len(historical_data)} symbols")
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return {}
    
    async def _calculate_performance_metrics(self, 
                                           positions: List[Dict[str, Any]],
                                           historical_data: Dict[str, pd.DataFrame]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        try:
            # Get realized P&L data for performance calculation
            realized_trades = self.db.query(RealizedPnL).filter(
                RealizedPnL.closed_at >= datetime.now(timezone.utc) - timedelta(days=30)
            ).all()
            
            if not realized_trades:
                # Use current position data for approximation
                total_pnl = sum(float(pos.get("pnl_amount", 0)) for pos in positions)
                return PerformanceMetrics(
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    win_rate=0.0,
                    profit_factor=0.0,
                    avg_trade_duration=0.0,
                    total_trades=len(positions),
                    profitable_trades=len([p for p in positions if float(p.get("pnl_amount", 0)) > 0]),
                    largest_win=max([float(p.get("pnl_amount", 0)) for p in positions] + [0]),
                    largest_loss=min([float(p.get("pnl_amount", 0)) for p in positions] + [0]),
                    avg_win=0.0,
                    avg_loss=0.0,
                    volatility=0.0,
                    beta=0.0,
                    alpha=0.0
                )
            
            # Calculate metrics from realized trades
            pnl_values = [float(trade.realized_pnl) for trade in realized_trades]
            profitable_trades = [pnl for pnl in pnl_values if pnl > 0]
            losing_trades = [pnl for pnl in pnl_values if pnl < 0]
            
            total_trades = len(realized_trades)
            profitable_count = len(profitable_trades)
            win_rate = (profitable_count / total_trades * 100) if total_trades > 0 else 0.0
            
            # Calculate profit factor
            total_profit = sum(profitable_trades) if profitable_trades else 0
            total_loss = abs(sum(losing_trades)) if losing_trades else 1
            profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
            
            # Calculate Sharpe ratio (simplified)
            if pnl_values:
                avg_return = np.mean(pnl_values)
                std_return = np.std(pnl_values)
                sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0.0
            else:
                sharpe_ratio = 0.0
            
            # Calculate maximum drawdown
            cumulative_pnl = np.cumsum(pnl_values) if pnl_values else [0]
            running_max = np.maximum.accumulate(cumulative_pnl)
            drawdown = (cumulative_pnl - running_max) / running_max
            max_drawdown = abs(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0.0
            
            # Calculate average trade duration
            durations = [trade.trade_duration_minutes for trade in realized_trades if trade.trade_duration_minutes]
            avg_duration = np.mean(durations) / 60 if durations else 0.0  # Convert to hours
            
            # Calculate volatility from portfolio returns
            portfolio_returns = []
            if historical_data:
                for symbol, data in historical_data.items():
                    if not data.empty and 'returns' in data.columns:
                        portfolio_returns.extend(data['returns'].dropna().tolist())
            
            volatility = np.std(portfolio_returns) * np.sqrt(24) * 100 if portfolio_returns else 0.0  # Annualized
            
            return PerformanceMetrics(
                sharpe_ratio=round(sharpe_ratio, 4),
                max_drawdown=round(max_drawdown, 2),
                win_rate=round(win_rate, 2),
                profit_factor=round(profit_factor, 4),
                avg_trade_duration=round(avg_duration, 2),
                total_trades=total_trades,
                profitable_trades=profitable_count,
                largest_win=max(pnl_values) if pnl_values else 0.0,
                largest_loss=min(pnl_values) if pnl_values else 0.0,
                avg_win=np.mean(profitable_trades) if profitable_trades else 0.0,
                avg_loss=np.mean(losing_trades) if losing_trades else 0.0,
                volatility=round(volatility, 2),
                beta=0.0,  # TODO: Calculate against market benchmark
                alpha=0.0  # TODO: Calculate against market benchmark
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return PerformanceMetrics(
                sharpe_ratio=0.0, max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                avg_trade_duration=0.0, total_trades=0, profitable_trades=0,
                largest_win=0.0, largest_loss=0.0, avg_win=0.0, avg_loss=0.0,
                volatility=0.0, beta=0.0, alpha=0.0
            )
    
    async def _calculate_risk_metrics(self, 
                                    positions: List[Dict[str, Any]],
                                    historical_data: Dict[str, pd.DataFrame]) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        try:
            # Calculate portfolio returns for VaR calculation
            portfolio_returns = []
            if historical_data:
                for symbol, data in historical_data.items():
                    if not data.empty and 'returns' in data.columns:
                        returns = data['returns'].dropna()
                        if len(returns) > 0:
                            portfolio_returns.extend(returns.tolist())
            
            if not portfolio_returns:
                portfolio_returns = [0.0]
            
            portfolio_returns = np.array(portfolio_returns)
            
            # Calculate Value at Risk (VaR)
            var_95 = np.percentile(portfolio_returns, 5) * 100  # 5th percentile for 95% VaR
            var_99 = np.percentile(portfolio_returns, 1) * 100  # 1st percentile for 99% VaR
            
            # Calculate Expected Shortfall (Conditional VaR)
            threshold_95 = np.percentile(portfolio_returns, 5)
            expected_shortfall = np.mean(portfolio_returns[portfolio_returns <= threshold_95]) * 100
            
            # Calculate maximum drawdown from current positions
            position_values = [float(pos.get("position_value", 0)) for pos in positions]
            total_value = sum(position_values)
            largest_loss_pct = abs(min([float(pos.get("pnl_percentage", 0)) for pos in positions] + [0]))
            max_drawdown = min(largest_loss_pct, 100.0)
            
            # Calculate downside deviation
            negative_returns = portfolio_returns[portfolio_returns < 0]
            downside_deviation = np.std(negative_returns) * 100 if len(negative_returns) > 0 else 0.0
            
            # Calculate Sortino ratio
            avg_return = np.mean(portfolio_returns) * 100
            sortino_ratio = (avg_return / downside_deviation) if downside_deviation > 0 else 0.0
            
            # Calculate concentration index (Herfindahl-Hirschman Index)
            if total_value > 0:
                market_shares = [(value / total_value) ** 2 for value in position_values]
                concentration_index = sum(market_shares)
            else:
                concentration_index = 0.0
            
            # Calculate leverage risk score
            leverages = [float(pos.get("leverage", 1)) for pos in positions]
            avg_leverage = np.mean(leverages) if leverages else 1.0
            max_leverage = max(leverages) if leverages else 1.0
            
            if max_leverage >= 20:
                leverage_risk_score = 90
            elif avg_leverage >= 10:
                leverage_risk_score = 70
            elif avg_leverage >= 5:
                leverage_risk_score = 50
            else:
                leverage_risk_score = 20
            
            # Calculate correlation risk score (simplified)
            correlation_risk_score = 50  # TODO: Implement based on actual correlations
            
            return RiskMetrics(
                value_at_risk_95=round(abs(var_95), 4),
                value_at_risk_99=round(abs(var_99), 4),
                expected_shortfall=round(abs(expected_shortfall), 4),
                maximum_drawdown=round(max_drawdown, 2),
                downside_deviation=round(downside_deviation, 4),
                sortino_ratio=round(sortino_ratio, 4),
                concentration_index=round(concentration_index, 4),
                leverage_risk_score=leverage_risk_score,
                correlation_risk_score=correlation_risk_score
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return RiskMetrics(
                value_at_risk_95=0.0, value_at_risk_99=0.0, expected_shortfall=0.0,
                maximum_drawdown=0.0, downside_deviation=0.0, sortino_ratio=0.0,
                concentration_index=0.0, leverage_risk_score=0, correlation_risk_score=0
            )
    
    async def _calculate_correlation_matrix(self, 
                                          symbols: List[str],
                                          historical_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix between positions"""
        correlation_matrix = {}
        
        try:
            if len(symbols) < 2 or not historical_data:
                return correlation_matrix
            
            # Create returns DataFrame
            returns_data = {}
            for symbol in symbols:
                if symbol in historical_data and not historical_data[symbol].empty:
                    returns = historical_data[symbol]['returns'].dropna()
                    if len(returns) > 10:  # Minimum data points
                        returns_data[symbol] = returns
            
            if len(returns_data) < 2:
                return correlation_matrix
            
            # Align time series and calculate correlations
            df_returns = pd.DataFrame(returns_data)
            df_returns = df_returns.dropna()
            
            if df_returns.empty or len(df_returns) < 10:
                return correlation_matrix
            
            # Calculate correlation matrix
            corr_matrix = df_returns.corr()
            
            # Convert to dictionary format and store in database
            for symbol1 in corr_matrix.index:
                correlation_matrix[symbol1] = {}
                for symbol2 in corr_matrix.columns:
                    correlation_value = corr_matrix.loc[symbol1, symbol2]
                    
                    if pd.isna(correlation_value):
                        correlation_value = 0.0
                    else:
                        correlation_value = float(correlation_value)
                    
                    correlation_matrix[symbol1][symbol2] = round(correlation_value, 4)
                    
                    # Store significant correlations in database
                    if (symbol1 != symbol2 and abs(correlation_value) > 0.3 and 
                        not pd.isna(correlation_value)):
                        await self._store_correlation(
                            symbol1, symbol2, correlation_value, len(df_returns)
                        )
            
            logger.info(f"Calculated correlation matrix for {len(symbols)} symbols")
            return correlation_matrix
            
        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return correlation_matrix
    
    async def _store_correlation(self, 
                               symbol1: str, 
                               symbol2: str, 
                               correlation: float, 
                               data_points: int):
        """Store correlation data in database"""
        try:
            # Determine correlation strength
            abs_corr = abs(correlation)
            if abs_corr >= 0.7:
                strength = "STRONG"
            elif abs_corr >= 0.4:
                strength = "MODERATE" 
            else:
                strength = "WEAK"
            
            # Check if correlation already exists (within last day)
            existing = self.db.query(PositionCorrelation).filter(
                and_(
                    PositionCorrelation.symbol_1 == symbol1,
                    PositionCorrelation.symbol_2 == symbol2,
                    PositionCorrelation.timeframe == "30d",
                    PositionCorrelation.calculated_at >= datetime.now(timezone.utc) - timedelta(days=1)
                )
            ).first()
            
            if not existing:
                correlation_record = PositionCorrelation(
                    symbol_1=symbol1,
                    symbol_2=symbol2,
                    correlation_coefficient=Decimal(str(correlation)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
                    correlation_strength=strength,
                    timeframe="30d",
                    data_points=data_points,
                    statistical_significance=Decimal('0.95'),  # Placeholder
                    calculated_at=datetime.now(timezone.utc)
                )
                
                self.db.add(correlation_record)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error storing correlation for {symbol1}-{symbol2}: {e}")
    
    def _calculate_sector_allocation(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate allocation by crypto sector (simplified)"""
        try:
            sector_mapping = {
                'BTC': 'Bitcoin',
                'ETH': 'Ethereum',
                'ADA': 'Smart Contract',
                'DOT': 'Smart Contract', 
                'SOL': 'Smart Contract',
                'AVAX': 'Smart Contract',
                'MATIC': 'Layer 2',
                'LTC': 'Payment',
                'XRP': 'Payment',
                'DOGE': 'Meme',
                'SHIB': 'Meme',
                'LINK': 'Oracle',
                'UNI': 'DeFi',
                'AAVE': 'DeFi',
                'COMP': 'DeFi'
            }
            
            sector_values = {}
            total_value = sum(float(pos.get("position_value", 0)) for pos in positions)
            
            for position in positions:
                symbol = position.get("symbol", "").replace("USDT", "")
                position_value = float(position.get("position_value", 0))
                
                sector = sector_mapping.get(symbol, "Other")
                
                if sector not in sector_values:
                    sector_values[sector] = 0.0
                
                sector_values[sector] += position_value
            
            # Convert to percentages
            sector_allocation = {}
            for sector, value in sector_values.items():
                percentage = (value / total_value * 100) if total_value > 0 else 0.0
                sector_allocation[sector] = round(percentage, 2)
            
            return sector_allocation
            
        except Exception as e:
            logger.error(f"Error calculating sector allocation: {e}")
            return {}
    
    async def _calculate_risk_adjusted_returns(self, 
                                             positions: List[Dict[str, Any]],
                                             historical_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Calculate risk-adjusted returns for each position"""
        risk_adjusted_returns = {}
        
        try:
            for position in positions:
                symbol = position.get("symbol", "")
                pnl_pct = float(position.get("pnl_percentage", 0))
                
                if symbol in historical_data and not historical_data[symbol].empty:
                    returns = historical_data[symbol]['returns'].dropna()
                    if len(returns) > 5:
                        volatility = returns.std() * 100  # Convert to percentage
                        
                        # Simple risk-adjusted return calculation
                        if volatility > 0:
                            risk_adjusted_return = pnl_pct / volatility
                        else:
                            risk_adjusted_return = pnl_pct
                    else:
                        risk_adjusted_return = pnl_pct
                else:
                    risk_adjusted_return = pnl_pct
                
                risk_adjusted_returns[symbol] = round(risk_adjusted_return, 4)
            
            return risk_adjusted_returns
            
        except Exception as e:
            logger.error(f"Error calculating risk-adjusted returns: {e}")
            return {}
    
    async def _perform_trend_analysis(self, 
                                    positions: List[Dict[str, Any]],
                                    historical_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Perform comprehensive trend analysis"""
        try:
            trend_analysis = {
                "overall_trend": "NEUTRAL",
                "trend_strength": 0.0,
                "bullish_positions": 0,
                "bearish_positions": 0,
                "momentum_score": 0.0,
                "trend_consistency": 0.0
            }
            
            bullish_count = 0
            bearish_count = 0
            momentum_scores = []
            
            for position in positions:
                symbol = position.get("symbol", "")
                pnl_pct = float(position.get("pnl_percentage", 0))
                
                if symbol in historical_data and not historical_data[symbol].empty:
                    data = historical_data[symbol]
                    if len(data) > 10:
                        # Calculate short-term vs long-term moving averages
                        short_ma = data['close'].tail(5).mean()
                        long_ma = data['close'].tail(20).mean() if len(data) >= 20 else data['close'].mean()
                        
                        momentum = (short_ma - long_ma) / long_ma * 100 if long_ma > 0 else 0
                        momentum_scores.append(momentum)
                        
                        if momentum > 1:
                            bullish_count += 1
                        elif momentum < -1:
                            bearish_count += 1
            
            total_analyzed = bullish_count + bearish_count
            if total_analyzed > 0:
                bullish_ratio = bullish_count / total_analyzed
                if bullish_ratio > 0.6:
                    trend_analysis["overall_trend"] = "BULLISH"
                elif bullish_ratio < 0.4:
                    trend_analysis["overall_trend"] = "BEARISH"
            
            trend_analysis.update({
                "bullish_positions": bullish_count,
                "bearish_positions": bearish_count,
                "momentum_score": round(np.mean(momentum_scores), 2) if momentum_scores else 0.0,
                "trend_strength": round(abs(np.mean(momentum_scores)), 2) if momentum_scores else 0.0,
                "trend_consistency": round(1 - (np.std(momentum_scores) / max(abs(np.mean(momentum_scores)), 1)), 2) if momentum_scores else 0.0
            })
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"Error performing trend analysis: {e}")
            return {"overall_trend": "UNKNOWN", "trend_strength": 0.0}
    
    async def _generate_analytics_recommendations(self, 
                                                positions: List[Dict[str, Any]],
                                                performance_metrics: PerformanceMetrics,
                                                risk_metrics: RiskMetrics,
                                                correlation_matrix: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """Generate recommendations based on analytics"""
        recommendations = []
        
        try:
            # Risk-based recommendations
            if risk_metrics.leverage_risk_score > 70:
                recommendations.append({
                    "type": "RISK_MANAGEMENT",
                    "priority": "HIGH",
                    "title": "High Leverage Risk Detected",
                    "description": f"Average leverage risk score is {risk_metrics.leverage_risk_score}. Consider reducing position sizes.",
                    "action": "REDUCE_LEVERAGE",
                    "confidence": 85
                })
            
            if risk_metrics.concentration_index > 0.5:
                recommendations.append({
                    "type": "DIVERSIFICATION", 
                    "priority": "MEDIUM",
                    "title": "Portfolio Concentration Risk",
                    "description": f"High concentration index ({risk_metrics.concentration_index:.2f}). Portfolio may benefit from diversification.",
                    "action": "DIVERSIFY_POSITIONS",
                    "confidence": 75
                })
            
            # Performance-based recommendations
            if performance_metrics.win_rate < 40:
                recommendations.append({
                    "type": "PERFORMANCE",
                    "priority": "MEDIUM", 
                    "title": "Low Win Rate",
                    "description": f"Win rate is {performance_metrics.win_rate:.1f}%. Review trading strategy.",
                    "action": "REVIEW_STRATEGY",
                    "confidence": 70
                })
            
            if performance_metrics.profit_factor < 1.2:
                recommendations.append({
                    "type": "PERFORMANCE",
                    "priority": "HIGH",
                    "title": "Low Profit Factor",
                    "description": f"Profit factor is {performance_metrics.profit_factor:.2f}. Losses may be outweighing gains.",
                    "action": "IMPROVE_RISK_REWARD",
                    "confidence": 80
                })
            
            # Correlation-based recommendations
            high_correlations = []
            for symbol1, correlations in correlation_matrix.items():
                for symbol2, corr_value in correlations.items():
                    if symbol1 != symbol2 and abs(corr_value) > 0.8:
                        high_correlations.append((symbol1, symbol2, corr_value))
            
            if len(high_correlations) > 3:
                recommendations.append({
                    "type": "CORRELATION",
                    "priority": "MEDIUM",
                    "title": "High Position Correlations",
                    "description": f"Found {len(high_correlations)} highly correlated position pairs. This increases portfolio risk.",
                    "action": "REDUCE_CORRELATED_POSITIONS",
                    "confidence": 70
                })
            
            # Add general recommendations if none found
            if not recommendations:
                recommendations.append({
                    "type": "GENERAL",
                    "priority": "LOW",
                    "title": "Portfolio Monitoring",
                    "description": "Continue monitoring portfolio metrics and maintain current risk management practices.",
                    "action": "MONITOR",
                    "confidence": 60
                })
            
            return recommendations[:5]  # Return top 5 recommendations
            
        except Exception as e:
            logger.error(f"Error generating analytics recommendations: {e}")
            return []
    
    async def _store_analytics(self, analytics: PortfolioAnalytics, positions: List[Dict[str, Any]]):
        """Store analytics results in database"""
        try:
            metrics = PortfolioMetrics(
                metric_date=analytics.last_calculated,
                sharpe_ratio=Decimal(str(analytics.performance_metrics.sharpe_ratio)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
                max_drawdown=Decimal(str(analytics.performance_metrics.max_drawdown)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                win_rate=Decimal(str(analytics.performance_metrics.win_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                avg_trade_duration=Decimal(str(analytics.performance_metrics.avg_trade_duration)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                total_trades=analytics.performance_metrics.total_trades,
                profitable_trades=analytics.performance_metrics.profitable_trades,
                largest_win=Decimal(str(analytics.performance_metrics.largest_win)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                largest_loss=Decimal(str(analytics.performance_metrics.largest_loss)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                avg_win=Decimal(str(analytics.performance_metrics.avg_win)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                avg_loss=Decimal(str(analytics.performance_metrics.avg_loss)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                profit_factor=Decimal(str(analytics.performance_metrics.profit_factor)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
                created_at=datetime.now(timezone.utc)
            )
            
            self.db.add(metrics)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error storing analytics: {e}")
    
    async def _create_fallback_analytics(self, 
                                       positions: List[Dict[str, Any]], 
                                       error_message: str) -> PortfolioAnalytics:
        """Create minimal analytics when calculation fails"""
        return PortfolioAnalytics(
            performance_metrics=PerformanceMetrics(
                sharpe_ratio=0.0, max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                avg_trade_duration=0.0, total_trades=0, profitable_trades=0,
                largest_win=0.0, largest_loss=0.0, avg_win=0.0, avg_loss=0.0,
                volatility=0.0, beta=0.0, alpha=0.0
            ),
            risk_metrics=RiskMetrics(
                value_at_risk_95=0.0, value_at_risk_99=0.0, expected_shortfall=0.0,
                maximum_drawdown=0.0, downside_deviation=0.0, sortino_ratio=0.0,
                concentration_index=0.0, leverage_risk_score=0, correlation_risk_score=0
            ),
            correlation_matrix={},
            sector_allocation={},
            risk_adjusted_returns={},
            trend_analysis={"overall_trend": "UNKNOWN"},
            recommendations=[{
                "type": "ERROR",
                "priority": "HIGH",
                "title": "Analytics Calculation Error",
                "description": f"Failed to calculate analytics: {error_message}",
                "action": "CHECK_DATA",
                "confidence": 100
            }],
            last_calculated=datetime.now(timezone.utc),
            calculation_duration=0.0
        )

    async def get_correlation_data(self, 
                                 symbol1: str, 
                                 symbol2: str, 
                                 timeframe: str = "30d") -> Optional[CorrelationData]:
        """Get stored correlation data between two symbols"""
        try:
            correlation = self.db.query(PositionCorrelation).filter(
                and_(
                    PositionCorrelation.symbol_1 == symbol1,
                    PositionCorrelation.symbol_2 == symbol2,
                    PositionCorrelation.timeframe == timeframe
                )
            ).order_by(desc(PositionCorrelation.calculated_at)).first()
            
            if correlation:
                return CorrelationData(
                    symbol_1=correlation.symbol_1,
                    symbol_2=correlation.symbol_2,
                    correlation_coefficient=float(correlation.correlation_coefficient),
                    correlation_strength=correlation.correlation_strength,
                    p_value=float(correlation.statistical_significance or 0.0),
                    data_points=correlation.data_points,
                    timeframe=correlation.timeframe
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting correlation data for {symbol1}-{symbol2}: {e}")
            return None
    
    async def get_historical_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get historical portfolio performance metrics"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            metrics = self.db.query(PortfolioMetrics).filter(
                PortfolioMetrics.metric_date >= cutoff_date
            ).order_by(PortfolioMetrics.metric_date).all()
            
            snapshots = self.db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.created_at >= cutoff_date
            ).order_by(PortfolioSnapshot.created_at).all()
            
            historical_data = {
                "performance_timeline": [],
                "portfolio_value_timeline": [],
                "risk_score_timeline": [],
                "summary": {
                    "total_data_points": len(snapshots),
                    "date_range": {
                        "start": snapshots[0].created_at.isoformat() if snapshots else None,
                        "end": snapshots[-1].created_at.isoformat() if snapshots else None
                    }
                }
            }
            
            for snapshot in snapshots:
                historical_data["portfolio_value_timeline"].append({
                    "date": snapshot.created_at.isoformat(),
                    "value": float(snapshot.portfolio_value),
                    "pnl": float(snapshot.total_pnl),
                    "risk_score": snapshot.risk_score
                })
            
            for metric in metrics:
                historical_data["performance_timeline"].append({
                    "date": metric.metric_date.isoformat(),
                    "sharpe_ratio": float(metric.sharpe_ratio or 0),
                    "win_rate": float(metric.win_rate or 0),
                    "profit_factor": float(metric.profit_factor or 0),
                    "max_drawdown": float(metric.max_drawdown or 0)
                })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical performance: {e}")
            return {"performance_timeline": [], "portfolio_value_timeline": [], "summary": {}}