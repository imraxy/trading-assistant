"""
Comprehensive Browser Functionality Test Suite
Tests all browser automation features and API endpoints
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.services.browser_service import BrowserService


class TestBrowserService:
    """Test the browser service directly"""
    
    @pytest.fixture
    async def browser_service(self):
        """Create a browser service instance for testing"""
        service = BrowserService()
        # Mock playwright for testing
        service.playwright = Mock()
        service.browser = Mock()
        yield service
        await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_browser_service_initialization(self, browser_service):
        """Test browser service initialization"""
        with patch('app.services.browser_service.PLAYWRIGHT_AVAILABLE', True):
            with patch('app.services.browser_service.async_playwright') as mock_playwright:
                mock_playwright.return_value.start = AsyncMock()
                mock_playwright.return_value.start.return_value.chromium.launch = AsyncMock()
                
                result = await browser_service.initialize()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_create_context(self, browser_service):
        """Test browser context creation"""
        browser_service.browser = Mock()
        browser_service.browser.new_context = AsyncMock()
        
        context_id = await browser_service.create_context("test_context")
        assert context_id == "test_context"
        assert "test_context" in browser_service.contexts
    
    @pytest.mark.asyncio
    async def test_create_page(self, browser_service):
        """Test page creation"""
        mock_context = Mock()
        mock_context.new_page = AsyncMock()
        browser_service.contexts["test_context"] = mock_context
        
        page_id = await browser_service.create_page("test_page", "test_context")
        assert page_id == "test_page"
        assert "test_page" in browser_service.pages
    
    @pytest.mark.asyncio
    async def test_navigate(self, browser_service):
        """Test page navigation"""
        mock_page = Mock()
        mock_response = Mock()
        mock_response.status = 200
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test Page")
        
        browser_service.pages["test_page"] = mock_page
        
        result = await browser_service.navigate("https://example.com", "test_page")
        
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["status"] == 200
    
    @pytest.mark.asyncio
    async def test_click_element(self, browser_service):
        """Test element clicking"""
        mock_page = Mock()
        mock_page.click = AsyncMock()
        browser_service.pages["test_page"] = mock_page
        
        result = await browser_service.click("#test-button", "test_page")
        
        assert result["success"] is True
        mock_page.click.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_type_text(self, browser_service):
        """Test text typing"""
        mock_page = Mock()
        mock_page.fill = AsyncMock()
        browser_service.pages["test_page"] = mock_page
        
        result = await browser_service.type_text("#input", "test text", "test_page")
        
        assert result["success"] is True
        mock_page.fill.assert_called_once_with("#input", "test text", timeout=30000)
    
    @pytest.mark.asyncio
    async def test_screenshot(self, browser_service):
        """Test screenshot functionality"""
        mock_page = Mock()
        mock_page.screenshot = AsyncMock()
        browser_service.pages["test_page"] = mock_page
        
        with patch('builtins.open', create=True) as mock_open:
            with patch('base64.b64encode') as mock_b64:
                mock_b64.return_value.decode.return_value = "base64data"
                
                result = await browser_service.screenshot("test_page")
                
                assert result["success"] is True
                assert "filename" in result
                assert "data" in result


class TestBrowserAPI:
    """Test the browser API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_browser_service(self):
        """Mock browser service"""
        service = Mock()
        service.create_context = AsyncMock(return_value="test_context")
        service.create_page = AsyncMock(return_value="test_page")
        service.navigate = AsyncMock(return_value={"success": True, "url": "https://example.com"})
        service.click = AsyncMock(return_value={"success": True})
        service.type_text = AsyncMock(return_value={"success": True})
        service.screenshot = AsyncMock(return_value={
            "success": True,
            "filename": "test.png",
            "filepath": "/path/to/test.png",
            "data": "base64data"
        })
        service.evaluate = AsyncMock(return_value={"success": True, "result": "test"})
        service.get_page_info = AsyncMock(return_value={
            "success": True,
            "url": "https://example.com",
            "title": "Test Page"
        })
        service.close_page = AsyncMock(return_value={"success": True})
        service.contexts = {}
        service.pages = {}
        service.browser = Mock()
        return service
    
    def test_launch_browser(self, client, mock_browser_service):
        """Test browser launch endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/launch", json={
                "page_id": "test",
                "context_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["data"]["page_id"] == "test"
            assert data["data"]["context_id"] == "test"
    
    def test_navigate_endpoint(self, client, mock_browser_service):
        """Test navigation endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/navigate", json={
                "url": "https://example.com",
                "page_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_click_endpoint(self, client, mock_browser_service):
        """Test click endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/click", json={
                "selector": "#test-button",
                "page_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_type_endpoint(self, client, mock_browser_service):
        """Test type endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/type", json={
                "selector": "#input",
                "text": "test text",
                "page_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_screenshot_endpoint(self, client, mock_browser_service):
        """Test screenshot endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/screenshot", json={
                "page_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "screenshot_data" in data["data"]
    
    def test_evaluate_endpoint(self, client, mock_browser_service):
        """Test JavaScript evaluation endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.post("/api/v1/browser/evaluate", json={
                "script": "document.title",
                "page_id": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_browser_status_endpoint(self, client, mock_browser_service):
        """Test browser status endpoint"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            response = client.get("/api/v1/browser/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "service_available" in data["data"]
    
    def test_browser_service_not_available(self, client):
        """Test endpoints when browser service is not available"""
        with patch.object(app.state, 'browser_service', None):
            response = client.post("/api/v1/browser/launch", json={})
            assert response.status_code == 503


class TestEndToEndScenarios:
    """End-to-end browser automation test scenarios"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def mock_browser_service(self):
        """Mock browser service for E2E tests"""
        service = Mock()
        
        # Mock a complete browser session
        service.create_context = AsyncMock(return_value="e2e_context")
        service.create_page = AsyncMock(return_value="e2e_page")
        service.navigate = AsyncMock(return_value={
            "success": True,
            "url": "http://localhost:8000",
            "title": "AI Trading Assistant",
            "status": 200
        })
        service.wait_for_selector = AsyncMock(return_value={"success": True})
        service.click = AsyncMock(return_value={"success": True})
        service.type_text = AsyncMock(return_value={"success": True})
        service.screenshot = AsyncMock(return_value={
            "success": True,
            "filename": "e2e_test.png",
            "filepath": "/screenshots/e2e_test.png",
            "data": "base64screenshot"
        })
        service.evaluate = AsyncMock(return_value={
            "success": True,
            "result": {"positions": 2, "connected": True}
        })
        service.close_page = AsyncMock(return_value={"success": True})
        
        service.contexts = {}
        service.pages = {}
        service.browser = Mock()
        
        return service
    
    def test_complete_trading_dashboard_interaction(self, client, mock_browser_service):
        """Test complete interaction with trading dashboard"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            # 1. Launch browser
            response = client.post("/api/v1/browser/launch", json={
                "page_id": "dashboard_test",
                "context_id": "trading_session"
            })
            assert response.status_code == 200
            
            # 2. Navigate to dashboard
            response = client.post("/api/v1/browser/navigate", json={
                "url": "http://localhost:8000",
                "page_id": "dashboard_test",
                "wait_until": "networkidle"
            })
            assert response.status_code == 200
            
            # 3. Wait for dashboard to load
            response = client.post("/api/v1/browser/wait", json={
                "selector": ".trading-dashboard",
                "page_id": "dashboard_test",
                "timeout": 10000
            })
            assert response.status_code == 200
            
            # 4. Click refresh button
            response = client.post("/api/v1/browser/click", json={
                "selector": "button[onclick*='refreshData']",
                "page_id": "dashboard_test"
            })
            assert response.status_code == 200
            
            # 5. Take screenshot of dashboard
            response = client.post("/api/v1/browser/screenshot", json={
                "page_id": "dashboard_test",
                "filename": "dashboard_loaded.png",
                "full_page": True
            })
            assert response.status_code == 200
            data = response.json()
            assert "screenshot_data" in data["data"]
            
            # 6. Evaluate dashboard state
            response = client.post("/api/v1/browser/evaluate", json={
                "script": """
                ({
                    positions: document.querySelectorAll('.position-row').length,
                    connected: document.querySelector('.connection-status').textContent.includes('Connected'),
                    totalPnl: document.querySelector('.total-pnl')?.textContent || '0'
                })
                """,
                "page_id": "dashboard_test"
            })
            assert response.status_code == 200
            
            # 7. Close browser
            response = client.delete("/api/v1/browser/close?page_id=dashboard_test")
            assert response.status_code == 200
    
    def test_form_interaction_scenario(self, client, mock_browser_service):
        """Test form interaction scenario"""
        with patch.object(app.state, 'browser_service', mock_browser_service):
            # Launch and navigate
            client.post("/api/v1/browser/launch", json={"page_id": "form_test"})
            client.post("/api/v1/browser/navigate", json={
                "url": "http://localhost:8000",
                "page_id": "form_test"
            })
            
            # Fill form fields
            response = client.post("/api/v1/browser/type", json={
                "selector": "#api-key-input",
                "text": "test_api_key_123",
                "page_id": "form_test"
            })
            assert response.status_code == 200
            
            # Submit form
            response = client.post("/api/v1/browser/click", json={
                "selector": "#submit-button",
                "page_id": "form_test"
            })
            assert response.status_code == 200
    
    def test_error_handling_scenario(self, client, mock_browser_service):
        """Test error handling in browser automation"""
        # Mock service to return errors
        mock_browser_service.navigate = AsyncMock(return_value={
            "success": False,
            "error": "Navigation timeout"
        })
        
        with patch.object(app.state, 'browser_service', mock_browser_service):
            client.post("/api/v1/browser/launch", json={"page_id": "error_test"})
            
            response = client.post("/api/v1/browser/navigate", json={
                "url": "http://invalid-url",
                "page_id": "error_test"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "Navigation timeout" in data["detail"]


class TestPerformanceAndReliability:
    """Test performance and reliability aspects"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_concurrent_browser_sessions(self, client):
        """Test handling multiple concurrent browser sessions"""
        mock_service = Mock()
        mock_service.create_context = AsyncMock(side_effect=lambda x: x)
        mock_service.create_page = AsyncMock(side_effect=lambda x, y: x)
        mock_service.contexts = {}
        mock_service.pages = {}
        mock_service.browser = Mock()
        
        with patch.object(app.state, 'browser_service', mock_service):
            # Create multiple sessions
            sessions = []
            for i in range(5):
                response = client.post("/api/v1/browser/launch", json={
                    "page_id": f"session_{i}",
                    "context_id": f"context_{i}"
                })
                assert response.status_code == 200
                sessions.append(response.json())
            
            # Verify all sessions were created
            assert len(sessions) == 5
    
    def test_browser_service_recovery(self, client):
        """Test browser service recovery after failure"""
        mock_service = Mock()
        mock_service.browser = None  # Simulate uninitialized state
        mock_service.contexts = {}
        mock_service.pages = {}
        
        with patch.object(app.state, 'browser_service', mock_service):
            response = client.get("/api/v1/browser/status")
            assert response.status_code == 200
            
            data = response.json()
            assert data["data"]["browser_initialized"] is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])