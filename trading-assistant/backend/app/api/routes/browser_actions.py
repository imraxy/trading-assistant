"""
Browser Actions API Routes
Provides comprehensive browser automation endpoints
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class BrowserActionRequest(BaseModel):
    """Base browser action request"""
    page_id: str = Field(default="default", description="Page identifier")
    context_id: str = Field(default="default", description="Browser context identifier")


class NavigateRequest(BrowserActionRequest):
    """Navigate to URL request"""
    url: str = Field(..., description="URL to navigate to")
    wait_until: str = Field(default="networkidle", description="Wait condition")


class ClickRequest(BrowserActionRequest):
    """Click element request"""
    selector: str = Field(..., description="CSS selector")
    button: str = Field(default="left", description="Mouse button")
    click_count: int = Field(default=1, description="Number of clicks")


class TypeRequest(BrowserActionRequest):
    """Type text request"""
    selector: str = Field(..., description="CSS selector")
    text: str = Field(..., description="Text to type")
    delay: int = Field(default=0, description="Delay between keystrokes")


class WaitRequest(BrowserActionRequest):
    """Wait for element request"""
    selector: str = Field(..., description="CSS selector to wait for")
    timeout: int = Field(default=30000, description="Timeout in milliseconds")
    state: str = Field(default="visible", description="Element state to wait for")


class ScreenshotRequest(BrowserActionRequest):
    """Screenshot request"""
    filename: Optional[str] = Field(None, description="Screenshot filename")
    full_page: bool = Field(default=False, description="Capture full page")
    quality: int = Field(default=80, description="JPEG quality (0-100)")


class EvaluateRequest(BrowserActionRequest):
    """JavaScript evaluation request"""
    script: str = Field(..., description="JavaScript code to execute")


class SnapshotRequest(BaseModel):
    """Capture snapshot of a URL and return image + logs"""
    url: str
    page_id: str = Field(default="assistant", description="Page identifier")
    full_page: bool = False


def get_browser_service(request: Request):
    """Get browser service from app state"""
    if not hasattr(request.app.state, 'browser_service') or not request.app.state.browser_service:
        raise HTTPException(status_code=503, detail="Browser service not available")
    return request.app.state.browser_service


@router.post("/browser/launch")
async def launch_browser(
    request: BrowserActionRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Launch a new browser context and page"""
    try:
        context_id = await browser_service.create_context(request.context_id)
        page_id = await browser_service.create_page(request.page_id, context_id)
        
        return {
            "status": "success",
            "data": {
                "context_id": context_id,
                "page_id": page_id,
                "message": "Browser launched successfully"
            }
        }
    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/navigate")
async def navigate_to_url(
    request: NavigateRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Navigate to a URL"""
    try:
        result = await browser_service.navigate(
            url=request.url,
            page_id=request.page_id,
            wait_until=request.wait_until
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Navigation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/click")
async def click_element(
    request: ClickRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Click an element"""
    try:
        result = await browser_service.click(
            selector=request.selector,
            page_id=request.page_id,
            button=request.button,
            click_count=request.click_count
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": {"message": "Element clicked successfully"}
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Click failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Click failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/type")
async def type_text(
    request: TypeRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Type text into an element"""
    try:
        result = await browser_service.type_text(
            selector=request.selector,
            text=request.text,
            page_id=request.page_id,
            delay=request.delay
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": {"message": "Text typed successfully"}
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Type failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Type failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/wait")
async def wait_for_element(
    request: WaitRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Wait for an element to appear"""
    try:
        result = await browser_service.wait_for_selector(
            selector=request.selector,
            page_id=request.page_id,
            timeout=request.timeout,
            state=request.state
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": {"message": "Element found"}
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Wait failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Wait failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/screenshot")
async def take_screenshot(
    request: ScreenshotRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Take a screenshot"""
    try:
        result = await browser_service.screenshot(
            page_id=request.page_id,
            filename=request.filename,
            full_page=request.full_page,
            quality=request.quality
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": {
                    "filename": result["filename"],
                    "filepath": result["filepath"],
                    "screenshot_data": result["data"]
                }
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Screenshot failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/evaluate")
async def evaluate_javascript(
    request: EvaluateRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Execute JavaScript in the page"""
    try:
        result = await browser_service.evaluate(
            script=request.script,
            page_id=request.page_id
        )
        
        if result["success"]:
            return {
                "status": "success",
                "data": {"result": result["result"]}
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Script evaluation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Script evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browser/snapshot")
async def capture_snapshot(
    request: SnapshotRequest,
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Capture a screenshot and return base64 image + logs"""
    try:
        result = await browser_service.capture_snapshot(
            url=request.url, page_id=request.page_id, full_page=request.full_page
        )
        if result.get("success"):
            return {"status": "success", "data": result}
        raise HTTPException(status_code=400, detail=result.get("error", "Snapshot failed"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser/info")
async def get_page_info(
    page_id: str = "default",
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Get current page information"""
    try:
        result = await browser_service.get_page_info(page_id=page_id)
        
        if result["success"]:
            return {
                "status": "success",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to get page info"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get page info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/browser/close")
async def close_browser(
    page_id: str = "default",
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Close a browser page"""
    try:
        result = await browser_service.close_page(page_id=page_id)
        
        if result["success"]:
            return {
                "status": "success",
                "data": {"message": "Page closed successfully"}
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to close page"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close page failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser/status")
async def get_browser_status(
    browser_service = Depends(get_browser_service)
) -> Dict[str, Any]:
    """Get browser service status"""
    try:
        return {
            "status": "success",
            "data": {
                "service_available": True,
                "active_contexts": len(browser_service.contexts),
                "active_pages": len(browser_service.pages),
                "browser_initialized": browser_service.browser is not None
            }
        }
    except Exception as e:
        logger.error(f"Get browser status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))