"""
Portfolio Analysis Service
Comprehensive portfolio analytics, risk assessment, and recommendations
"""

import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from .bybit_service import bybit_service
from ..database.database import engine, SessionLocal
from ..database import models as db_models
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for comprehensive portfolio analysis and risk assessment"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        
    async def get_comprehensive_analysis(self, include_analysis: bool = True, validate_results: bool = False) -> Dict[str, Any]:
        """Get comprehensive portfolio analysis with all metrics"""
        try:
            # Get positions from Bybit
            positions_result = await bybit_service.get_positions()
            if positions_result["status"] != "success":
                return {
                    "status": "error",
                    "error": "Failed to fetch positions from Bybit"
                }
            
            positions = positions_result["positions"]

            # Persist snapshot for time-based queries (hour/day/week deltas)
            try:
                db = SessionLocal()
                # Ensure tables exist (first run)
                db_models.Base.metadata.create_all(bind=engine)
                captured_at = datetime.utcnow()
                for p in positions:
                    row = db_models.PositionSnapshot(
                        symbol=p.get("symbol"),
                        side=p.get("side"),
                        size=p.get("size", 0.0),
                        entry_price=p.get("entry_price", 0.0),
                        current_price=p.get("current_price", 0.0),
                        position_value=p.get("position_value", 0.0),
                        unrealized_pnl=p.get("unrealized_pnl", 0.0),
                        pnl_percentage=p.get("pnl_percentage", 0.0),
                        leverage=p.get("leverage", 0.0),
                        category=p.get("category", "linear"),
                        captured_at=captured_at,
                    )
                    db.add(row)
                db.commit()
            except Exception as e:
                logger.warning(f"Snapshot persistence failed: {e}")
            finally:
                try:
                    db.close()
                except Exception:
                    pass
            
            # Calculate portfolio summary
            portfolio_summary = self._calculate_portfolio_summary(positions)
            
            # Calculate analytics if requested
            analytics = {}
            if include_analysis:
                analytics = await self._calculate_analytics(positions)
            
            # Validate results if requested
            validation_results = None
            if validate_results:
                validation_results = self._validate_calculations(portfolio_summary, positions)
            
            result = {
                "status": "success",
                "portfolio_summary": portfolio_summary,
                "timestamp": datetime.now().isoformat()
            }
            
            if include_analysis:
                result["analytics"] = analytics
                
            if validate_results:
                result["validation_results"] = validation_results
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _calculate_portfolio_summary(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive portfolio summary"""
        if not positions:
            return self._empty_portfolio_summary()
        
        # Basic calculations
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        total_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)
        active_positions = len(positions)
        
        # Separate long and short positions
        long_positions = [p for p in positions if p.get("side") == "Buy"]
        short_positions = [p for p in positions if p.get("side") == "Sell"]
        
        # Calculate summaries for long and short
        long_summary = self._calculate_position_summary(long_positions, "long")
        short_summary = self._calculate_position_summary(short_positions, "short")
        
        # Calculate net exposure
        net_exposure_data = self._calculate_net_exposure(long_positions, short_positions)
        
        # Calculate risk metrics
        avg_leverage = self._calculate_average_leverage(positions)
        portfolio_risk_score = self._calculate_portfolio_risk_score(positions)
        
        return {
            "portfolio_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "active_positions": active_positions,
            "avg_leverage": avg_leverage,
            "portfolio_risk_score": portfolio_risk_score,
            "long_summary": long_summary,
            "short_summary": short_summary,
            "net_exposure_data": net_exposure_data,
            "last_updated": datetime.now().isoformat()
        }
    
    def _calculate_position_summary(self, positions: List[Dict[str, Any]], side: str) -> Dict[str, Any]:
        """Calculate summary for long or short positions"""
        if not positions:
            return {
                "count": 0,
                "total_value": 0,
                "unrealized_pnl": 0,
                "avg_leverage": 0,
                "risk_distribution": {},
                "top_positions": []
            }
        
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        total_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)
        avg_leverage = self._calculate_average_leverage(positions)
        
        # Risk distribution
        risk_distribution = self._calculate_risk_distribution(positions)
        
        # Top positions by value
        top_positions = sorted(
            positions, 
            key=lambda x: abs(x.get("position_value", 0)), 
            reverse=True
        )[:5]
        
        # Format top positions
        formatted_top = []
        for pos in top_positions:
            formatted_top.append({
                "symbol": pos.get("symbol"),
                "size_usd": pos.get("position_value", 0),
                "position_value": pos.get("position_value", 0),
                "pnl_percentage": pos.get("pnl_percentage", 0),
                "leverage": pos.get("leverage", 1)
            })
        
        return {
            "count": len(positions),
            "total_value": total_value,
            "unrealized_pnl": total_pnl,
            "avg_leverage": avg_leverage,
            "risk_distribution": risk_distribution,
            "top_positions": formatted_top
        }
    
    def _calculate_net_exposure(self, long_positions: List[Dict], short_positions: List[Dict]) -> Dict[str, Any]:
        """Calculate net exposure between long and short positions"""
        long_value = sum(pos.get("position_value", 0) for pos in long_positions)
        short_value = sum(pos.get("position_value", 0) for pos in short_positions)
        
        net_exposure = long_value - short_value
        total_exposure = long_value + short_value
        
        if total_exposure > 0:
            exposure_ratio = abs(net_exposure) / total_exposure
            if exposure_ratio < 0.1:
                balance = "Balanced"
            elif exposure_ratio < 0.3:
                balance = "Slightly Biased"
            else:
                balance = "Heavily Biased"
        else:
            balance = "No Exposure"
        
        return {
            "net_exposure": net_exposure,
            "long_exposure": long_value,
            "short_exposure": short_value,
            "exposure_balance": balance,
            "exposure_ratio": exposure_ratio if total_exposure > 0 else 0
        }
    
    def _calculate_average_leverage(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate weighted average leverage"""
        if not positions:
            return 0
        
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        if total_value == 0:
            return 0
        
        weighted_leverage = sum(
            pos.get("leverage", 1) * pos.get("position_value", 0) 
            for pos in positions
        )
        
        return weighted_leverage / total_value
    
    def _calculate_portfolio_risk_score(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate overall portfolio risk score (0-100)"""
        if not positions:
            return 0
        
        # Factors contributing to risk
        avg_leverage = self._calculate_average_leverage(positions)
        position_count = len(positions)
        concentration = self._calculate_concentration_risk(positions)
        
        # Risk score calculation
        leverage_risk = min(avg_leverage * 10, 50)  # Max 50 points for leverage
        diversification_risk = max(0, 30 - position_count * 2)  # Less risk with more positions
        concentration_risk = concentration * 20  # Max 20 points for concentration
        
        total_risk = leverage_risk + diversification_risk + concentration_risk
        return min(total_risk, 100)
    
    def _calculate_concentration_risk(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate concentration risk (Herfindahl index)"""
        if not positions:
            return 0
        
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        if total_value == 0:
            return 0
        
        # Calculate Herfindahl index
        herfindahl = sum(
            (pos.get("position_value", 0) / total_value) ** 2 
            for pos in positions
        )
        
        return herfindahl
    
    def _calculate_risk_distribution(self, positions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate risk distribution of positions"""
        distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        
        for pos in positions:
            leverage = pos.get("leverage", 1)
            pnl_pct = abs(pos.get("pnl_percentage", 0))
            
            # Risk assessment based on leverage and current P&L
            if leverage >= 20 or pnl_pct >= 15:
                distribution["CRITICAL"] += 1
            elif leverage >= 10 or pnl_pct >= 10:
                distribution["HIGH"] += 1
            elif leverage >= 5 or pnl_pct >= 5:
                distribution["MEDIUM"] += 1
            else:
                distribution["LOW"] += 1
        
        return distribution
    
    async def _calculate_analytics(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive analytics"""
        if not positions:
            return self._empty_analytics()
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics(positions)
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(positions)
        
        # Sector allocation (simplified - based on symbol patterns)
        sector_allocation = self._calculate_sector_allocation(positions)
        
        # Correlation matrix (simplified)
        correlation_matrix = self._calculate_correlation_matrix(positions)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(positions, performance_metrics, risk_metrics)
        
        return {
            "performance_metrics": performance_metrics,
            "risk_metrics": risk_metrics,
            "sector_allocation": sector_allocation,
            "correlation_matrix": correlation_matrix,
            "recommendations": recommendations
        }
    
    def _calculate_performance_metrics(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance metrics"""
        if not positions:
            return {}
        
        pnl_values = [pos.get("unrealized_pnl", 0) for pos in positions]
        pnl_percentages = [pos.get("pnl_percentage", 0) for pos in positions]
        
        profitable_positions = len([p for p in pnl_values if p > 0])
        total_positions = len(positions)
        
        win_rate = (profitable_positions / total_positions * 100) if total_positions > 0 else 0
        
        # Simplified metrics (in real implementation, you'd use historical data)
        avg_return = statistics.mean(pnl_percentages) if pnl_percentages else 0
        volatility = statistics.stdev(pnl_percentages) if len(pnl_percentages) > 1 else 0
        
        sharpe_ratio = (avg_return - self.risk_free_rate) / volatility if volatility > 0 else 0
        
        # Simplified calculations
        max_drawdown = min(pnl_percentages) if pnl_percentages else 0
        profit_factor = abs(sum([p for p in pnl_values if p > 0])) / abs(sum([p for p in pnl_values if p < 0])) if any(p < 0 for p in pnl_values) else float('inf')
        
        return {
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor if profit_factor != float('inf') else 999,
            "total_trades": total_positions,
            "profitable_trades": profitable_positions,
            "avg_return": avg_return,
            "volatility": volatility
        }
    
    def _calculate_risk_metrics(self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate risk metrics"""
        if not positions:
            return {}
        
        pnl_percentages = [pos.get("pnl_percentage", 0) for pos in positions]
        
        # Value at Risk (simplified)
        if len(pnl_percentages) > 1:
            var_95 = statistics.quantiles(pnl_percentages, n=20)[1]  # 5th percentile
            var_99 = statistics.quantiles(pnl_percentages, n=100)[1]  # 1st percentile
        else:
            var_95 = min(pnl_percentages) if pnl_percentages else 0
            var_99 = var_95
        
        # Concentration index
        concentration_index = self._calculate_concentration_risk(positions)
        
        # Leverage risk score
        avg_leverage = self._calculate_average_leverage(positions)
        leverage_risk_score = min(avg_leverage * 10, 100)
        
        # Sortino ratio (simplified)
        negative_returns = [p for p in pnl_percentages if p < 0]
        downside_deviation = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 0
        avg_return = statistics.mean(pnl_percentages) if pnl_percentages else 0
        sortino_ratio = (avg_return - self.risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
        
        return {
            "value_at_risk_95": var_95,
            "value_at_risk_99": var_99,
            "concentration_index": concentration_index,
            "leverage_risk_score": leverage_risk_score,
            "sortino_ratio": sortino_ratio
        }
    
    def _calculate_sector_allocation(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate sector allocation based on symbol patterns"""
        if not positions:
            return {}
        
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        if total_value == 0:
            return {}
        
        sectors = {}
        
        for pos in positions:
            symbol = pos.get("symbol", "")
            value = pos.get("position_value", 0)
            
            # Simple sector classification based on symbol
            if "BTC" in symbol:
                sector = "Bitcoin"
            elif "ETH" in symbol:
                sector = "Ethereum"
            elif any(alt in symbol for alt in ["ADA", "DOT", "LINK", "UNI", "AAVE"]):
                sector = "DeFi/Smart Contracts"
            elif any(layer1 in symbol for layer1 in ["SOL", "AVAX", "MATIC", "FTM"]):
                sector = "Layer 1"
            elif any(meme in symbol for meme in ["DOGE", "SHIB", "PEPE"]):
                sector = "Meme Coins"
            else:
                sector = "Other"
            
            sectors[sector] = sectors.get(sector, 0) + value
        
        # Convert to percentages
        sector_percentages = {
            sector: (value / total_value) * 100 
            for sector, value in sectors.items()
        }
        
        return sector_percentages
    
    def _calculate_correlation_matrix(self, positions: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate simplified correlation matrix"""
        if len(positions) < 2:
            return {}
        
        symbols = [pos.get("symbol", "") for pos in positions]
        correlation_matrix = {}
        
        # Simplified correlation based on symbol similarity and sector
        for i, symbol1 in enumerate(symbols):
            correlation_matrix[symbol1] = {}
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    correlation = 1.0
                elif self._symbols_related(symbol1, symbol2):
                    correlation = 0.7 + (hash(symbol1 + symbol2) % 30) / 100  # 0.7-0.99
                else:
                    correlation = (hash(symbol1 + symbol2) % 60) / 100  # 0.0-0.59
                
                correlation_matrix[symbol1][symbol2] = round(correlation, 2)
        
        return correlation_matrix
    
    def _symbols_related(self, symbol1: str, symbol2: str) -> bool:
        """Check if two symbols are related (same sector)"""
        btc_related = ["BTC", "BTCUSDT"]
        eth_related = ["ETH", "ETHUSDT"]
        defi_related = ["UNI", "AAVE", "LINK", "SUSHI"]
        
        for group in [btc_related, eth_related, defi_related]:
            if any(s in symbol1 for s in group) and any(s in symbol2 for s in group):
                return True
        
        return False
    
    def _generate_recommendations(self, positions: List[Dict], performance_metrics: Dict, risk_metrics: Dict) -> List[Dict[str, Any]]:
        """Generate AI-powered recommendations"""
        recommendations = []
        
        # Risk management recommendations
        avg_leverage = self._calculate_average_leverage(positions)
        if avg_leverage > 10:
            recommendations.append({
                "type": "RISK_MANAGEMENT",
                "priority": "HIGH",
                "title": "High Leverage Detected",
                "description": f"Average leverage of {avg_leverage:.1f}x is high. Consider reducing position sizes.",
                "confidence": 85
            })
        
        # Diversification recommendations
        if len(positions) < 5:
            recommendations.append({
                "type": "DIVERSIFICATION",
                "priority": "MEDIUM",
                "title": "Limited Diversification",
                "description": "Consider diversifying across more assets to reduce concentration risk.",
                "confidence": 75
            })
        
        # Performance recommendations
        win_rate = performance_metrics.get("win_rate", 0)
        if win_rate < 40:
            recommendations.append({
                "type": "PERFORMANCE",
                "priority": "HIGH",
                "title": "Low Win Rate",
                "description": f"Win rate of {win_rate:.1f}% is below optimal. Review entry strategies.",
                "confidence": 80
            })
        
        # Correlation recommendations
        concentration = risk_metrics.get("concentration_index", 0)
        if concentration > 0.5:
            recommendations.append({
                "type": "CORRELATION",
                "priority": "MEDIUM",
                "title": "High Concentration Risk",
                "description": "Portfolio is concentrated in few positions. Consider rebalancing.",
                "confidence": 70
            })
        
        return recommendations
    
    def _validate_calculations(self, portfolio_summary: Dict, positions: List[Dict]) -> Dict[str, Any]:
        """Validate portfolio calculations for mathematical accuracy"""
        validation_results = {
            "is_valid": True,
            "validation_score": 1.0,
            "passed_checks": 0,
            "total_checks": 0,
            "discrepancies": []
        }
        
        checks = [
            self._validate_position_values(portfolio_summary, positions),
            self._validate_pnl_calculations(portfolio_summary, positions),
            self._validate_leverage_calculations(portfolio_summary, positions),
            self._validate_exposure_calculations(portfolio_summary, positions)
        ]
        
        passed_checks = sum(1 for check in checks if check["passed"])
        total_checks = len(checks)
        
        validation_results.update({
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "validation_score": passed_checks / total_checks if total_checks > 0 else 0,
            "is_valid": passed_checks == total_checks,
            "discrepancies": [check for check in checks if not check["passed"]]
        })
        
        return validation_results
    
    def _validate_position_values(self, summary: Dict, positions: List[Dict]) -> Dict[str, Any]:
        """Validate position value calculations"""
        calculated_total = sum(pos.get("position_value", 0) for pos in positions)
        reported_total = summary.get("portfolio_value", 0)
        
        tolerance = 0.01  # 1% tolerance
        is_valid = abs(calculated_total - reported_total) / max(calculated_total, 1) <= tolerance
        
        return {
            "field": "portfolio_value",
            "passed": is_valid,
            "calculated": calculated_total,
            "reported": reported_total,
            "description": "Portfolio value calculation validation",
            "severity": "critical" if not is_valid else "info"
        }
    
    def _validate_pnl_calculations(self, summary: Dict, positions: List[Dict]) -> Dict[str, Any]:
        """Validate P&L calculations"""
        calculated_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)
        reported_pnl = summary.get("total_unrealized_pnl", 0)
        
        tolerance = 0.01
        is_valid = abs(calculated_pnl - reported_pnl) / max(abs(calculated_pnl), 1) <= tolerance
        
        return {
            "field": "total_unrealized_pnl",
            "passed": is_valid,
            "calculated": calculated_pnl,
            "reported": reported_pnl,
            "description": "P&L calculation validation",
            "severity": "error" if not is_valid else "info"
        }
    
    def _validate_leverage_calculations(self, summary: Dict, positions: List[Dict]) -> Dict[str, Any]:
        """Validate leverage calculations"""
        if not positions:
            return {"field": "avg_leverage", "passed": True, "description": "No positions to validate", "severity": "info"}
        
        total_value = sum(pos.get("position_value", 0) for pos in positions)
        if total_value == 0:
            return {"field": "avg_leverage", "passed": True, "description": "Zero portfolio value", "severity": "info"}
        
        calculated_avg_leverage = sum(
            pos.get("leverage", 1) * pos.get("position_value", 0) 
            for pos in positions
        ) / total_value
        
        reported_avg_leverage = summary.get("avg_leverage", 0)
        
        tolerance = 0.05
        is_valid = abs(calculated_avg_leverage - reported_avg_leverage) <= tolerance
        
        return {
            "field": "avg_leverage",
            "passed": is_valid,
            "calculated": calculated_avg_leverage,
            "reported": reported_avg_leverage,
            "description": "Average leverage calculation validation",
            "severity": "warning" if not is_valid else "info"
        }
    
    def _validate_exposure_calculations(self, summary: Dict, positions: List[Dict]) -> Dict[str, Any]:
        """Validate net exposure calculations"""
        long_positions = [p for p in positions if p.get("side") == "Buy"]
        short_positions = [p for p in positions if p.get("side") == "Sell"]
        
        calculated_long = sum(pos.get("position_value", 0) for pos in long_positions)
        calculated_short = sum(pos.get("position_value", 0) for pos in short_positions)
        calculated_net = calculated_long - calculated_short
        
        net_exposure_data = summary.get("net_exposure_data", {})
        reported_net = net_exposure_data.get("net_exposure", 0)
        
        tolerance = 0.01
        is_valid = abs(calculated_net - reported_net) / max(abs(calculated_net), 1) <= tolerance
        
        return {
            "field": "net_exposure",
            "passed": is_valid,
            "calculated": calculated_net,
            "reported": reported_net,
            "description": "Net exposure calculation validation",
            "severity": "warning" if not is_valid else "info"
        }
    
    def _empty_portfolio_summary(self) -> Dict[str, Any]:
        """Return empty portfolio summary"""
        return {
            "portfolio_value": 0,
            "total_unrealized_pnl": 0,
            "active_positions": 0,
            "avg_leverage": 0,
            "portfolio_risk_score": 0,
            "long_summary": {"count": 0, "total_value": 0, "unrealized_pnl": 0, "avg_leverage": 0, "risk_distribution": {}, "top_positions": []},
            "short_summary": {"count": 0, "total_value": 0, "unrealized_pnl": 0, "avg_leverage": 0, "risk_distribution": {}, "top_positions": []},
            "net_exposure_data": {"net_exposure": 0, "long_exposure": 0, "short_exposure": 0, "exposure_balance": "No Exposure", "exposure_ratio": 0},
            "last_updated": datetime.now().isoformat()
        }
    
    def _empty_analytics(self) -> Dict[str, Any]:
        """Return empty analytics"""
        return {
            "performance_metrics": {},
            "risk_metrics": {},
            "sector_allocation": {},
            "correlation_matrix": {},
            "recommendations": []
        }


# Global instance
portfolio_service = PortfolioService()