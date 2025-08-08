"""
Browser Automation Service using Puppeteer-like functionality
Provides comprehensive browser automation for testing and interaction
"""

import asyncio
import logging
import json
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BrowserService:
    """Browser automation service with comprehensive testing capabilities"""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        
    async def initialize(self):
        """Initialize browser automation service"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available. Browser automation disabled.")
            return False
            
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("✅ Browser service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize browser service: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup browser resources"""
        try:
            # Close all pages and contexts
            for page in self.pages.values():
                await page.close()
            for context in self.contexts.values():
                await context.close()
            
            # Close browser
            if self.browser:
                await self.browser.close()
            
            # Stop playwright
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("✅ Browser service cleaned up")
        except Exception as e:
            logger.error(f"❌ Error during browser cleanup: {e}")
    
    async def create_context(self, context_id: str = "default", **options) -> str:
        """Create a new browser context"""
        if not self.browser:
            raise RuntimeError("Browser not initialized")
        
        context_options = {
            "viewport": {
                "width": settings.BROWSER_VIEWPORT_WIDTH,
                "height": settings.BROWSER_VIEWPORT_HEIGHT
            },
            **options
        }
        
        context = await self.browser.new_context(**context_options)
        self.contexts[context_id] = context
        
        logger.info(f"Created browser context: {context_id}")
        return context_id
    
    async def create_page(self, page_id: str = "default", context_id: str = "default") -> str:
        """Create a new page in the specified context"""
        if context_id not in self.contexts:
            await self.create_context(context_id)
        
        context = self.contexts[context_id]
        page = await context.new_page()
        self.pages[page_id] = page
        
        logger.info(f"Created page: {page_id} in context: {context_id}")
        return page_id
    
    async def navigate(self, url: str, page_id: str = "default", wait_until: str = "networkidle") -> Dict[str, Any]:
        """Navigate to a URL"""
        if page_id not in self.pages:
            await self.create_page(page_id)
        
        page = self.pages[page_id]
        
        try:
            response = await page.goto(url, wait_until=wait_until, timeout=settings.BROWSER_TIMEOUT)
            
            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None
            }
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def click(self, selector: str, page_id: str = "default", **options) -> Dict[str, Any]:
        """Click an element"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        try:
            await page.click(selector, timeout=settings.BROWSER_TIMEOUT, **options)
            return {"success": True}
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def type_text(self, selector: str, text: str, page_id: str = "default", **options) -> Dict[str, Any]:
        """Type text into an element"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        try:
            await page.fill(selector, text, timeout=settings.BROWSER_TIMEOUT, **options)
            return {"success": True}
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def wait_for_selector(self, selector: str, page_id: str = "default", **options) -> Dict[str, Any]:
        """Wait for an element to appear"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        try:
            await page.wait_for_selector(selector, timeout=settings.BROWSER_TIMEOUT, **options)
            return {"success": True}
        except Exception as e:
            logger.error(f"Wait for selector failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def screenshot(self, page_id: str = "default", filename: Optional[str] = None, **options) -> Dict[str, Any]:
        """Take a screenshot"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        
        filepath = self.screenshots_dir / filename
        
        try:
            await page.screenshot(path=str(filepath), **options)
            
            # Return base64 encoded screenshot for API response
            with open(filepath, "rb") as f:
                screenshot_data = base64.b64encode(f.read()).decode()
            
            return {
                "success": True,
                "filename": filename,
                "filepath": str(filepath),
                "data": screenshot_data
            }
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def evaluate(self, script: str, page_id: str = "default") -> Dict[str, Any]:
        """Execute JavaScript in the page"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        try:
            result = await page.evaluate(script)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Script evaluation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_page_info(self, page_id: str = "default") -> Dict[str, Any]:
        """Get current page information"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        page = self.pages[page_id]
        
        try:
            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size
            }
        except Exception as e:
            logger.error(f"Get page info failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def close_page(self, page_id: str) -> Dict[str, Any]:
        """Close a specific page"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        try:
            page = self.pages[page_id]
            await page.close()
            del self.pages[page_id]
            return {"success": True}
        except Exception as e:
            logger.error(f"Close page failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_console_logs(self, page_id: str = "default") -> Dict[str, Any]:
        """Get console logs from the page"""
        if page_id not in self.pages:
            return {"success": False, "error": "Page not found"}
        
        # Note: This is a simplified implementation
        # In a real implementation, you'd need to set up console event listeners
        return {
            "success": True,
            "logs": [],
            "note": "Console logging requires event listener setup"
        }