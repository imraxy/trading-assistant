"""
Portfolio Aggregation Service

Provides comprehensive portfolio-level aggregation and analysis of trading positions,
including long/short separation, net exposure calculations, and mathematical validation.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.models import Position, Account, PortfolioSnapshot, ValidationLog
from app.api.bybit_client import BybitClient
from app.services.enhanced_position_analysis_service import EnhancedPositionAnalysisService
from app.config import get_settings

logger = logging.getLogger(__name__)

@dataclass
class ValidationDiscrepancy:
    """Represents a validation discrepancy"""
    field: str
    expected: float
    actual: float
    difference: float
    severity: str  # 'warning', 'error', 'critical'
    description: str

@dataclass
class ValidationStatus:
    """Portfolio validation status"""
    is_valid: bool
    validation_score: float  # 0.0 to 1.0
    discrepancies: List[ValidationDiscrepancy]
    last_validated: datetime
    validation_warnings: List[str]
    total_checks: int
    passed_checks: int

@dataclass
class NetExposureData:
    """Net exposure calculation results"""
    long_exposure: Decimal
    short_exposure: Decimal
    net_exposure: Decimal
    total_exposure: Decimal
    net_ratio: float
    exposure_balance: str
    leverage_weighted_exposure: Decimal
    risk_adjusted_exposure: Decimal

@dataclass
class DirectionSummary:
    """Summary for long or short positions"""
    count: int
    total_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    avg_leverage: float
    weighted_avg_leverage: float
    risk_distribution: Dict[str, int]
    pnl_distribution: Dict[str, int]
    top_positions: List[Dict]
    positions: List[Dict]
    total_margin: Decimal
    avg_entry_price: float
    avg_current_price: float

@dataclass
class PortfolioSummary:
    """Complete portfolio summary"""
    total_positions: int
    active_positions: int
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    net_exposure: Decimal
    total_exposure: Decimal
    portfolio_value: Decimal
    available_balance: Decimal
    total_margin: Decimal
    avg_leverage: float
    portfolio_risk_score: int
    long_summary: DirectionSummary
    short_summary: DirectionSummary
    net_exposure_data: NetExposureData
    symbol_allocation: Dict[str, Dict[str, Any]]
    risk_metrics: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    validation_status: ValidationStatus
    last_calculated: datetime
    calculation_duration: float

class PortfolioValidator:
    """Validates portfolio calculations and data integrity"""
    
    def __init__(self, db: Session, validation_tolerance: float = 0.01):
        self.db = db
        self.validation_tolerance = validation_tolerance
        
    async def validate_position(self, position: Dict[str, Any]) -> List[ValidationDiscrepancy]:
        """Validate individual position calculations"""
        discrepancies = []
        
        try:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = float(position.get("size", 0))
            entry_price = float(position.get("entry_price", 0))
            current_price = float(position.get("current_price", 0))
            position_value = float(position.get("position_value", 0))
            pnl_amount = float(position.get("pnl_amount", 0))
            pnl_percentage = float(position.get("pnl_percentage", 0))
            leverage = int(position.get("leverage", 1))
            
            # Validate position value calculation
            if size > 0 and current_price > 0:
                calculated_value = size * current_price
                value_diff = abs(calculated_value - position_value)
                if value_diff > (position_value * self.validation_tolerance):
                    discrepancies.append(ValidationDiscrepancy(
                        field="position_value",
                        expected=calculated_value,
                        actual=position_value,
                        difference=value_diff,
                        severity="warning",
                        description=f"Position value mismatch for {symbol}"
                    ))
            
            # Validate P&L calculation
            if size > 0 and entry_price > 0 and current_price > 0:
                direction_multiplier = 1 if side.lower() in ["buy", "long"] else -1
                calculated_pnl = (current_price - entry_price) * size * direction_multiplier
                pnl_diff = abs(calculated_pnl - pnl_amount)
                
                if pnl_diff > (abs(pnl_amount) * self.validation_tolerance + 0.01):
                    discrepancies.append(ValidationDiscrepancy(
                        field="pnl_amount",
                        expected=calculated_pnl,
                        actual=pnl_amount,
                        difference=pnl_diff,
                        severity="error",
                        description=f"P&L calculation mismatch for {symbol}"
                    ))
            
            # Validate P&L percentage
            if position_value > 0:
                calculated_pnl_pct = (pnl_amount / position_value) * 100
                pnl_pct_diff = abs(calculated_pnl_pct - pnl_percentage)
                
                if pnl_pct_diff > 0.1:  # 0.1% tolerance
                    discrepancies.append(ValidationDiscrepancy(
                        field="pnl_percentage",
                        expected=calculated_pnl_pct,
                        actual=pnl_percentage,
                        difference=pnl_pct_diff,
                        severity="warning",
                        description=f"P&L percentage mismatch for {symbol}"
                    ))
                    
        except Exception as e:
            logger.error(f"Error validating position {position.get('symbol')}: {e}")
            discrepancies.append(ValidationDiscrepancy(
                field="validation_error",
                expected=0,
                actual=1,
                difference=1,
                severity="critical",
                description=f"Validation error for {position.get('symbol')}: {str(e)}"
            ))
        
        return discrepancies
    
    async def validate_portfolio_aggregation(self, 
                                           portfolio_summary: PortfolioSummary,
                                           raw_positions: List[Dict]) -> ValidationStatus:
        """Validate portfolio-level aggregations"""
        discrepancies = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        
        try:
            # Check position count consistency
            total_checks += 1
            expected_count = len([p for p in raw_positions if float(p.get("size", 0)) > 0])
            if portfolio_summary.active_positions == expected_count:
                passed_checks += 1
            else:
                discrepancies.append(ValidationDiscrepancy(
                    field="position_count",
                    expected=expected_count,
                    actual=portfolio_summary.active_positions,
                    difference=abs(expected_count - portfolio_summary.active_positions),
                    severity="error",
                    description="Position count mismatch between raw data and aggregation"
                ))
            
            # Validate total P&L
            total_checks += 1
            expected_pnl = sum(float(p.get("pnl_amount", 0)) for p in raw_positions)
            actual_pnl = float(portfolio_summary.total_unrealized_pnl)
            pnl_diff = abs(expected_pnl - actual_pnl)
            
            if pnl_diff <= (abs(expected_pnl) * self.validation_tolerance + 0.01):
                passed_checks += 1
            else:
                discrepancies.append(ValidationDiscrepancy(
                    field="total_pnl",
                    expected=expected_pnl,
                    actual=actual_pnl,
                    difference=pnl_diff,
                    severity="error",
                    description="Total P&L aggregation mismatch"
                ))
            
            # Validate exposure calculations
            total_checks += 1
            long_positions = [p for p in raw_positions if p.get("side", "").lower() in ["buy", "long"]]
            short_positions = [p for p in raw_positions if p.get("side", "").lower() in ["sell", "short"]]
            
            expected_long_exposure = sum(float(p.get("position_value", 0)) for p in long_positions)
            expected_short_exposure = sum(float(p.get("position_value", 0)) for p in short_positions)
            
            actual_long_exposure = float(portfolio_summary.net_exposure_data.long_exposure)
            actual_short_exposure = float(portfolio_summary.net_exposure_data.short_exposure)
            
            long_diff = abs(expected_long_exposure - actual_long_exposure)
            short_diff = abs(expected_short_exposure - actual_short_exposure)
            
            if (long_diff <= (expected_long_exposure * self.validation_tolerance + 0.01) and
                short_diff <= (expected_short_exposure * self.validation_tolerance + 0.01)):
                passed_checks += 1
            else:
                discrepancies.append(ValidationDiscrepancy(
                    field="exposure_calculation",
                    expected=expected_long_exposure + expected_short_exposure,
                    actual=actual_long_exposure + actual_short_exposure,
                    difference=long_diff + short_diff,
                    severity="error",
                    description="Exposure calculation mismatch"
                ))
            
            # Validate direction summaries
            total_checks += 1
            long_count = len(long_positions)
            short_count = len(short_positions)
            
            if (portfolio_summary.long_summary.count == long_count and
                portfolio_summary.short_summary.count == short_count):
                passed_checks += 1
            else:
                discrepancies.append(ValidationDiscrepancy(
                    field="direction_counts",
                    expected=long_count + short_count,
                    actual=portfolio_summary.long_summary.count + portfolio_summary.short_summary.count,
                    difference=abs((long_count + short_count) - 
                                 (portfolio_summary.long_summary.count + portfolio_summary.short_summary.count)),
                    severity="warning",
                    description="Direction-based position count mismatch"
                ))
            
            # Calculate validation score
            validation_score = passed_checks / total_checks if total_checks > 0 else 0.0
            is_valid = validation_score >= 0.95 and len([d for d in discrepancies if d.severity == "critical"]) == 0
            
            # Add warnings for low validation score
            if validation_score < 0.9:
                warnings.append(f"Low validation score: {validation_score:.2%}")
            
            if len(discrepancies) > 5:
                warnings.append(f"High number of discrepancies: {len(discrepancies)}")
            
            return ValidationStatus(
                is_valid=is_valid,
                validation_score=validation_score,
                discrepancies=discrepancies,
                last_validated=datetime.now(timezone.utc),
                validation_warnings=warnings,
                total_checks=total_checks,
                passed_checks=passed_checks
            )
            
        except Exception as e:
            logger.error(f"Error validating portfolio aggregation: {e}")
            return ValidationStatus(
                is_valid=False,
                validation_score=0.0,
                discrepancies=[ValidationDiscrepancy(
                    field="validation_error",
                    expected=1,
                    actual=0,
                    difference=1,
                    severity="critical",
                    description=f"Portfolio validation error: {str(e)}"
                )],
                last_validated=datetime.now(timezone.utc),
                validation_warnings=[f"Critical validation error: {str(e)}"],
                total_checks=1,
                passed_checks=0
            )

class PortfolioAggregationService:
    """Main service for portfolio aggregation and analysis"""
    
    def __init__(self, 
                 bybit_client: BybitClient,
                 db: Session, 
                 validation_tolerance: float = 0.01):
        self.bybit_client = bybit_client
        self.db = db
        self.settings = get_settings()
        self.validator = PortfolioValidator(db, validation_tolerance)
        self.validation_tolerance = validation_tolerance
        
    async def aggregate_portfolio(self, 
                                positions: List[Dict[str, Any]], 
                                include_analysis: bool = True,
                                validate_results: bool = True) -> PortfolioSummary:
        """
        Main aggregation method that creates comprehensive portfolio summary
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting portfolio aggregation for {len(positions)} positions")
            
            # Filter active positions
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]
            
            # Enrich with analysis if requested
            if include_analysis and active_positions:
                logger.info("Enriching positions with enhanced analysis...")
                async with EnhancedPositionAnalysisService(
                    self.bybit_client, self.db, 
                    enable_technical_analysis=True,
                    enable_sentiment_analysis=True
                ) as analysis_service:
                    active_positions = await analysis_service.analyze_all_positions(active_positions)
            
            # Separate by direction
            direction_data = await self._separate_by_direction(active_positions)
            long_positions = direction_data["long"]
            short_positions = direction_data["short"]
            
            # Calculate net exposure
            net_exposure_data = await self._calculate_net_exposure(long_positions, short_positions)
            
            # Create direction summaries
            long_summary = await self._create_direction_summary(long_positions, "long")
            short_summary = await self._create_direction_summary(short_positions, "short")
            
            # Calculate portfolio metrics
            portfolio_metrics = await self._calculate_portfolio_metrics(active_positions, net_exposure_data)
            
            # Calculate symbol allocation
            symbol_allocation = await self._calculate_symbol_allocation(active_positions)
            
            # Create portfolio summary
            portfolio_summary = PortfolioSummary(
                total_positions=len(positions),
                active_positions=len(active_positions),
                total_unrealized_pnl=Decimal(str(sum(float(p.get("pnl_amount", 0)) for p in active_positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                total_realized_pnl=Decimal('0.00'),  # TODO: Implement realized P&L tracking
                net_exposure=net_exposure_data.net_exposure,
                total_exposure=net_exposure_data.total_exposure,
                portfolio_value=Decimal(str(sum(float(p.get("position_value", 0)) for p in active_positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                available_balance=Decimal('0.00'),  # TODO: Get from account info
                total_margin=Decimal(str(sum(float(p.get("position_value", 0)) / max(float(p.get("leverage", 1)), 1) for p in active_positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                avg_leverage=portfolio_metrics["avg_leverage"],
                portfolio_risk_score=portfolio_metrics["risk_score"],
                long_summary=long_summary,
                short_summary=short_summary,
                net_exposure_data=net_exposure_data,
                symbol_allocation=symbol_allocation,
                risk_metrics=portfolio_metrics["risk_metrics"],
                performance_metrics=portfolio_metrics["performance_metrics"],
                validation_status=ValidationStatus(is_valid=True, validation_score=1.0, discrepancies=[], 
                                                 last_validated=datetime.now(timezone.utc), validation_warnings=[], 
                                                 total_checks=0, passed_checks=0),
                last_calculated=datetime.now(timezone.utc),
                calculation_duration=(datetime.now() - start_time).total_seconds()
            )
            
            # Validate results if requested
            if validate_results:
                logger.info("Validating portfolio aggregation results...")
                validation_status = await self.validator.validate_portfolio_aggregation(
                    portfolio_summary, positions
                )
                portfolio_summary.validation_status = validation_status
                
                # Log validation results
                if validation_status.is_valid:
                    logger.info(f"Portfolio validation passed with score: {validation_status.validation_score:.2%}")
                else:
                    logger.warning(f"Portfolio validation issues found: {len(validation_status.discrepancies)} discrepancies")
                    for discrepancy in validation_status.discrepancies[:5]:  # Log first 5
                        logger.warning(f"  {discrepancy.field}: {discrepancy.description}")
            
            # Store portfolio snapshot
            await self._store_portfolio_snapshot(portfolio_summary)
            
            logger.info(f"Portfolio aggregation completed in {portfolio_summary.calculation_duration:.2f}s")
            return portfolio_summary
            
        except Exception as e:
            logger.error(f"Error in portfolio aggregation: {e}")
            # Return minimal portfolio summary on error
            return await self._create_error_portfolio_summary(positions, str(e))
    
    async def _separate_by_direction(self, positions: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Separate positions by long/short direction"""
        classified = {
            "long": [],
            "short": [],
            "invalid": []
        }
        
        for position in positions:
            try:
                side = position.get("side", "").lower()
                size = float(position.get("size", 0))
                
                if size > 0:
                    if side in ["buy", "long"]:
                        classified["long"].append(position)
                    elif side in ["sell", "short"]:
                        classified["short"].append(position)
                    else:
                        classified["invalid"].append(position)
                        logger.warning(f"Invalid position side '{side}' for {position.get('symbol')}")
                else:
                    classified["invalid"].append(position)
                    
            except Exception as e:
                logger.error(f"Error classifying position {position.get('symbol')}: {e}")
                classified["invalid"].append(position)
        
        logger.info(f"Position classification: {len(classified['long'])} long, {len(classified['short'])} short, {len(classified['invalid'])} invalid")
        return classified
    
    async def _calculate_net_exposure(self, 
                                    long_positions: List[Dict], 
                                    short_positions: List[Dict]) -> NetExposureData:
        """Calculate comprehensive net exposure metrics"""
        try:
            # Basic exposure calculations
            long_exposure = Decimal(str(sum(float(pos.get("position_value", 0)) for pos in long_positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            short_exposure = Decimal(str(sum(float(pos.get("position_value", 0)) for pos in short_positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            net_exposure = long_exposure - short_exposure
            total_exposure = long_exposure + short_exposure
            net_ratio = float(net_exposure / total_exposure) if total_exposure > 0 else 0.0
            
            # Leverage-weighted exposure
            long_leverage_weighted = sum(
                float(pos.get("position_value", 0)) * float(pos.get("leverage", 1)) 
                for pos in long_positions
            )
            short_leverage_weighted = sum(
                float(pos.get("position_value", 0)) * float(pos.get("leverage", 1)) 
                for pos in short_positions
            )
            leverage_weighted_exposure = Decimal(str(long_leverage_weighted + short_leverage_weighted)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Risk-adjusted exposure (weighted by risk scores)
            long_risk_weighted = sum(
                float(pos.get("position_value", 0)) * (float(pos.get("risk_score", 50)) / 100) 
                for pos in long_positions
            )
            short_risk_weighted = sum(
                float(pos.get("position_value", 0)) * (float(pos.get("risk_score", 50)) / 100) 
                for pos in short_positions
            )
            risk_adjusted_exposure = Decimal(str(long_risk_weighted + short_risk_weighted)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Determine exposure balance
            if net_ratio > 0.15:
                exposure_balance = "Long Heavy"
            elif net_ratio < -0.15:
                exposure_balance = "Short Heavy"
            elif abs(net_ratio) <= 0.05:
                exposure_balance = "Balanced"
            else:
                exposure_balance = "Long Bias" if net_ratio > 0 else "Short Bias"
            
            return NetExposureData(
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                net_exposure=net_exposure,
                total_exposure=total_exposure,
                net_ratio=net_ratio,
                exposure_balance=exposure_balance,
                leverage_weighted_exposure=leverage_weighted_exposure,
                risk_adjusted_exposure=risk_adjusted_exposure
            )
            
        except Exception as e:
            logger.error(f"Error calculating net exposure: {e}")
            return NetExposureData(
                long_exposure=Decimal('0.00'),
                short_exposure=Decimal('0.00'),
                net_exposure=Decimal('0.00'),
                total_exposure=Decimal('0.00'),
                net_ratio=0.0,
                exposure_balance="Unknown",
                leverage_weighted_exposure=Decimal('0.00'),
                risk_adjusted_exposure=Decimal('0.00')
            )
    
    async def _create_direction_summary(self, 
                                      positions: List[Dict], 
                                      direction: str) -> DirectionSummary:
        """Create summary for positions in one direction"""
        if not positions:
            return DirectionSummary(
                count=0,
                total_value=Decimal('0.00'),
                unrealized_pnl=Decimal('0.00'),
                realized_pnl=Decimal('0.00'),
                avg_leverage=0.0,
                weighted_avg_leverage=0.0,
                risk_distribution={},
                pnl_distribution={},
                top_positions=[],
                positions=[],
                total_margin=Decimal('0.00'),
                avg_entry_price=0.0,
                avg_current_price=0.0
            )
        
        try:
            # Basic metrics
            count = len(positions)
            total_value = Decimal(str(sum(float(p.get("position_value", 0)) for p in positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            unrealized_pnl = Decimal(str(sum(float(p.get("pnl_amount", 0)) for p in positions))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Leverage calculations
            leverages = [float(p.get("leverage", 1)) for p in positions]
            avg_leverage = sum(leverages) / len(leverages)
            
            # Weighted average leverage (by position value)
            total_weighted_leverage = sum(
                float(p.get("leverage", 1)) * float(p.get("position_value", 0)) 
                for p in positions
            )
            weighted_avg_leverage = total_weighted_leverage / float(total_value) if total_value > 0 else 0.0
            
            # Risk distribution
            risk_distribution = {}
            for position in positions:
                risk_level = position.get("risk_level", "UNKNOWN")
                risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
            
            # P&L distribution
            pnl_distribution = {"positive": 0, "negative": 0, "breakeven": 0}
            for position in positions:
                pnl = float(position.get("pnl_amount", 0))
                if pnl > 0.01:
                    pnl_distribution["positive"] += 1
                elif pnl < -0.01:
                    pnl_distribution["negative"] += 1
                else:
                    pnl_distribution["breakeven"] += 1
            
            # Top positions by value
            sorted_positions = sorted(positions, key=lambda x: float(x.get("position_value", 0)), reverse=True)
            top_positions = sorted_positions[:5]
            
            # Margin calculation
            total_margin = Decimal(str(sum(
                float(p.get("position_value", 0)) / max(float(p.get("leverage", 1)), 1) 
                for p in positions
            ))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Average prices
            total_value_float = float(total_value)
            if total_value_float > 0:
                avg_entry_price = sum(
                    float(p.get("entry_price", 0)) * float(p.get("position_value", 0)) 
                    for p in positions
                ) / total_value_float
                
                avg_current_price = sum(
                    float(p.get("current_price", 0)) * float(p.get("position_value", 0)) 
                    for p in positions
                ) / total_value_float
            else:
                avg_entry_price = 0.0
                avg_current_price = 0.0
            
            return DirectionSummary(
                count=count,
                total_value=total_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=Decimal('0.00'),  # TODO: Implement realized P&L
                avg_leverage=avg_leverage,
                weighted_avg_leverage=weighted_avg_leverage,
                risk_distribution=risk_distribution,
                pnl_distribution=pnl_distribution,
                top_positions=top_positions,
                positions=positions,
                total_margin=total_margin,
                avg_entry_price=avg_entry_price,
                avg_current_price=avg_current_price
            )
            
        except Exception as e:
            logger.error(f"Error creating {direction} direction summary: {e}")
            return DirectionSummary(
                count=len(positions),
                total_value=Decimal('0.00'),
                unrealized_pnl=Decimal('0.00'),
                realized_pnl=Decimal('0.00'),
                avg_leverage=0.0,
                weighted_avg_leverage=0.0,
                risk_distribution={"UNKNOWN": len(positions)},
                pnl_distribution={"unknown": len(positions)},
                top_positions=positions[:5],
                positions=positions,
                total_margin=Decimal('0.00'),
                avg_entry_price=0.0,
                avg_current_price=0.0
            )
    
    async def _calculate_portfolio_metrics(self, 
                                         positions: List[Dict], 
                                         net_exposure_data: NetExposureData) -> Dict[str, Any]:
        """Calculate comprehensive portfolio metrics"""
        try:
            # Average leverage
            if positions:
                leverages = [float(p.get("leverage", 1)) for p in positions]
                avg_leverage = sum(leverages) / len(leverages)
            else:
                avg_leverage = 0.0
            
            # Portfolio risk score (weighted average)
            if positions:
                total_value = sum(float(p.get("position_value", 0)) for p in positions)
                if total_value > 0:
                    weighted_risk_score = sum(
                        float(p.get("risk_score", 50)) * float(p.get("position_value", 0)) 
                        for p in positions
                    ) / total_value
                else:
                    weighted_risk_score = 50
            else:
                weighted_risk_score = 0
            
            # Risk metrics
            risk_metrics = {
                "portfolio_risk_score": int(weighted_risk_score),
                "leverage_risk": "HIGH" if avg_leverage > 10 else "MEDIUM" if avg_leverage > 5 else "LOW",
                "exposure_risk": "HIGH" if abs(net_exposure_data.net_ratio) > 0.7 else "MEDIUM" if abs(net_exposure_data.net_ratio) > 0.3 else "LOW",
                "concentration_risk": self._calculate_concentration_risk(positions),
                "correlation_risk": "UNKNOWN"  # TODO: Implement correlation analysis
            }
            
            # Performance metrics
            performance_metrics = {
                "total_pnl": sum(float(p.get("pnl_amount", 0)) for p in positions),
                "winning_positions": len([p for p in positions if float(p.get("pnl_amount", 0)) > 0]),
                "losing_positions": len([p for p in positions if float(p.get("pnl_amount", 0)) < 0]),
                "win_rate": 0.0,  # TODO: Calculate from historical data
                "avg_trade_duration": 0.0,  # TODO: Calculate from historical data
                "sharpe_ratio": 0.0,  # TODO: Calculate from historical performance
                "max_drawdown": 0.0  # TODO: Calculate from historical data
            }
            
            if positions:
                performance_metrics["win_rate"] = (
                    performance_metrics["winning_positions"] / len(positions) * 100
                )
            
            return {
                "avg_leverage": avg_leverage,
                "risk_score": int(weighted_risk_score),
                "risk_metrics": risk_metrics,
                "performance_metrics": performance_metrics
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            return {
                "avg_leverage": 0.0,
                "risk_score": 0,
                "risk_metrics": {},
                "performance_metrics": {}
            }
    
    def _calculate_concentration_risk(self, positions: List[Dict]) -> str:
        """Calculate concentration risk based on position distribution"""
        if not positions:
            return "LOW"
        
        try:
            total_value = sum(float(p.get("position_value", 0)) for p in positions)
            if total_value <= 0:
                return "LOW"
            
            # Calculate largest position percentage
            largest_position = max(float(p.get("position_value", 0)) for p in positions)
            largest_percentage = (largest_position / total_value) * 100
            
            # Calculate top 5 positions percentage
            sorted_positions = sorted(positions, key=lambda x: float(x.get("position_value", 0)), reverse=True)
            top_5_value = sum(float(p.get("position_value", 0)) for p in sorted_positions[:5])
            top_5_percentage = (top_5_value / total_value) * 100
            
            if largest_percentage > 30 or top_5_percentage > 70:
                return "HIGH"
            elif largest_percentage > 15 or top_5_percentage > 50:
                return "MEDIUM"
            else:
                return "LOW"
                
        except Exception as e:
            logger.error(f"Error calculating concentration risk: {e}")
            return "UNKNOWN"
    
    async def _calculate_symbol_allocation(self, positions: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Calculate allocation by symbol"""
        try:
            symbol_data = {}
            total_value = sum(float(p.get("position_value", 0)) for p in positions)
            
            for position in positions:
                symbol = position.get("symbol", "UNKNOWN")
                position_value = float(position.get("position_value", 0))
                
                if symbol not in symbol_data:
                    symbol_data[symbol] = {
                        "total_value": 0.0,
                        "position_count": 0,
                        "allocation_percentage": 0.0,
                        "net_pnl": 0.0,
                        "avg_leverage": 0.0,
                        "positions": []
                    }
                
                symbol_data[symbol]["total_value"] += position_value
                symbol_data[symbol]["position_count"] += 1
                symbol_data[symbol]["net_pnl"] += float(position.get("pnl_amount", 0))
                symbol_data[symbol]["avg_leverage"] += float(position.get("leverage", 1))
                symbol_data[symbol]["positions"].append(position)
            
            # Calculate percentages and averages
            for symbol, data in symbol_data.items():
                if total_value > 0:
                    data["allocation_percentage"] = (data["total_value"] / total_value) * 100
                data["avg_leverage"] = data["avg_leverage"] / data["position_count"]
            
            return symbol_data
            
        except Exception as e:
            logger.error(f"Error calculating symbol allocation: {e}")
            return {}
    
    async def _store_portfolio_snapshot(self, portfolio_summary: PortfolioSummary):
        """Store portfolio snapshot for historical tracking"""
        try:
            snapshot = PortfolioSnapshot(
                total_positions=portfolio_summary.total_positions,
                active_positions=portfolio_summary.active_positions,
                total_pnl=portfolio_summary.total_unrealized_pnl,
                net_exposure=portfolio_summary.net_exposure,
                total_exposure=portfolio_summary.total_exposure,
                portfolio_value=portfolio_summary.portfolio_value,
                avg_leverage=portfolio_summary.avg_leverage,
                risk_score=portfolio_summary.portfolio_risk_score,
                long_positions_count=portfolio_summary.long_summary.count,
                short_positions_count=portfolio_summary.short_summary.count,
                validation_score=portfolio_summary.validation_status.validation_score,
                created_at=datetime.now(timezone.utc)
            )
            
            self.db.add(snapshot)
            self.db.commit()
            
            # Store validation log if there are issues
            if not portfolio_summary.validation_status.is_valid:
                validation_log = ValidationLog(
                    validation_type="portfolio_aggregation",
                    validation_score=portfolio_summary.validation_status.validation_score,
                    discrepancies_count=len(portfolio_summary.validation_status.discrepancies),
                    critical_issues=len([d for d in portfolio_summary.validation_status.discrepancies if d.severity == "critical"]),
                    details=str(portfolio_summary.validation_status.discrepancies[:10]),  # Store first 10
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(validation_log)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error storing portfolio snapshot: {e}")
    
    async def _create_error_portfolio_summary(self, 
                                            positions: List[Dict], 
                                            error_message: str) -> PortfolioSummary:
        """Create minimal portfolio summary when aggregation fails"""
        return PortfolioSummary(
            total_positions=len(positions),
            active_positions=0,
            total_unrealized_pnl=Decimal('0.00'),
            total_realized_pnl=Decimal('0.00'),
            net_exposure=Decimal('0.00'),
            total_exposure=Decimal('0.00'),
            portfolio_value=Decimal('0.00'),
            available_balance=Decimal('0.00'),
            total_margin=Decimal('0.00'),
            avg_leverage=0.0,
            portfolio_risk_score=0,
            long_summary=DirectionSummary(
                count=0, total_value=Decimal('0.00'), unrealized_pnl=Decimal('0.00'),
                realized_pnl=Decimal('0.00'), avg_leverage=0.0, weighted_avg_leverage=0.0,
                risk_distribution={}, pnl_distribution={}, top_positions=[], positions=[],
                total_margin=Decimal('0.00'), avg_entry_price=0.0, avg_current_price=0.0
            ),
            short_summary=DirectionSummary(
                count=0, total_value=Decimal('0.00'), unrealized_pnl=Decimal('0.00'),
                realized_pnl=Decimal('0.00'), avg_leverage=0.0, weighted_avg_leverage=0.0,
                risk_distribution={}, pnl_distribution={}, top_positions=[], positions=[],
                total_margin=Decimal('0.00'), avg_entry_price=0.0, avg_current_price=0.0
            ),
            net_exposure_data=NetExposureData(
                long_exposure=Decimal('0.00'), short_exposure=Decimal('0.00'),
                net_exposure=Decimal('0.00'), total_exposure=Decimal('0.00'),
                net_ratio=0.0, exposure_balance="Unknown",
                leverage_weighted_exposure=Decimal('0.00'), risk_adjusted_exposure=Decimal('0.00')
            ),
            symbol_allocation={},
            risk_metrics={},
            performance_metrics={},
            validation_status=ValidationStatus(
                is_valid=False, validation_score=0.0,
                discrepancies=[ValidationDiscrepancy(
                    field="aggregation_error", expected=1, actual=0, difference=1,
                    severity="critical", description=error_message
                )],
                last_validated=datetime.now(timezone.utc),
                validation_warnings=[f"Aggregation failed: {error_message}"],
                total_checks=1, passed_checks=0
            ),
            last_calculated=datetime.now(timezone.utc),
            calculation_duration=0.0
        )