/**
 * Puppeteer Alternative for Node.js v16
 * Chrome DevTools Protocol implementation for real-time debugging
 */

const WebSocket = require('ws');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

class ChromeDebugger {
    constructor(options = {}) {
        this.port = options.port || 9222;
        this.wsPort = options.wsPort || 8081;
        this.chromeProcess = null;
        this.debuggerWs = null;
        this.clients = new Set();
        this.isConnected = false;
        this.debugData = {
            console: [],
            network: [],
            errors: [],
            performance: []
        };
    }

    async launch() {
        console.log('🚀 Starting Chrome with debugging enabled...');
        
        // Launch Chrome with remote debugging
        const chromeArgs = [
            `--remote-debugging-port=${this.port}`,
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--enable-automation',
            '--password-store=basic',
            '--use-mock-keychain'
        ];

        // Try different Chrome executable paths
        const chromePaths = [
            'google-chrome',
            'google-chrome-stable',
            'chromium',
            'chromium-browser',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        ];

        let chromePath = null;
        for (const path of chromePaths) {
            try {
                this.chromeProcess = spawn(path, chromeArgs, { 
                    detached: true,
                    stdio: 'ignore'
                });
                chromePath = path;
                break;
            } catch (error) {
                continue;
            }
        }

        if (!chromePath) {
            console.log('⚠️  Chrome not found, using existing browser instance');
            console.log(`Please manually start Chrome with: --remote-debugging-port=${this.port}`);
        } else {
            console.log(`✅ Chrome started with debugging on port ${this.port}`);
        }

        // Wait for Chrome to start
        await this.waitForChrome();
        
        // Start WebSocket server for clients
        this.startWebSocketServer();
        
        return this;
    }

    async waitForChrome(timeout = 10000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            try {
                const response = await this.makeRequest(`http://localhost:${this.port}/json/version`);
                if (response) {
                    console.log('✅ Chrome debugging interface ready');
                    return true;
                }
            } catch (error) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        
        throw new Error('Chrome debugging interface not available');
    }

    async makeRequest(url) {
        return new Promise((resolve, reject) => {
            const request = http.get(url, (response) => {
                let data = '';
                response.on('data', chunk => data += chunk);
                response.on('end', () => {
                    try {
                        resolve(JSON.parse(data));
                    } catch (error) {
                        resolve(data);
                    }
                });
            });
            
            request.on('error', reject);
            request.setTimeout(5000, () => {
                request.destroy();
                reject(new Error('Request timeout'));
            });
        });
    }

    startWebSocketServer() {
        const wss = new WebSocket.Server({ port: this.wsPort });
        
        wss.on('connection', (ws) => {
            console.log('🔗 Client connected to Chrome debugger');
            this.clients.add(ws);
            
            ws.on('message', async (message) => {
                try {
                    const data = JSON.parse(message);
                    await this.handleClientMessage(data, ws);
                } catch (error) {
                    console.error('Error handling client message:', error);
                }
            });
            
            ws.on('close', () => {
                console.log('🔌 Client disconnected from Chrome debugger');
                this.clients.delete(ws);
            });
            
            // Send welcome message
            ws.send(JSON.stringify({
                type: 'welcome',
                message: 'Connected to Chrome Debugger',
                capabilities: ['console', 'network', 'performance', 'runtime']
            }));
        });
        
        console.log(`🔌 Chrome debugger WebSocket server running on port ${this.wsPort}`);
    }

    async handleClientMessage(data, ws) {
        switch (data.type) {
            case 'connect_tab':
                await this.connectToTab(data.url || 'http://localhost:8000');
                break;
            case 'execute_script':
                await this.executeScript(data.script);
                break;
            case 'get_console_logs':
                ws.send(JSON.stringify({
                    type: 'console_logs',
                    data: this.debugData.console
                }));
                break;
            case 'get_network_logs':
                ws.send(JSON.stringify({
                    type: 'network_logs',
                    data: this.debugData.network
                }));
                break;
        }
    }

    async connectToTab(targetUrl) {
        try {
            // Get list of tabs
            const tabs = await this.makeRequest(`http://localhost:${this.port}/json`);
            
            // Find or create tab with target URL
            let targetTab = tabs.find(tab => tab.url.includes('localhost:8000'));
            
            if (!targetTab) {
                // Create new tab
                const newTab = await this.makeRequest(`http://localhost:${this.port}/json/new?${targetUrl}`);
                targetTab = newTab;
            }
            
            if (targetTab && targetTab.webSocketDebuggerUrl) {
                await this.connectToTabWebSocket(targetTab.webSocketDebuggerUrl);
            }
            
        } catch (error) {
            console.error('Error connecting to tab:', error);
        }
    }

    async connectToTabWebSocket(wsUrl) {
        if (this.debuggerWs) {
            this.debuggerWs.close();
        }
        
        this.debuggerWs = new WebSocket(wsUrl);
        
        this.debuggerWs.on('open', () => {
            console.log('✅ Connected to Chrome tab');
            this.isConnected = true;
            
            // Enable domains
            this.sendCommand('Runtime.enable');
            this.sendCommand('Console.enable');
            this.sendCommand('Network.enable');
            this.sendCommand('Performance.enable');
            
            // Inject debugging script
            this.injectDebuggingScript();
        });
        
        this.debuggerWs.on('message', (data) => {
            try {
                const message = JSON.parse(data);
                this.handleChromeMessage(message);
            } catch (error) {
                console.error('Error parsing Chrome message:', error);
            }
        });
        
        this.debuggerWs.on('close', () => {
            console.log('🔌 Disconnected from Chrome tab');
            this.isConnected = false;
        });
    }

    sendCommand(method, params = {}) {
        if (this.debuggerWs && this.debuggerWs.readyState === WebSocket.OPEN) {
            const command = {
                id: Date.now(),
                method,
                params
            };
            this.debuggerWs.send(JSON.stringify(command));
        }
    }

    handleChromeMessage(message) {
        if (message.method) {
            switch (message.method) {
                case 'Console.messageAdded':
                    this.handleConsoleMessage(message.params);
                    break;
                case 'Runtime.consoleAPICalled':
                    this.handleConsoleAPI(message.params);
                    break;
                case 'Network.requestWillBeSent':
                    this.handleNetworkRequest(message.params);
                    break;
                case 'Network.responseReceived':
                    this.handleNetworkResponse(message.params);
                    break;
                case 'Runtime.exceptionThrown':
                    this.handleException(message.params);
                    break;
            }
        }
    }

    handleConsoleMessage(params) {
        const logEntry = {
            level: params.level || 'log',
            text: params.text || '',
            timestamp: Date.now(),
            source: 'console'
        };
        
        this.debugData.console.push(logEntry);
        this.broadcastToClients('console_message', logEntry);
        
        console.log(`📝 [${logEntry.level.toUpperCase()}] ${logEntry.text}`);
    }

    handleConsoleAPI(params) {
        const logEntry = {
            level: params.type || 'log',
            text: params.args?.map(arg => arg.value || arg.description || '').join(' ') || '',
            timestamp: Date.now(),
            source: 'console_api'
        };
        
        this.debugData.console.push(logEntry);
        this.broadcastToClients('console_message', logEntry);
    }

    handleNetworkRequest(params) {
        const networkEntry = {
            requestId: params.requestId,
            url: params.request.url,
            method: params.request.method,
            timestamp: Date.now(),
            type: 'request'
        };
        
        this.debugData.network.push(networkEntry);
        this.broadcastToClients('network_request', networkEntry);
    }

    handleNetworkResponse(params) {
        const networkEntry = {
            requestId: params.requestId,
            url: params.response.url,
            status: params.response.status,
            statusText: params.response.statusText,
            timestamp: Date.now(),
            type: 'response'
        };
        
        this.debugData.network.push(networkEntry);
        this.broadcastToClients('network_response', networkEntry);
    }

    handleException(params) {
        const errorEntry = {
            message: params.exceptionDetails.text,
            source: params.exceptionDetails.url,
            line: params.exceptionDetails.lineNumber,
            column: params.exceptionDetails.columnNumber,
            timestamp: Date.now()
        };
        
        this.debugData.errors.push(errorEntry);
        this.broadcastToClients('javascript_error', errorEntry);
        
        console.log(`❌ JavaScript Error: ${errorEntry.message} at ${errorEntry.source}:${errorEntry.line}`);
    }

    injectDebuggingScript() {
        const script = `
            // Enhanced debugging script injection
            (function() {
                console.log('🔧 AI Debugging script injected successfully');
                
                // Override console methods to capture all logs
                const originalLog = console.log;
                const originalError = console.error;
                const originalWarn = console.warn;
                
                console.log = function(...args) {
                    originalLog.apply(console, args);
                    window.postMessage({
                        type: 'AI_DEBUG_CONSOLE',
                        level: 'log',
                        message: args.join(' '),
                        timestamp: Date.now()
                    }, '*');
                };
                
                console.error = function(...args) {
                    originalError.apply(console, args);
                    window.postMessage({
                        type: 'AI_DEBUG_CONSOLE',
                        level: 'error',
                        message: args.join(' '),
                        timestamp: Date.now()
                    }, '*');
                };
                
                console.warn = function(...args) {
                    originalWarn.apply(console, args);
                    window.postMessage({
                        type: 'AI_DEBUG_CONSOLE',
                        level: 'warn',
                        message: args.join(' '),
                        timestamp: Date.now()
                    }, '*');
                };
                
                // Monitor for errors
                window.addEventListener('error', function(event) {
                    window.postMessage({
                        type: 'AI_DEBUG_ERROR',
                        message: event.message,
                        filename: event.filename,
                        lineno: event.lineno,
                        colno: event.colno,
                        timestamp: Date.now()
                    }, '*');
                });
                
                // Monitor unhandled promise rejections
                window.addEventListener('unhandledrejection', function(event) {
                    window.postMessage({
                        type: 'AI_DEBUG_REJECTION',
                        reason: event.reason,
                        timestamp: Date.now()
                    }, '*');
                });
                
                // Create debug overlay
                const overlay = document.createElement('div');
                overlay.id = 'ai-debug-overlay';
                overlay.style.cssText = \`
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    width: 300px;
                    background: rgba(0, 0, 0, 0.9);
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                    font-family: monospace;
                    font-size: 12px;
                    z-index: 10000;
                    max-height: 200px;
                    overflow-y: auto;
                \`;
                overlay.innerHTML = '<div style="color: #4CAF50;">🤖 AI Debugger Active</div>';
                document.body.appendChild(overlay);
                
                console.log('✅ AI Debugging overlay created');
            })();
        `;
        
        this.sendCommand('Runtime.evaluate', {
            expression: script,
            includeCommandLineAPI: true
        });
    }

    broadcastToClients(type, data) {
        const message = JSON.stringify({ type, data, timestamp: Date.now() });
        this.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(message);
            }
        });
    }

    async close() {
        if (this.debuggerWs) {
            this.debuggerWs.close();
        }
        
        if (this.chromeProcess) {
            this.chromeProcess.kill();
        }
        
        console.log('🔌 Chrome debugger closed');
    }
}

module.exports = ChromeDebugger;

// CLI usage
if (require.main === module) {
    const debugger = new ChromeDebugger();
    
    debugger.launch().then(() => {
        console.log('🚀 Chrome debugger ready');
        console.log('📊 WebSocket server: ws://localhost:8081');
        console.log('🌐 Chrome debugging: http://localhost:9222');
        
        // Auto-connect to localhost:8000 after 3 seconds
        setTimeout(() => {
            debugger.connectToTab('http://localhost:8000');
        }, 3000);
        
    }).catch(error => {
        console.error('❌ Failed to start Chrome debugger:', error);
    });
    
    // Graceful shutdown
    process.on('SIGINT', async () => {
        console.log('\n🛑 Shutting down Chrome debugger...');
        await debugger.close();
        process.exit(0);
    });
}