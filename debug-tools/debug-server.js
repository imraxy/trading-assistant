/**
 * Real-time Debug Server
 * WebSocket server to receive and process browser debugging data
 */

const WebSocket = require('ws');
const http = require('http');
const fs = require('fs');
const path = require('path');

class DebugServer {
    constructor(port = 8080) {
        this.port = port;
        this.clients = new Set();
        this.debugData = {
            sessions: new Map(),
            aggregated: {
                errors: [],
                performance: [],
                network: [],
                console: [],
                interactions: []
            }
        };
        this.aiAnalysisQueue = [];
        this.init();
    }

    init() {
        // Create HTTP server for serving debug interface
        this.httpServer = http.createServer((req, res) => {
            this.handleHttpRequest(req, res);
        });

        // Create WebSocket server
        this.wss = new WebSocket.Server({ 
            server: this.httpServer,
            path: '/debug'
        });

        this.wss.on('connection', (ws, req) => {
            console.log(`🔗 New debug client connected from ${req.socket.remoteAddress}`);
            this.clients.add(ws);

            ws.on('message', (data) => {
                try {
                    const debugMessage = JSON.parse(data.toString());
                    this.processDebugMessage(debugMessage, ws);
                } catch (error) {
                    console.error('❌ Error processing debug message:', error);
                }
            });

            ws.on('close', () => {
                console.log('🔌 Debug client disconnected');
                this.clients.delete(ws);
            });

            ws.on('error', (error) => {
                console.error('❌ WebSocket error:', error);
                this.clients.delete(ws);
            });

            // Send welcome message
            ws.send(JSON.stringify({
                type: 'welcome',
                message: 'Connected to AI Debug Server',
                timestamp: Date.now()
            }));
        });

        this.httpServer.listen(this.port, () => {
            console.log(`🚀 Debug Server running on http://localhost:${this.port}`);
            console.log(`📊 Debug Dashboard: http://localhost:${this.port}/dashboard`);
            console.log(`🔌 WebSocket endpoint: ws://localhost:${this.port}/debug`);
        });

        // Start AI analysis processor
        this.startAIAnalysisProcessor();
    }

    handleHttpRequest(req, res) {
        const url = req.url;

        if (url === '/dashboard') {
            this.serveDashboard(res);
        } else if (url === '/api/debug-data') {
            this.serveDebugData(res);
        } else if (url === '/api/analysis') {
            this.serveAIAnalysis(res);
        } else if (url.startsWith('/static/')) {
            this.serveStaticFile(req, res);
        } else {
            res.writeHead(404);
            res.end('Not Found');
        }
    }

    serveDashboard(res) {
        const dashboardHTML = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Debug Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #fff; }
        .header { background: #2d2d2d; padding: 1rem; border-bottom: 2px solid #4a9eff; }
        .header h1 { color: #4a9eff; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1rem; height: calc(100vh - 80px); }
        .panel { background: #2d2d2d; border-radius: 8px; padding: 1rem; overflow-y: auto; }
        .panel h2 { color: #4a9eff; margin-bottom: 1rem; border-bottom: 1px solid #444; padding-bottom: 0.5rem; }
        .log-entry { margin-bottom: 0.5rem; padding: 0.5rem; border-radius: 4px; font-size: 0.9rem; }
        .log-error { background: rgba(255, 99, 99, 0.1); border-left: 3px solid #ff6363; }
        .log-warn { background: rgba(255, 193, 7, 0.1); border-left: 3px solid #ffc107; }
        .log-info { background: rgba(23, 162, 184, 0.1); border-left: 3px solid #17a2b8; }
        .log-network { background: rgba(40, 167, 69, 0.1); border-left: 3px solid #28a745; }
        .timestamp { color: #888; font-size: 0.8rem; }
        .metric { display: flex; justify-content: space-between; margin-bottom: 0.5rem; padding: 0.5rem; background: #3a3a3a; border-radius: 4px; }
        .metric-value { color: #4a9eff; font-weight: bold; }
        .status { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; }
        .status-connected { background: #28a745; }
        .status-disconnected { background: #dc3545; }
        .ai-suggestion { background: rgba(74, 158, 255, 0.1); border: 1px solid #4a9eff; border-radius: 4px; padding: 1rem; margin-bottom: 1rem; }
        .controls { margin-bottom: 1rem; }
        .btn { background: #4a9eff; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-right: 0.5rem; }
        .btn:hover { background: #357abd; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Real-time Debug Dashboard</h1>
        <span id="connectionStatus" class="status status-disconnected">Disconnected</span>
    </div>
    
    <div class="container">
        <div class="panel">
            <h2>📊 Live Metrics</h2>
            <div class="controls">
                <button class="btn" onclick="clearLogs()">Clear Logs</button>
                <button class="btn" onclick="exportData()">Export Data</button>
                <button class="btn" onclick="requestAIAnalysis()">AI Analysis</button>
            </div>
            <div id="metrics">
                <div class="metric">
                    <span>Connected Clients:</span>
                    <span class="metric-value" id="clientCount">0</span>
                </div>
                <div class="metric">
                    <span>Total Errors:</span>
                    <span class="metric-value" id="errorCount">0</span>
                </div>
                <div class="metric">
                    <span>Network Requests:</span>
                    <span class="metric-value" id="networkCount">0</span>
                </div>
                <div class="metric">
                    <span>Performance Score:</span>
                    <span class="metric-value" id="perfScore">-</span>
                </div>
            </div>
            
            <h3>🤖 AI Suggestions</h3>
            <div id="aiSuggestions"></div>
        </div>
        
        <div class="panel">
            <h2>📝 Live Debug Log</h2>
            <div id="debugLog"></div>
        </div>
    </div>

    <script>
        let ws;
        let debugData = { errors: [], network: [], console: [], performance: [] };
        
        function connect() {
            ws = new WebSocket('ws://localhost:8080/debug');
            
            ws.onopen = () => {
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').className = 'status status-connected';
                console.log('Connected to debug server');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleDebugMessage(data);
            };
            
            ws.onclose = () => {
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                document.getElementById('connectionStatus').className = 'status status-disconnected';
                setTimeout(connect, 3000); // Reconnect after 3 seconds
            };
        }
        
        function handleDebugMessage(data) {
            const logDiv = document.getElementById('debugLog');
            const timestamp = new Date(data.timestamp).toLocaleTimeString();
            
            let logClass = 'log-info';
            if (data.type === 'error') logClass = 'log-error';
            else if (data.type === 'network') logClass = 'log-network';
            else if (data.data && data.data.level === 'warn') logClass = 'log-warn';
            
            const logEntry = document.createElement('div');
            logEntry.className = \`log-entry \${logClass}\`;
            logEntry.innerHTML = \`
                <div><strong>[\${data.type.toUpperCase()}]</strong> \${formatLogData(data)}</div>
                <div class="timestamp">\${timestamp}</div>
            \`;
            
            logDiv.insertBefore(logEntry, logDiv.firstChild);
            
            // Keep only last 100 entries
            while (logDiv.children.length > 100) {
                logDiv.removeChild(logDiv.lastChild);
            }
            
            // Update metrics
            updateMetrics(data);
            
            // Store data for AI analysis
            if (!debugData[data.type]) debugData[data.type] = [];
            debugData[data.type].push(data);
        }
        
        function formatLogData(data) {
            switch (data.type) {
                case 'error':
                    return \`\${data.data.message} at \${data.data.filename}:\${data.data.lineno}\`;
                case 'network':
                    return \`\${data.data.method || 'GET'} \${data.data.url} - \${data.data.response?.status || 'pending'}\`;
                case 'console':
                    return \`[\${data.data.level}] \${data.data.message}\`;
                case 'performance':
                    return \`\${data.data.name}: \${data.data.duration?.toFixed(2)}ms\`;
                case 'interaction':
                    return \`\${data.data.type} on \${data.data.target}\`;
                default:
                    return JSON.stringify(data.data).substring(0, 100);
            }
        }
        
        function updateMetrics(data) {
            document.getElementById('clientCount').textContent = '1'; // Simplified
            
            const errorCount = debugData.errors?.length || 0;
            document.getElementById('errorCount').textContent = errorCount;
            
            const networkCount = debugData.network?.length || 0;
            document.getElementById('networkCount').textContent = networkCount;
            
            // Calculate simple performance score
            const perfData = debugData.performance || [];
            const avgDuration = perfData.length > 0 ? 
                perfData.reduce((sum, p) => sum + (p.data.duration || 0), 0) / perfData.length : 0;
            const perfScore = avgDuration > 0 ? Math.max(0, 100 - avgDuration).toFixed(0) : '-';
            document.getElementById('perfScore').textContent = perfScore;
        }
        
        function clearLogs() {
            document.getElementById('debugLog').innerHTML = '';
            debugData = { errors: [], network: [], console: [], performance: [] };
            updateMetrics({});
        }
        
        function exportData() {
            const dataStr = JSON.stringify(debugData, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            
            const link = document.createElement('a');
            link.href = url;
            link.download = \`debug-export-\${Date.now()}.json\`;
            link.click();
            
            URL.revokeObjectURL(url);
        }
        
        function requestAIAnalysis() {
            fetch('/api/analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(debugData)
            })
            .then(response => response.json())
            .then(analysis => {
                displayAISuggestions(analysis);
            })
            .catch(error => {
                console.error('AI Analysis failed:', error);
            });
        }
        
        function displayAISuggestions(analysis) {
            const suggestionsDiv = document.getElementById('aiSuggestions');
            suggestionsDiv.innerHTML = '';
            
            analysis.suggestions.forEach(suggestion => {
                const suggestionDiv = document.createElement('div');
                suggestionDiv.className = 'ai-suggestion';
                suggestionDiv.innerHTML = \`
                    <strong>\${suggestion.title}</strong>
                    <p>\${suggestion.description}</p>
                    <small>Priority: \${suggestion.priority}</small>
                \`;
                suggestionsDiv.appendChild(suggestionDiv);
            });
        }
        
        // Connect on page load
        connect();
    </script>
</body>
</html>`;

        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(dashboardHTML);
    }

    serveDebugData(res) {
        res.writeHead(200, { 
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        });
        res.end(JSON.stringify(this.debugData.aggregated));
    }

    serveAIAnalysis(res) {
        if (req.method === 'POST') {
            let body = '';
            req.on('data', chunk => body += chunk.toString());
            req.on('end', () => {
                try {
                    const debugData = JSON.parse(body);
                    const analysis = this.performAIAnalysis(debugData);
                    
                    res.writeHead(200, { 
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    });
                    res.end(JSON.stringify(analysis));
                } catch (error) {
                    res.writeHead(400);
                    res.end(JSON.stringify({ error: 'Invalid request' }));
                }
            });
        } else {
            res.writeHead(405);
            res.end('Method Not Allowed');
        }
    }

    processDebugMessage(message, ws) {
        const { type, data, timestamp, url } = message;
        
        console.log(`📊 [${type.toUpperCase()}] ${this.formatDebugMessage(type, data)}`);
        
        // Store in aggregated data
        if (!this.debugData.aggregated[type]) {
            this.debugData.aggregated[type] = [];
        }
        
        this.debugData.aggregated[type].push({
            data,
            timestamp,
            url
        });
        
        // Keep only last 1000 entries per type
        if (this.debugData.aggregated[type].length > 1000) {
            this.debugData.aggregated[type] = this.debugData.aggregated[type].slice(-1000);
        }
        
        // Add to AI analysis queue for critical issues
        if (this.shouldAnalyze(type, data)) {
            this.aiAnalysisQueue.push({ type, data, timestamp, url });
        }
        
        // Broadcast to all connected clients (dashboard)
        this.broadcast({
            type,
            data,
            timestamp,
            url
        });
    }

    formatDebugMessage(type, data) {
        switch (type) {
            case 'error':
                return `${data.message} at ${data.filename}:${data.lineno}`;
            case 'network':
                return `${data.method || 'GET'} ${data.url} - ${data.response?.status || 'pending'}`;
            case 'console':
                return `[${data.level}] ${data.message}`;
            case 'performance':
                return `${data.name}: ${data.duration?.toFixed(2)}ms`;
            case 'interaction':
                return `${data.type} on ${data.target}`;
            default:
                return JSON.stringify(data).substring(0, 100);
        }
    }

    shouldAnalyze(type, data) {
        // Analyze errors, slow network requests, and performance issues
        return type === 'error' || 
               (type === 'network' && data.response?.duration > 2000) ||
               (type === 'performance' && data.duration > 1000);
    }

    performAIAnalysis(debugData) {
        // Simple AI-like analysis based on patterns
        const suggestions = [];
        
        // Analyze errors
        if (debugData.errors && debugData.errors.length > 0) {
            const errorTypes = {};
            debugData.errors.forEach(error => {
                const key = error.data.message.split(' ')[0];
                errorTypes[key] = (errorTypes[key] || 0) + 1;
            });
            
            Object.entries(errorTypes).forEach(([error, count]) => {
                if (count > 3) {
                    suggestions.push({
                        title: `Recurring Error Pattern`,
                        description: `"${error}" error occurs ${count} times. Consider implementing error handling or fixing the root cause.`,
                        priority: 'high',
                        type: 'error'
                    });
                }
            });
        }
        
        // Analyze network performance
        if (debugData.network && debugData.network.length > 0) {
            const slowRequests = debugData.network.filter(req => 
                req.data.response && req.data.response.duration > 2000
            );
            
            if (slowRequests.length > 0) {
                suggestions.push({
                    title: `Slow Network Requests`,
                    description: `${slowRequests.length} requests taking >2s. Consider caching, optimization, or loading states.`,
                    priority: 'medium',
                    type: 'performance'
                });
            }
        }
        
        // Analyze console logs
        if (debugData.console && debugData.console.length > 0) {
            const warnings = debugData.console.filter(log => log.data.level === 'warn');
            if (warnings.length > 5) {
                suggestions.push({
                    title: `Excessive Console Warnings`,
                    description: `${warnings.length} warnings detected. Review and clean up console output.`,
                    priority: 'low',
                    type: 'cleanup'
                });
            }
        }
        
        return {
            timestamp: Date.now(),
            suggestions,
            summary: {
                totalIssues: suggestions.length,
                criticalIssues: suggestions.filter(s => s.priority === 'high').length
            }
        };
    }

    broadcast(message) {
        this.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(JSON.stringify(message));
            }
        });
    }

    startAIAnalysisProcessor() {
        setInterval(() => {
            if (this.aiAnalysisQueue.length > 0) {
                const issues = this.aiAnalysisQueue.splice(0, 10); // Process 10 at a time
                const analysis = this.performAIAnalysis({ 
                    errors: issues.filter(i => i.type === 'error'),
                    network: issues.filter(i => i.type === 'network'),
                    performance: issues.filter(i => i.type === 'performance')
                });
                
                if (analysis.suggestions.length > 0) {
                    console.log('🤖 AI Analysis Results:');
                    analysis.suggestions.forEach(suggestion => {
                        console.log(`  • [${suggestion.priority.toUpperCase()}] ${suggestion.title}: ${suggestion.description}`);
                    });
                    
                    // Broadcast AI suggestions to dashboard
                    this.broadcast({
                        type: 'ai-analysis',
                        data: analysis,
                        timestamp: Date.now()
                    });
                }
            }
        }, 10000); // Analyze every 10 seconds
    }

    getStats() {
        return {
            connectedClients: this.clients.size,
            totalMessages: Object.values(this.debugData.aggregated).reduce((sum, arr) => sum + arr.length, 0),
            queuedAnalysis: this.aiAnalysisQueue.length
        };
    }
}

// Start the debug server
const debugServer = new DebugServer(8080);

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down debug server...');
    debugServer.httpServer.close(() => {
        console.log('✅ Debug server stopped');
        process.exit(0);
    });
});

module.exports = DebugServer;