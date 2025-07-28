"""
Configuration Management System

Supports multiple configuration sources with priority:
1. Environment variables (highest priority)
2. Database settings (middle priority)  
3. Configuration files (lowest priority)
"""

import os
from typing import Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings
import yaml
from pathlib import Path


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    url: str = Field(default="sqlite:///./trading_assistant.db")  # SQLite default for development
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    echo: bool = Field(default=False)  # Set to True for SQL logging in development

    class Config:
        env_prefix = "DB_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class BybitConfig(BaseSettings):
    """Bybit API configuration"""
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    testnet: bool = Field(default=True)  # Start with testnet for safety
    base_url: str = Field(default="https://api-testnet.bybit.com")

    class Config:
        env_prefix = "BYBIT_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class OpenAIConfig(BaseSettings):
    """OpenAI API configuration"""
    api_key: Optional[str] = Field(default=None)
    model: str = Field(default="gpt-4")
    max_tokens: int = Field(default=1000)
    temperature: float = Field(default=0.1)

    class Config:
        env_prefix = "OPENAI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class AlphaVantageConfig(BaseSettings):
    """Alpha Vantage API configuration for technical indicators"""
    api_key: Optional[str] = Field(default="demo")  # Uses demo key if not configured

    class Config:
        env_prefix = "ALPHA_VANTAGE_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class NewsAPIConfig(BaseSettings):
    """NewsAPI configuration for sentiment analysis"""
    api_key: Optional[str] = Field(default=None)

    class Config:
        env_prefix = "NEWS_API_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class SecurityConfig(BaseSettings):
    """Security and encryption configuration"""
    secret_key: str = Field(default="local-development-secret-key-change-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    encryption_key: Optional[str] = Field(default=None)  # For API key encryption

    class Config:
        env_prefix = "SECURITY_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class AppConfig(BaseSettings):
    """Main application configuration"""
    debug: bool = Field(default=True)  # Default to True for development
    host: str = Field(default="127.0.0.1")  # Localhost for development
    port: int = Field(default=8000)
    workers: int = Field(default=1)
    log_level: str = Field(default="DEBUG")  # More verbose for development
    
    # Analysis settings
    analysis_interval: int = Field(default=30)  # seconds
    max_positions: int = Field(default=500)
    data_retention_days: int = Field(default=90)

    class Config:
        env_prefix = "APP_"
        env_file = ".env"
        env_file_encoding = "utf-8"


class Settings:
    """Main settings manager that combines all configuration sources"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.bybit = BybitConfig()
        self.openai = OpenAIConfig()
        self.alpha_vantage = AlphaVantageConfig()
        self.news_api = NewsAPIConfig()
        self.security = SecurityConfig()
        self.app = AppConfig()
        
        # Load additional config from files
        self._load_config_files()
        
        # Validate critical settings
        self._validate_config()
    
    def _load_config_files(self):
        """Load configuration from YAML files if they exist"""
        config_dir = Path(__file__).parent.parent / "config"
        
        # Load main config file
        main_config_path = config_dir / "config.yaml"
        if main_config_path.exists():
            with open(main_config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                self._apply_config_data(config_data)
        
        # Load environment-specific config
        env = os.getenv('ENVIRONMENT', 'development')
        env_config_path = config_dir / f"config.{env}.yaml"
        if env_config_path.exists():
            with open(env_config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                self._apply_config_data(config_data)
    
    def _apply_config_data(self, config_data: Dict[str, Any]):
        """Apply configuration data from files (only if not already set by env vars)"""
        if 'database' in config_data:
            for key, value in config_data['database'].items():
                if not hasattr(self.database, key) or getattr(self.database, key) is None:
                    setattr(self.database, key, value)
        
        if 'bybit' in config_data:
            for key, value in config_data['bybit'].items():
                if not hasattr(self.bybit, key) or getattr(self.bybit, key) is None:
                    setattr(self.bybit, key, value)
        
        if 'openai' in config_data:
            for key, value in config_data['openai'].items():
                if not hasattr(self.openai, key) or getattr(self.openai, key) is None:
                    setattr(self.openai, key, value)
        
        if 'alpha_vantage' in config_data:
            for key, value in config_data['alpha_vantage'].items():
                if not hasattr(self.alpha_vantage, key) or getattr(self.alpha_vantage, key) is None:
                    setattr(self.alpha_vantage, key, value)
        
        if 'news_api' in config_data:
            for key, value in config_data['news_api'].items():
                if not hasattr(self.news_api, key) or getattr(self.news_api, key) is None:
                    setattr(self.news_api, key, value)
        
        if 'app' in config_data:
            for key, value in config_data['app'].items():
                if not hasattr(self.app, key):
                    setattr(self.app, key, value)
        
        if 'security' in config_data:
            for key, value in config_data['security'].items():
                if not hasattr(self.security, key):
                    setattr(self.security, key, value)
    
    def _validate_config(self):
        """Validate that critical configuration is present"""
        warnings = []
        
        if not self.bybit.api_key:
            warnings.append("Bybit API key not configured - set BYBIT_API_KEY environment variable")
        
        if not self.openai.api_key:
            warnings.append("OpenAI API key not configured - set OPENAI_API_KEY environment variable")
        
        if not self.alpha_vantage.api_key or self.alpha_vantage.api_key == "demo":
            warnings.append("Alpha Vantage API key not configured - using demo key (limited functionality)")
        
        if not self.news_api.api_key:
            warnings.append("NewsAPI key not configured - sentiment analysis will be limited")
        
        if not self.security.encryption_key:
            warnings.append("Encryption key not configured - API keys will not be encrypted")
        
        if warnings:
            print("Configuration warnings:")
            for warning in warnings:
                print(f"  - {warning}")
            print("\nFor local development, you can set these environment variables:")
            print("  set BYBIT_API_KEY=your_api_key")
            print("  set BYBIT_API_SECRET=your_api_secret")
            print("  set OPENAI_API_KEY=your_openai_key")
            print("\nOptional for enhanced analysis:")
            print("  set ALPHA_VANTAGE_API_KEY=your_alphavantage_key")
            print("  set NEWS_API_API_KEY=your_newsapi_key")
    
    def get_database_url(self) -> str:
        """Get the database URL for SQLAlchemy"""
        return self.database.url
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    def is_sqlite(self) -> bool:
        """Check if using SQLite database"""
        return self.database.url.startswith('sqlite')


# Global settings instance
settings = Settings()


# Helper functions for easy access
def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings


def get_database_url() -> str:
    """Get the database URL"""
    return settings.get_database_url()


def is_debug() -> bool:
    """Check if debug mode is enabled"""
    return settings.app.debug 