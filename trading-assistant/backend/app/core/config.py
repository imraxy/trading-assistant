"""
Configuration management for AI Trading Assistant
"""

import os
from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings"""
    
    # App Configuration
    APP_NAME: str = "AI Trading Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./trading_assistant.db"
    
    # External APIs
    BYBIT_API_KEY: Optional[str] = None
    BYBIT_API_SECRET: Optional[str] = None
    BYBIT_TESTNET: bool = True
    
    # LLM / AI Providers
    AI_PROVIDER: str = "openai"  # openai|gemini
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.2
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # Aggregators and Router
    AGGREGATORS_ENABLED: bool = True
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    CHUTES_API_KEY: Optional[str] = None
    NIM_API_KEY: Optional[str] = None
    NIM_TOKEN: Optional[str] = None
    NIM_BASE_URL: Optional[str] = "https://integrate.api.nvidia.com"
    AGGREGATOR_OPTOUT_OPENROUTER: bool = False
    AGGREGATOR_OPTOUT_CHUTES: bool = False
    AGGREGATOR_OPTOUT_NIM: bool = False

    CATALOG_REFRESH_INTERVAL_HOURS: int = 24
    CATALOG_CACHE_PATH: str = "./.cache/models_catalog.json"

    ROUTER_BUDGET_CEILING_USD_PER_M: float = 5.0
    ROUTER_LATENCY_TARGET_MS: int = 2000
    
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    NEWS_API_KEY: Optional[str] = None
    
    # Browser Automation
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000
    BROWSER_VIEWPORT_WIDTH: int = 1920
    BROWSER_VIEWPORT_HEIGHT: int = 1080
    
    # Task Management
    TASK_TIMEOUT: int = 300  # 5 minutes
    MAX_CONCURRENT_TASKS: int = 5
    
    @validator("DEBUG", pre=True)
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)
    
    @validator("BYBIT_TESTNET", pre=True)
    def parse_testnet(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)
    
    @validator("BROWSER_HEADLESS", pre=True)
    def parse_headless(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)
    
    # Use explicit python-dotenv loading order in app.main; do not pin here
    model_config = {"case_sensitive": True, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()