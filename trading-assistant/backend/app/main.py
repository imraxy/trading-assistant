"""
AI Trading Assistant - FastAPI Backend
Main application entry point with browser automation support
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import health, positions, browser_actions, market_data, portfolio
from .api.routes import research
from .api.routes import chat
from .core.config import get_settings
from .services.llm_provider import available_providers, suggested_models, get_models_map
from .core.logging import setup_logging
from dotenv import load_dotenv

# Load environment variables from backend/.env and backend/app/.env so os.getenv works across services
try:
    _here = os.path.dirname(__file__)
    _env_path_backend = os.path.abspath(os.path.join(_here, "..", ".env"))
    load_dotenv(_env_path_backend)
    # Also try app/.env if present (some setups keep env here)
    _env_path_app = os.path.abspath(os.path.join(_here, ".env"))
    load_dotenv(_env_path_app, override=False)
except Exception:
    pass

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 Starting AI Trading Assistant Backend")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Initialize browser automation service
    try:
        from .services.browser_service import BrowserService
        browser_service = BrowserService()
        await browser_service.initialize()
        app.state.browser_service = browser_service
        logger.info("✅ Browser automation service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Browser service initialization failed: {e}")
        app.state.browser_service = None
    
    # Test Bybit connection
    try:
        from .services.bybit_service import bybit_service
        connection_test = await bybit_service.test_connection()
        if connection_test.get("connected"):
            logger.info("✅ Bybit API connection successful")
        else:
            logger.warning(f"⚠️ Bybit API connection failed: {connection_test.get('error')}")
    except Exception as e:
        logger.warning(f"⚠️ Bybit API test failed: {e}")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down AI Trading Assistant Backend")
    if hasattr(app.state, 'browser_service') and app.state.browser_service:
        await app.state.browser_service.cleanup()
        logger.info("✅ Browser service cleaned up")
    
    try:
        from .services.bybit_service import bybit_service
        await bybit_service.close()
        logger.info("✅ Bybit service cleaned up")
    except Exception as e:
        logger.warning(f"⚠️ Bybit service cleanup failed: {e}")


# Create FastAPI application
app = FastAPI(
    title="AI Trading Assistant",
    description="Real-time AI-powered trading assistant with Bybit integration, comprehensive portfolio analysis, and browser automation",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, tags=["Health"])
app.include_router(positions.router, prefix="/api/v1", tags=["Positions & Account"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio Analysis"])
app.include_router(browser_actions.router, prefix="/api/v1", tags=["Browser Actions"])
app.include_router(market_data.router, prefix="/api/v1", tags=["Market Data"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(research.router, prefix="/api/v1", tags=["Research"])

# Serve static files (frontend)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve the comprehensive portfolio dashboard"""
        # Try to serve the comprehensive dashboard first
        comprehensive_path = os.path.join(frontend_path, "comprehensive-portfolio-dashboard.html")
        if os.path.exists(comprehensive_path):
            return FileResponse(comprehensive_path)
        
        # Fallback to index.html
        index_path = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not found"}


@app.get("/api/v1/config")
async def get_config():
    """Get application configuration status"""
    # Live model discovery where possible; fall back to curated list
    _models = await get_models_map(prefer_live=True)
    _defaults = {prov: (mods[0] if mods else None) for prov, mods in _models.items()}
    return {
        "status": "success",
        "data": {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "version": "2.0.0",
            "features": {
                "browser_automation": hasattr(app.state, 'browser_service') and app.state.browser_service is not None,
                "bybit_integration": bool(settings.BYBIT_API_KEY),
                "openai_integration": bool(os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY),
                "gemini_integration": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
                "ai_provider": (os.getenv("AI_PROVIDER") or "openai"),
            },
            "llm_providers": available_providers(),
            "llm_models": _models,  # latest from providers when available
            "llm_defaults": _defaults,
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )