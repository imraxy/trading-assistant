/**
 * Manual Chrome DevTools Protocol implementation
 * Works with existing Chrome instances - no auto-launch needed
 */

const WebSocket = require('ws');
const http = require('http');

class ManualChromeDebugger {
    constructor(options = {}) {
        this.port = options.port || 9222;
        this.wsPort = options.wsPort || 8081;
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

    async start() {
        console.log('🚀 Starting Manual Chrome Debugger...');
        console.log('📋 Setup Instructions:');
        console.log('1. Close all Chrome instances');
        console.log(`2. Start Chrome with: google-chrome --remote-debugging-port=${this.port}`);
        console.log('   Or on Windows: chrome.exe --remote-debugging-port=9222');
        console.log('3. Navigate to your trading assistant: http://localhost:8000');
        console.log('4. This debugger will connect automatically\n');
        
        // Start WebSocket server for clients
        this.startWebSocketServer();
        
        // Try to connect to Chrome
        await this.waitAndConnect();
        
        return this;
    }

    async waitAndConnect(maxAttempts = 30) {
        console.log('🔍 Waiting for Chrome debugging interface...');
        
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                const version = await this.makeRequest(`http://localhost:${this.port}/json/version`);
                if (version) {
                    console.log('✅ Chrome debugging interface found');
                    console.log(`📊 Chrome Version: ${version.Browser || 'Unknown'}`);
                    await this.connectToTab();
                    return true;
                }
            } catch (error) {
                if (attempt === 1) {
                    console.log(`⏳ Attempt ${attempt}/${maxAttempts} - Chrome not ready yet...`);
                } else if (attempt % 5 === 0) {
                    console.log(`⏳ Attempt ${attempt}/${maxAttempts} - Still waiting for Chrome...`);
                }
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        }
        
        console.log('❌ Chrome debugging interface not available after 60 seconds');
        console.log('💡 Please make sure Chrome is running with --remote-debugging-port=9222');
        return false;
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
            request.setTimeout(3000, () => {
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
                message: 'Connected to Manual Chrome Debugger',
                capabilities: ['console', 'network', 'performance', 'runtime'],
                status: this.isConnected ? 'connected' : 'waiting_for_chrome'
            }));
        });
        
        console.log(`🔌 WebSocket server running on port ${this.wsPort}`);
    }

    async handleClientMessage(data, ws) {
        switch (data.type) {
            case 'connect_tab':
                await this.connectToTab(data.url);
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
            case 'get_status':
                ws.send(JSON.stringify({
                    type: 'status',
                    connected: this.isConnected,
                    chrome_port: this.port,
                    websocket_port: this.wsPort
                }));
                break;
        }
    }

    async connectToTab(targetUrl = 'localhost:8000') {
        try {
            // Get list of tabs
            const tabs = await this.makeRequest(`http://localhost:${this.port}/json`);
            
            if (!Array.isArray(tabs)) {
                console.log('❌ No tabs found or invalid response');
                return;
            }
            
            // Find tab with target URL or any localhost tab
            let targetTab = tabs.find(tab => 
                tab.url.includes(targetUrl) || 
                tab.url.includes('localhost:8000') ||
                tab.url.includes('127.0.0.1:8000')
            );
            
            if (!targetTab && tabs.length > 0) {
                // Use the first available tab
                targetTab = tabs[0];
                console.log(`📱 Using tab: ${targetTab.title || targetTab.url}`);
            }
            
            if (targetTab && targetTab.webSocketDebuggerUrl) {
                await this.connectToTabWebSocket(targetTab.webSocketDebuggerUrl);
            } else {
                console.log('❌ No suitable tab found');
                console.log('💡 Please navigate to http://localhost:8000 in Chrome');
            }
            
        } catch (error) {
            console.error('Error connecting to tab:', error);
        }
    }

    async connectToTabWebSocket(wsUrl) {
        if (this.debuggerWs) {
            this.debuggerWs.close();
        }
        
        console.log('🔗 Connecting to Chrome tab...');
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
            
            // Notify clients
            this.broadcastToClients('chrome_connected', { status: 'connected' });
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
            this.broadcastToClients('chrome_disconnected', { status: 'disconnected' });
        });
        
        this.debuggerWs.on('error', (error) => {
            console.error('❌ Chrome WebSocket error:', error);
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
                
                // Create debug overlay if it doesn't exist
                if (!document.getElementById('ai-debug-overlay')) {
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
                }
                
                console.log('✅ AI Debugging overlay ready');
            })();
        `;
        
        this.sendCommand('Runtime.evaluate', {
            expression: script,
            includeCommandLineAPI: true
        });
    }

    executeScript(script) {
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
        
        console.log('🔌 Manual Chrome debugger closed');
    }
}

module.exports = ManualChromeDebugger;

// CLI usage
if (require.main === module) {
    const chromeDebugger = new ManualChromeDebugger();
    
    chromeDebugger.start().then(() => {
        console.log('🚀 Manual Chrome debugger ready');
        console.log('📊 WebSocket server: ws://localhost:8081');
        console.log('🌐 Chrome debugging: http://localhost:9222');
        console.log('📱 Connect to your trading assistant and start debugging!\n');
        
    }).catch(error => {
        console.error('❌ Failed to start Chrome debugger:', error);
    });
    
    // Graceful shutdown
    process.on('SIGINT', async () => {
        console.log('\n🛑 Shutting down Chrome debugger...');
        await chromeDebugger.close();
        process.exit(0);
    });
}