"""
Database Models for AI Trading Assistant

SQLAlchemy ORM models for all data entities including accounts,
positions, market data, technical indicators, and analysis results.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.database import Base
from datetime import datetime, timezone


class Account(Base):
    """Trading account information"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    exchange = Column(String(50), nullable=False)  # bybit, 3commas, etc
    api_key_encrypted = Column(Text, nullable=True)  # Encrypted API key
    api_secret_encrypted = Column(Text, nullable=True)  # Encrypted API secret
    is_testnet = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    positions = relationship("Position", back_populates="account")
    
    # Indexes
    __table_args__ = (
        Index('idx_account_exchange', 'exchange'),
        Index('idx_account_active', 'is_active'),
    )


class Position(Base):
    """Trading position information"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # Buy/Sell, Long/Short
    size = Column(DECIMAL(20, 8), nullable=False)
    entry_price = Column(DECIMAL(20, 8), nullable=False)
    current_price = Column(DECIMAL(20, 8), nullable=True)
    pnl_amount = Column(DECIMAL(20, 8), nullable=True)
    pnl_percentage = Column(DECIMAL(10, 4), nullable=True)
    leverage = Column(Integer, nullable=True)
    margin = Column(DECIMAL(20, 8), nullable=True)
    liquidation_price = Column(DECIMAL(20, 8), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="positions")
    technical_indicators = relationship("TechnicalIndicator", back_populates="position")
    analysis_results = relationship("AnalysisResult", back_populates="position")
    
    # Indexes
    __table_args__ = (
        Index('idx_position_symbol', 'symbol'),
        Index('idx_position_account', 'account_id'),
        Index('idx_position_active', 'is_active'),
        Index('idx_position_symbol_account', 'symbol', 'account_id'),
    )


class MarketData(Base):
    """Market data (candlesticks, prices, volume)"""
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 1h, 1d, etc
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(DECIMAL(20, 8), nullable=False)
    high = Column(DECIMAL(20, 8), nullable=False)
    low = Column(DECIMAL(20, 8), nullable=False)
    close = Column(DECIMAL(20, 8), nullable=False)
    volume = Column(DECIMAL(20, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_market_data_symbol', 'symbol'),
        Index('idx_market_data_timeframe', 'timeframe'),
        Index('idx_market_data_timestamp', 'timestamp'),
        Index('idx_market_data_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp'),
    )


class TechnicalIndicator(Base):
    """Technical analysis indicators"""
    __tablename__ = "technical_indicators"
    
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)
    indicator_name = Column(String(50), nullable=False)  # RSI, MACD, EMA, etc
    value = Column(DECIMAL(20, 8), nullable=False)
    signal = Column(String(20), nullable=True)  # BUY, SELL, HOLD
    confidence = Column(DECIMAL(5, 4), nullable=True)  # 0.0 to 1.0
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    position = relationship("Position", back_populates="technical_indicators")
    
    # Indexes
    __table_args__ = (
        Index('idx_technical_symbol', 'symbol'),
        Index('idx_technical_indicator', 'indicator_name'),
        Index('idx_technical_timestamp', 'timestamp'),
        Index('idx_technical_symbol_indicator_timestamp', 'symbol', 'indicator_name', 'timestamp'),
    )


class AnalysisResult(Base):
    """AI analysis results and recommendations"""
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    symbol = Column(String(50), nullable=False)
    recommendation = Column(String(20), nullable=False)  # HOLD, EXIT, ADD, WATCH
    technical_score = Column(DECIMAL(5, 4), nullable=True)  # 0.0 to 1.0
    sentiment_score = Column(DECIMAL(5, 4), nullable=True)  # 0.0 to 1.0
    fundamental_score = Column(DECIMAL(5, 4), nullable=True)  # 0.0 to 1.0
    overall_confidence = Column(DECIMAL(5, 4), nullable=True)  # 0.0 to 1.0
    reasoning = Column(Text, nullable=True)  # AI explanation
    risk_level = Column(String(20), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    target_price = Column(DECIMAL(20, 8), nullable=True)
    stop_loss = Column(DECIMAL(20, 8), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    position = relationship("Position", back_populates="analysis_results")
    
    # Indexes
    __table_args__ = (
        Index('idx_analysis_symbol', 'symbol'),
        Index('idx_analysis_recommendation', 'recommendation'),
        Index('idx_analysis_risk_level', 'risk_level'),
        Index('idx_analysis_timestamp', 'created_at'),
    )


class Setting(Base):
    """Application settings and configuration"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # api, analysis, notification, etc
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_setting_key', 'key'),
        Index('idx_setting_category', 'category'),
    )


class Alert(Base):
    """Trading alerts and notifications"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    alert_type = Column(String(50), nullable=False)  # PRICE, INDICATOR, AI_SIGNAL
    trigger_condition = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # INFO, WARNING, CRITICAL
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_symbol', 'symbol'),
        Index('idx_alert_type', 'alert_type'),
        Index('idx_alert_severity', 'severity'),
        Index('idx_alert_sent', 'is_sent'),
    ) 