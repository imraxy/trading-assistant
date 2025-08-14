/**
 * Real-time Browser Debugger
 * Provides comprehensive browser debugging capabilities
 */

class RealTimeBrowserDebugger {
    constructor() {
        this.isEnabled = false;
        this.debugPanel = null;
        this.logs = [];
        this.maxLogs = 1000;
        this.apiEndpoint = 'http://localhost:8000/api/v1';
        
        this.init();
    }
    
    init() {
        // Auto-enable in development
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            this.enable();
        }
        
        // Listen for debug commands
        window.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                this.toggle();
            }
        });
        
        // Capture console logs
        this.interceptConsole();
        
        // Capture network requests
        this.interceptFetch();
        
        // Monitor page performance
        this.monitorPerformance();
    }
    
    enable() {
        this.isEnabled = true;
        this.createDebugPanel();
        this.log('🔧 Real-time Browser Debugger enabled', 'info');
    }
    
    disable() {
        this.isEnabled = false;
        if (this.debugPanel) {
            this.debugPanel.remove();
            this.debugPanel = null;
        }
        this.log('🔧 Real-time Browser Debugger disabled', 'info');
    }
    
    toggle() {
        if (this.isEnabled) {
            this.disable();
        } else {
            this.enable();
        }
    }
    
    createDebugPanel() {
        if (this.debugPanel) return;
        
        this.debugPanel = document.createElement('div');
        this.debugPanel.id = 'browser-debugger-panel';
        this.debugPanel.innerHTML = `
            <div style="
                position: fixed;
                top: 10px;
                right: 10px;
                width: 400px;
                height: 300px;
                background: rgba(0, 0, 0, 0.9);
                color: #00ff00;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #333;
                border-radius: 5px;
                z-index: 10000;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            ">
                <div style="
                    background: #333;
                    padding: 5px 10px;
                    border-bottom: 1px solid #555;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <span>🔧 Browser Debugger</span>
                    <div>
                        <button onclick="window.browserDebugger.clearLogs()" style="
                            background: #555;
                            color: white;
                            border: none;
                            padding: 2px 6px;
                            margin-right: 5px;
                            border-radius: 3px;
                            cursor: pointer;
                        ">Clear</button>
                        <button onclick="window.browserDebugger.disable()" style="
                            background: #d32f2f;
                            color: white;
                            border: none;
                            padding: 2px 6px;
                            border-radius: 3px;
                            cursor: pointer;
                        ">×</button>
                    </div>
                </div>
                <div id="debug-logs" style="
                    flex: 1;
                    padding: 10px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                "></div>
                <div style="
                    background: #333;
                    padding: 5px 10px;
                    border-top: 1px solid #555;
                    font-size: 10px;
                    color: #888;
                ">
                    Ctrl+Shift+D to toggle | API: ${this.apiEndpoint}
                </div>
            </div>
        `;
        
        document.body.appendChild(this.debugPanel);
        this.updateLogDisplay();
    }
    
    log(message, level = 'info', data = null) {
        const timestamp = new Date().toISOString().substr(11, 12);
        const logEntry = {
            timestamp,
            level,
            message,
            data
        };
        
        this.logs.push(logEntry);
        
        // Keep only recent logs
        if (this.logs.length > this.maxLogs) {
            this.logs = this.logs.slice(-this.maxLogs);
        }
        
        if (this.isEnabled) {
            this.updateLogDisplay();
        }
        
        // Send to backend if available
        this.sendToBackend(logEntry);
    }
    
    updateLogDisplay() {
        if (!this.debugPanel) return;
        
        const logsContainer = this.debugPanel.querySelector('#debug-logs');
        if (!logsContainer) return;
        
        const recentLogs = this.logs.slice(-50); // Show last 50 logs
        logsContainer.innerHTML = recentLogs.map(log => {
            const color = this.getLogColor(log.level);
            return `<div style="color: ${color}; margin-bottom: 2px;">
                [${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}
                ${log.data ? '\n' + JSON.stringify(log.data, null, 2) : ''}
            </div>`;
        }).join('');
        
        // Auto-scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
    
    getLogColor(level) {
        const colors = {
            error: '#ff4444',
            warn: '#ffaa00',
            info: '#00ff00',
            debug: '#00aaff',
            network: '#ff00ff'
        };
        return colors[level] || '#ffffff';
    }
    
    clearLogs() {
        this.logs = [];
        this.updateLogDisplay();
    }
    
    interceptConsole() {
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        
        console.log = (...args) => {
            this.log(args.join(' '), 'info');
            originalLog.apply(console, args);
        };
        
        console.error = (...args) => {
            this.log(args.join(' '), 'error');
            originalError.apply(console, args);
        };
        
        console.warn = (...args) => {
            this.log(args.join(' '), 'warn');
            originalWarn.apply(console, args);
        };
    }
    
    interceptFetch() {
        const originalFetch = window.fetch;
        
        window.fetch = async (...args) => {
            const [url, options] = args;
            const startTime = performance.now();
            
            this.log(`🌐 Fetch: ${url}`, 'network', { method: options?.method || 'GET' });
            
            try {
                const response = await originalFetch.apply(window, args);
                const endTime = performance.now();
                const duration = Math.round(endTime - startTime);
                
                this.log(`✅ Fetch completed: ${url} (${response.status}) ${duration}ms`, 'network');
                
                return response;
            } catch (error) {
                const endTime = performance.now();
                const duration = Math.round(endTime - startTime);
                
                this.log(`❌ Fetch failed: ${url} ${duration}ms`, 'error', error.message);
                throw error;
            }
        };
    }
    
    monitorPerformance() {
        // Monitor page load performance
        window.addEventListener('load', () => {
            setTimeout(() => {
                const perfData = performance.getEntriesByType('navigation')[0];
                if (perfData) {
                    this.log(`📊 Page load: ${Math.round(perfData.loadEventEnd - perfData.fetchStart)}ms`, 'info');
                }
            }, 100);
        });
        
        // Monitor long tasks
        if ('PerformanceObserver' in window) {
            try {
                const observer = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.duration > 50) {
                            this.log(`⚠️ Long task detected: ${Math.round(entry.duration)}ms`, 'warn');
                        }
                    }
                });
                observer.observe({ entryTypes: ['longtask'] });
            } catch (e) {
                // PerformanceObserver not supported
            }
        }
    }
    
    async sendToBackend(logEntry) {
        try {
            // Only send important logs to backend
            if (['error', 'network'].includes(logEntry.level)) {
                await fetch(`${this.apiEndpoint}/browser/debug-log`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(logEntry)
                }).catch(() => {
                    // Silently fail if backend not available
                });
            }
        } catch (e) {
            // Silently fail if backend not available
        }
    }
    
    // Public API methods
    testBrowserActions() {
        this.log('🧪 Testing browser actions...', 'info');
        
        // Test basic browser action API calls
        this.testNavigate();
        this.testScreenshot();
        this.testElementInteraction();
    }
    
    async testNavigate() {
        try {
            const response = await fetch(`${this.apiEndpoint}/browser/launch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ page_id: 'test', context_id: 'test' })
            });
            
            if (response.ok) {
                this.log('✅ Browser launch test passed', 'info');
            } else {
                this.log('❌ Browser launch test failed', 'error');
            }
        } catch (error) {
            this.log('❌ Browser launch test error', 'error', error.message);
        }
    }
    
    async testScreenshot() {
        try {
            const response = await fetch(`${this.apiEndpoint}/browser/screenshot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ page_id: 'test' })
            });
            
            if (response.ok) {
                this.log('✅ Screenshot test passed', 'info');
            } else {
                this.log('❌ Screenshot test failed', 'error');
            }
        } catch (error) {
            this.log('❌ Screenshot test error', 'error', error.message);
        }
    }
    
    async testElementInteraction() {
        try {
            const response = await fetch(`${this.apiEndpoint}/browser/status`);
            
            if (response.ok) {
                const data = await response.json();
                this.log('✅ Browser status check passed', 'info', data);
            } else {
                this.log('❌ Browser status check failed', 'error');
            }
        } catch (error) {
            this.log('❌ Browser status check error', 'error', error.message);
        }
    }
}

// Initialize global debugger instance
if (typeof window !== 'undefined') {
    window.browserDebugger = new RealTimeBrowserDebugger();
    
    // Expose testing methods globally
    window.testBrowserActions = () => window.browserDebugger.testBrowserActions();
}