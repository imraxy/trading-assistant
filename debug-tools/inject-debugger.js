/**
 * Inject Debugger Script
 * Automatically injects debugging capabilities into web pages
 */

(function() {
    'use strict';
    
    // Prevent multiple injections
    if (window.debuggerInjected) {
        return;
    }
    window.debuggerInjected = true;
    
    console.log('🔧 Debug tools injected');
    
    // Enhanced error handling
    window.addEventListener('error', function(event) {
        if (window.browserDebugger) {
            window.browserDebugger.log(
                `❌ JavaScript Error: ${event.message}`,
                'error',
                {
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    stack: event.error?.stack
                }
            );
        }
    });
    
    // Enhanced unhandled promise rejection handling
    window.addEventListener('unhandledrejection', function(event) {
        if (window.browserDebugger) {
            window.browserDebugger.log(
                `❌ Unhandled Promise Rejection: ${event.reason}`,
                'error',
                {
                    reason: event.reason,
                    stack: event.reason?.stack
                }
            );
        }
    });
    
    // Monitor DOM mutations for debugging
    if (window.MutationObserver) {
        const observer = new MutationObserver(function(mutations) {
            let significantChanges = 0;
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    significantChanges++;
                }
            });
            
            if (significantChanges > 10 && window.browserDebugger) {
                window.browserDebugger.log(
                    `🔄 Significant DOM changes detected: ${significantChanges} mutations`,
                    'debug'
                );
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Add visual debugging helpers
    function addVisualDebugging() {
        // Add debug styles
        const debugStyles = document.createElement('style');
        debugStyles.id = 'debug-styles';
        debugStyles.textContent = `
            .debug-highlight {
                outline: 2px solid #ff0000 !important;
                background-color: rgba(255, 0, 0, 0.1) !important;
            }
            .debug-info {
                position: absolute;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 2px 6px;
                font-size: 10px;
                font-family: monospace;
                border-radius: 2px;
                z-index: 9999;
                pointer-events: none;
            }
        `;
        document.head.appendChild(debugStyles);
        
        // Add element inspector on Alt+Click
        document.addEventListener('click', function(event) {
            if (event.altKey) {
                event.preventDefault();
                event.stopPropagation();
                
                const element = event.target;
                const rect = element.getBoundingClientRect();
                const info = {
                    tagName: element.tagName,
                    id: element.id,
                    className: element.className,
                    textContent: element.textContent?.substring(0, 50),
                    position: {
                        x: Math.round(rect.left),
                        y: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
                
                if (window.browserDebugger) {
                    window.browserDebugger.log(
                        `🎯 Element inspected: ${element.tagName}`,
                        'debug',
                        info
                    );
                }
                
                // Visual highlight
                element.classList.add('debug-highlight');
                setTimeout(() => {
                    element.classList.remove('debug-highlight');
                }, 2000);
            }
        });
    }
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addVisualDebugging);
    } else {
        addVisualDebugging();
    }
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Ctrl+Shift+I - Inspect mode toggle
        if (event.ctrlKey && event.shiftKey && event.key === 'I') {
            event.preventDefault();
            if (window.browserDebugger) {
                window.browserDebugger.log('🔍 Inspect mode activated - Alt+Click elements to inspect', 'info');
            }
        }
        
        // Ctrl+Shift+T - Run browser tests
        if (event.ctrlKey && event.shiftKey && event.key === 'T') {
            event.preventDefault();
            if (window.testBrowserActions) {
                window.testBrowserActions();
            }
        }
        
        // Ctrl+Shift+S - Take screenshot
        if (event.ctrlKey && event.shiftKey && event.key === 'S') {
            event.preventDefault();
            if (window.browserDebugger) {
                window.browserDebugger.log('📸 Taking screenshot...', 'info');
                fetch('http://localhost:8000/api/v1/browser/screenshot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ page_id: 'current' })
                }).then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        window.browserDebugger.log('✅ Screenshot saved', 'info', data.data);
                    } else {
                        window.browserDebugger.log('❌ Screenshot failed', 'error');
                    }
                }).catch(error => {
                    window.browserDebugger.log('❌ Screenshot error', 'error', error.message);
                });
            }
        }
    });
    
    // Monitor page visibility changes
    document.addEventListener('visibilitychange', function() {
        if (window.browserDebugger) {
            const state = document.hidden ? 'hidden' : 'visible';
            window.browserDebugger.log(`👁️ Page visibility changed: ${state}`, 'debug');
        }
    });
    
    // Monitor online/offline status
    window.addEventListener('online', function() {
        if (window.browserDebugger) {
            window.browserDebugger.log('🌐 Connection restored', 'info');
        }
    });
    
    window.addEventListener('offline', function() {
        if (window.browserDebugger) {
            window.browserDebugger.log('📡 Connection lost', 'warn');
        }
    });
    
    // Add helpful debugging functions to global scope
    window.debugUtils = {
        highlightElement: function(selector) {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.classList.add('debug-highlight');
                setTimeout(() => el.classList.remove('debug-highlight'), 3000);
            });
            return elements.length;
        },
        
        getElementInfo: function(selector) {
            const element = document.querySelector(selector);
            if (!element) return null;
            
            const rect = element.getBoundingClientRect();
            return {
                tagName: element.tagName,
                id: element.id,
                className: element.className,
                textContent: element.textContent?.substring(0, 100),
                attributes: Array.from(element.attributes).map(attr => ({
                    name: attr.name,
                    value: attr.value
                })),
                position: {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                },
                styles: window.getComputedStyle(element)
            };
        },
        
        testApiEndpoint: async function(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method,
                    headers: { 'Content-Type': 'application/json' }
                };
                
                if (data && method !== 'GET') {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(`http://localhost:8000/api/v1${endpoint}`, options);
                const result = await response.json();
                
                if (window.browserDebugger) {
                    window.browserDebugger.log(
                        `🧪 API Test: ${method} ${endpoint} - ${response.status}`,
                        response.ok ? 'info' : 'error',
                        result
                    );
                }
                
                return result;
            } catch (error) {
                if (window.browserDebugger) {
                    window.browserDebugger.log(
                        `❌ API Test Failed: ${method} ${endpoint}`,
                        'error',
                        error.message
                    );
                }
                throw error;
            }
        }
    };
    
    console.log('🔧 Debug injection complete. Available commands:');
    console.log('  - Ctrl+Shift+D: Toggle debugger panel');
    console.log('  - Ctrl+Shift+I: Activate inspect mode');
    console.log('  - Ctrl+Shift+T: Run browser tests');
    console.log('  - Ctrl+Shift+S: Take screenshot');
    console.log('  - Alt+Click: Inspect element');
    console.log('  - window.debugUtils: Utility functions');
    
})();