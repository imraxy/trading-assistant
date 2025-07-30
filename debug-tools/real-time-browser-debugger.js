/**
 * Real-time Browser Debugger
 * Establishes connection between browser and AI system for live debugging
 */

class RealTimeBrowserDebugger {
    constructor() {
        this.isConnected = false;
        this.debugData = {
            dom: null,
            console: [],
            network: [],
            performance: {},
            errors: [],
            userInteractions: []
        };
        this.websocket = null;
        this.observers = new Map();
        this.init();
    }

    async init() {
        console.log('🔧 Initializing Real-time Browser Debugger...');
        
        // Set up DOM monitoring
        this.setupDOMObserver();
        
        // Set up console monitoring
        this.setupConsoleMonitoring();
        
        // Set up network monitoring
        this.setupNetworkMonitoring();
        
        // Set up performance monitoring
        this.setupPerformanceMonitoring();
        
        // Set up error monitoring
        this.setupErrorMonitoring();
        
        // Set up user interaction monitoring
        this.setupUserInteractionMonitoring();
        
        // Establish WebSocket connection for real-time data streaming
        this.setupWebSocketConnection();
        
        console.log('✅ Real-time Browser Debugger initialized successfully');
    }

    setupDOMObserver() {
        const observer = new MutationObserver((mutations) => {
            const changes = mutations.map(mutation => ({
                type: mutation.type,
                target: mutation.target.tagName,
                addedNodes: Array.from(mutation.addedNodes).map(node => node.tagName).filter(Boolean),
                removedNodes: Array.from(mutation.removedNodes).map(node => node.tagName).filter(Boolean),
                attributeName: mutation.attributeName,
                oldValue: mutation.oldValue,
                timestamp: Date.now()
            }));
            
            this.debugData.dom = {
                changes,
                currentHTML: document.documentElement.outerHTML.substring(0, 10000), // Limit size
                timestamp: Date.now()
            };
            
            this.sendDebugData('dom-change', this.debugData.dom);
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeOldValue: true,
            characterData: true
        });

        this.observers.set('dom', observer);
    }

    setupConsoleMonitoring() {
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        const originalInfo = console.info;

        console.log = (...args) => {
            this.captureConsoleOutput('log', args);
            originalLog.apply(console, args);
        };

        console.error = (...args) => {
            this.captureConsoleOutput('error', args);
            originalError.apply(console, args);
        };

        console.warn = (...args) => {
            this.captureConsoleOutput('warn', args);
            originalWarn.apply(console, args);
        };

        console.info = (...args) => {
            this.captureConsoleOutput('info', args);
            originalInfo.apply(console, args);
        };
    }

    captureConsoleOutput(level, args) {
        const logEntry = {
            level,
            message: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '),
            timestamp: Date.now(),
            stack: new Error().stack
        };

        this.debugData.console.push(logEntry);
        
        // Keep only last 100 console entries
        if (this.debugData.console.length > 100) {
            this.debugData.console = this.debugData.console.slice(-100);
        }

        this.sendDebugData('console', logEntry);
    }

    setupNetworkMonitoring() {
        // Override fetch
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const startTime = performance.now();
            const request = {
                url: args[0],
                options: args[1] || {},
                timestamp: Date.now(),
                startTime
            };

            try {
                const response = await originalFetch.apply(window, args);
                const endTime = performance.now();
                
                const networkEntry = {
                    ...request,
                    response: {
                        status: response.status,
                        statusText: response.statusText,
                        headers: Object.fromEntries(response.headers.entries()),
                        duration: endTime - startTime
                    },
                    success: true
                };

                this.debugData.network.push(networkEntry);
                this.sendDebugData('network', networkEntry);
                
                return response;
            } catch (error) {
                const endTime = performance.now();
                const networkEntry = {
                    ...request,
                    error: error.message,
                    duration: endTime - startTime,
                    success: false
                };

                this.debugData.network.push(networkEntry);
                this.sendDebugData('network', networkEntry);
                
                throw error;
            }
        };

        // Override XMLHttpRequest
        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSend = XMLHttpRequest.prototype.send;

        XMLHttpRequest.prototype.open = function(method, url, ...args) {
            this._debugInfo = {
                method,
                url,
                startTime: performance.now(),
                timestamp: Date.now()
            };
            return originalXHROpen.apply(this, [method, url, ...args]);
        };

        XMLHttpRequest.prototype.send = function(...args) {
            const xhr = this;
            const originalOnReadyStateChange = xhr.onreadystatechange;

            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    const endTime = performance.now();
                    const networkEntry = {
                        ...xhr._debugInfo,
                        response: {
                            status: xhr.status,
                            statusText: xhr.statusText,
                            responseText: xhr.responseText.substring(0, 1000), // Limit size
                            duration: endTime - xhr._debugInfo.startTime
                        },
                        success: xhr.status >= 200 && xhr.status < 300
                    };

                    window.debugger.debugData.network.push(networkEntry);
                    window.debugger.sendDebugData('network', networkEntry);
                }

                if (originalOnReadyStateChange) {
                    originalOnReadyStateChange.apply(xhr, arguments);
                }
            };

            return originalXHRSend.apply(this, args);
        };
    }

    setupPerformanceMonitoring() {
        // Monitor Core Web Vitals
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                const perfData = {
                    name: entry.name,
                    entryType: entry.entryType,
                    startTime: entry.startTime,
                    duration: entry.duration,
                    timestamp: Date.now()
                };

                this.debugData.performance[entry.name] = perfData;
                this.sendDebugData('performance', perfData);
            }
        });

        observer.observe({ entryTypes: ['navigation', 'paint', 'largest-contentful-paint', 'first-input', 'layout-shift'] });
        this.observers.set('performance', observer);

        // Monitor memory usage
        setInterval(() => {
            if (performance.memory) {
                const memoryData = {
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize,
                    jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
                    timestamp: Date.now()
                };

                this.debugData.performance.memory = memoryData;
                this.sendDebugData('performance', { type: 'memory', data: memoryData });
            }
        }, 5000);
    }

    setupErrorMonitoring() {
        window.addEventListener('error', (event) => {
            const errorData = {
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error ? event.error.stack : null,
                timestamp: Date.now()
            };

            this.debugData.errors.push(errorData);
            this.sendDebugData('error', errorData);
        });

        window.addEventListener('unhandledrejection', (event) => {
            const errorData = {
                type: 'unhandledrejection',
                reason: event.reason,
                promise: event.promise,
                timestamp: Date.now()
            };

            this.debugData.errors.push(errorData);
            this.sendDebugData('error', errorData);
        });
    }

    setupUserInteractionMonitoring() {
        const events = ['click', 'scroll', 'keydown', 'mouseover', 'focus', 'blur'];
        
        events.forEach(eventType => {
            document.addEventListener(eventType, (event) => {
                const interactionData = {
                    type: eventType,
                    target: event.target.tagName,
                    targetId: event.target.id,
                    targetClass: event.target.className,
                    timestamp: Date.now(),
                    coordinates: eventType === 'click' ? { x: event.clientX, y: event.clientY } : null
                };

                this.debugData.userInteractions.push(interactionData);
                
                // Keep only last 50 interactions
                if (this.debugData.userInteractions.length > 50) {
                    this.debugData.userInteractions = this.debugData.userInteractions.slice(-50);
                }

                this.sendDebugData('interaction', interactionData);
            });
        });
    }

    setupWebSocketConnection() {
        try {
            // Try to connect to local debug server
            this.websocket = new WebSocket('ws://localhost:8080/debug');
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                console.log('🔗 Connected to AI debugging server');
                this.sendDebugData('connection', { status: 'connected', timestamp: Date.now() });
            };

            this.websocket.onclose = () => {
                this.isConnected = false;
                console.log('🔌 Disconnected from AI debugging server');
                // Attempt to reconnect after 5 seconds
                setTimeout(() => this.setupWebSocketConnection(), 5000);
            };

            this.websocket.onerror = (error) => {
                console.log('❌ WebSocket connection failed, falling back to local storage');
                this.isConnected = false;
                this.setupLocalStorageFallback();
            };

        } catch (error) {
            console.log('❌ WebSocket not available, using local storage fallback');
            this.setupLocalStorageFallback();
        }
    }

    setupLocalStorageFallback() {
        // Store debug data in localStorage for manual retrieval
        this.sendDebugData = (type, data) => {
            const debugEntry = {
                type,
                data,
                timestamp: Date.now()
            };

            const existingData = JSON.parse(localStorage.getItem('ai-debug-data') || '[]');
            existingData.push(debugEntry);
            
            // Keep only last 1000 entries
            if (existingData.length > 1000) {
                existingData.splice(0, existingData.length - 1000);
            }

            localStorage.setItem('ai-debug-data', JSON.stringify(existingData));
            
            // Also log to console for immediate visibility
            console.log(`🐛 [${type}]`, data);
        };
    }

    sendDebugData(type, data) {
        if (this.isConnected && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type,
                data,
                timestamp: Date.now(),
                url: window.location.href
            }));
        }
    }

    // Public API methods
    getDebugData() {
        return this.debugData;
    }

    exportDebugData() {
        const dataStr = JSON.stringify(this.debugData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `debug-data-${Date.now()}.json`;
        link.click();
        
        URL.revokeObjectURL(url);
    }

    clearDebugData() {
        this.debugData = {
            dom: null,
            console: [],
            network: [],
            performance: {},
            errors: [],
            userInteractions: []
        };
        localStorage.removeItem('ai-debug-data');
        console.log('🧹 Debug data cleared');
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close();
        }
        
        this.observers.forEach(observer => observer.disconnect());
        this.observers.clear();
        
        console.log('🔌 Real-time debugger disconnected');
    }
}

// Initialize the debugger
window.debugger = new RealTimeBrowserDebugger();

// Expose global methods
window.getDebugData = () => window.debugger.getDebugData();
window.exportDebugData = () => window.debugger.exportDebugData();
window.clearDebugData = () => window.debugger.clearDebugData();

console.log('🚀 Real-time Browser Debugger loaded successfully!');
console.log('Available commands: getDebugData(), exportDebugData(), clearDebugData()');