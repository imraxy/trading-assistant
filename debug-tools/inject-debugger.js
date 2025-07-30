/**
 * Debug Injector Script
 * Injects the real-time debugger into any web page
 */

(function() {
    'use strict';
    
    // Check if debugger is already loaded
    if (window.debugger && window.debugger.isConnected !== undefined) {
        console.log('🔧 Real-time debugger already loaded');
        return;
    }

    console.log('🚀 Injecting Real-time Browser Debugger...');

    // Create and inject the main debugger script
    const script = document.createElement('script');
    script.src = '/debug-tools/real-time-browser-debugger.js';
    script.onload = function() {
        console.log('✅ Real-time debugger injected successfully');
        
        // Add debug UI overlay
        createDebugOverlay();
        
        // Auto-connect to debug server
        setTimeout(() => {
            if (window.debugger && !window.debugger.isConnected) {
                console.log('🔄 Attempting to connect to debug server...');
            }
        }, 1000);
    };
    
    script.onerror = function() {
        console.error('❌ Failed to load real-time debugger');
        // Fallback to inline debugger
        loadInlineDebugger();
    };
    
    document.head.appendChild(script);

    function createDebugOverlay() {
        // Create floating debug panel
        const overlay = document.createElement('div');
        overlay.id = 'debug-overlay';
        overlay.innerHTML = `
            <div id="debug-panel" style="
                position: fixed;
                top: 10px;
                right: 10px;
                width: 300px;
                background: rgba(0, 0, 0, 0.9);
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-family: monospace;
                font-size: 12px;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease;
                max-height: 400px;
                overflow-y: auto;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="color: #4a9eff; font-weight: bold;">🤖 AI Debugger</span>
                    <div>
                        <button id="debug-minimize" style="background: #666; color: white; border: none; padding: 2px 6px; border-radius: 3px; cursor: pointer; margin-right: 5px;">−</button>
                        <button id="debug-close" style="background: #ff4444; color: white; border: none; padding: 2px 6px; border-radius: 3px; cursor: pointer;">×</button>
                    </div>
                </div>
                
                <div id="debug-status" style="margin-bottom: 10px;">
                    <div>Status: <span id="connection-status" style="color: #ff6b6b;">Connecting...</span></div>
                    <div>Errors: <span id="error-count">0</span></div>
                    <div>Network: <span id="network-count">0</span></div>
                </div>
                
                <div id="debug-controls" style="margin-bottom: 10px;">
                    <button onclick="window.exportDebugData()" style="background: #4a9eff; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; margin-right: 5px; font-size: 10px;">Export</button>
                    <button onclick="window.clearDebugData()" style="background: #666; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; margin-right: 5px; font-size: 10px;">Clear</button>
                    <button onclick="openDashboard()" style="background: #28a745; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 10px;">Dashboard</button>
                </div>
                
                <div id="debug-log" style="max-height: 200px; overflow-y: auto; background: rgba(255, 255, 255, 0.1); padding: 5px; border-radius: 3px; font-size: 10px;">
                    <div style="color: #4a9eff;">Debug log will appear here...</div>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // Add event listeners
        document.getElementById('debug-close').onclick = () => {
            overlay.remove();
        };
        
        document.getElementById('debug-minimize').onclick = () => {
            const panel = document.getElementById('debug-panel');
            const isMinimized = panel.style.height === '40px';
            
            if (isMinimized) {
                panel.style.height = 'auto';
                panel.style.overflow = 'visible';
                document.getElementById('debug-minimize').textContent = '−';
            } else {
                panel.style.height = '40px';
                panel.style.overflow = 'hidden';
                document.getElementById('debug-minimize').textContent = '+';
            }
        };
        
        // Update overlay with debug data
        setInterval(updateDebugOverlay, 1000);
    }

    function updateDebugOverlay() {
        if (!window.debugger) return;
        
        const data = window.debugger.getDebugData();
        const statusEl = document.getElementById('connection-status');
        const errorCountEl = document.getElementById('error-count');
        const networkCountEl = document.getElementById('network-count');
        const logEl = document.getElementById('debug-log');
        
        if (statusEl) {
            statusEl.textContent = window.debugger.isConnected ? 'Connected' : 'Disconnected';
            statusEl.style.color = window.debugger.isConnected ? '#28a745' : '#ff6b6b';
        }
        
        if (errorCountEl) {
            errorCountEl.textContent = data.errors.length;
        }
        
        if (networkCountEl) {
            networkCountEl.textContent = data.network.length;
        }
        
        // Update log with recent entries
        if (logEl && data.console.length > 0) {
            const recentLogs = data.console.slice(-5);
            logEl.innerHTML = recentLogs.map(log => 
                `<div style="margin-bottom: 2px; color: ${getLogColor(log.level)};">[${log.level}] ${log.message.substring(0, 50)}${log.message.length > 50 ? '...' : ''}</div>`
            ).join('');
        }
    }

    function getLogColor(level) {
        switch (level) {
            case 'error': return '#ff6b6b';
            case 'warn': return '#ffa500';
            case 'info': return '#4a9eff';
            default: return '#ffffff';
        }
    }

    function openDashboard() {
        window.open('http://localhost:8080/dashboard', '_blank');
    }

    function loadInlineDebugger() {
        console.log('📦 Loading inline debugger fallback...');
        
        // Simplified inline debugger
        window.debugger = {
            isConnected: false,
            debugData: { console: [], errors: [], network: [] },
            
            getDebugData() {
                return this.debugData;
            },
            
            exportDebugData() {
                const dataStr = JSON.stringify(this.debugData, null, 2);
                const dataBlob = new Blob([dataStr], { type: 'application/json' });
                const url = URL.createObjectURL(dataBlob);
                
                const link = document.createElement('a');
                link.href = url;
                link.download = `debug-data-${Date.now()}.json`;
                link.click();
                
                URL.revokeObjectURL(url);
            },
            
            clearDebugData() {
                this.debugData = { console: [], errors: [], network: [] };
                console.log('🧹 Debug data cleared');
            }
        };
        
        // Basic console monitoring
        const originalLog = console.log;
        const originalError = console.error;
        
        console.log = (...args) => {
            window.debugger.debugData.console.push({
                level: 'log',
                message: args.join(' '),
                timestamp: Date.now()
            });
            originalLog.apply(console, args);
        };
        
        console.error = (...args) => {
            const errorEntry = {
                level: 'error',
                message: args.join(' '),
                timestamp: Date.now()
            };
            window.debugger.debugData.console.push(errorEntry);
            window.debugger.debugData.errors.push(errorEntry);
            originalError.apply(console, args);
        };
        
        // Basic error monitoring
        window.addEventListener('error', (event) => {
            const errorData = {
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                timestamp: Date.now()
            };
            window.debugger.debugData.errors.push(errorData);
        });
        
        console.log('✅ Inline debugger loaded');
        createDebugOverlay();
    }

    // Global functions
    window.openDashboard = openDashboard;
    
    // Auto-inject CSS for better styling
    const style = document.createElement('style');
    style.textContent = `
        #debug-overlay * {
            box-sizing: border-box;
        }
        
        #debug-panel:hover {
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        }
        
        #debug-panel button:hover {
            opacity: 0.8;
        }
        
        #debug-log::-webkit-scrollbar {
            width: 4px;
        }
        
        #debug-log::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
        }
        
        #debug-log::-webkit-scrollbar-thumb {
            background: #4a9eff;
            border-radius: 2px;
        }
    `;
    document.head.appendChild(style);

})();