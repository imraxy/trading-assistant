/**
 * Test client for Chrome debugger
 * Verifies connectivity and basic functionality
 */

const WebSocket = require('ws');

class ChromeDebuggerClient {
    constructor(port = 8081) {
        this.port = port;
        this.ws = null;
        this.connected = false;
    }

    async connect() {
        return new Promise((resolve, reject) => {
            console.log(`🔗 Connecting to Chrome debugger on port ${this.port}...`);
            
            this.ws = new WebSocket(`ws://localhost:${this.port}`);
            
            this.ws.on('open', () => {
                console.log('✅ Connected to Chrome debugger');
                this.connected = true;
                resolve();
            });
            
            this.ws.on('message', (data) => {
                try {
                    const message = JSON.parse(data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            });
            
            this.ws.on('error', (error) => {
                console.error('❌ WebSocket error:', error);
                reject(error);
            });
            
            this.ws.on('close', () => {
                console.log('🔌 Disconnected from Chrome debugger');
                this.connected = false;
            });
        });
    }

    handleMessage(message) {
        console.log(`📨 Received: ${message.type}`);
        
        switch (message.type) {
            case 'welcome':
                console.log(`🎉 ${message.message}`);
                console.log(`🛠️  Capabilities: ${message.capabilities.join(', ')}`);
                this.testFunctionality();
                break;
            case 'console_message':
                console.log(`📝 Console [${message.data.level}]: ${message.data.text}`);
                break;
            case 'network_request':
                console.log(`🌐 Network Request: ${message.data.method} ${message.data.url}`);
                break;
            case 'network_response':
                console.log(`📡 Network Response: ${message.data.status} ${message.data.url}`);
                break;
            case 'javascript_error':
                console.log(`❌ JavaScript Error: ${message.data.message}`);
                break;
            case 'console_logs':
                console.log(`📋 Console logs (${message.data.length} entries)`);
                message.data.slice(-5).forEach(log => {
                    console.log(`  [${log.level}] ${log.text}`);
                });
                break;
            case 'network_logs':
                console.log(`🌐 Network logs (${message.data.length} entries)`);
                break;
        }
    }

    testFunctionality() {
        console.log('🧪 Testing Chrome debugger functionality...');
        
        // Test connecting to tab
        setTimeout(() => {
            this.send({
                type: 'connect_tab',
                url: 'http://localhost:8000'
            });
        }, 1000);
        
        // Test getting console logs
        setTimeout(() => {
            this.send({
                type: 'get_console_logs'
            });
        }, 3000);
        
        // Test script execution
        setTimeout(() => {
            this.send({
                type: 'execute_script',
                script: 'console.log("🤖 Test message from AI debugger client");'
            });
        }, 5000);
    }

    send(message) {
        if (this.connected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.error('❌ Not connected to Chrome debugger');
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Run test if called directly
if (require.main === module) {
    const client = new ChromeDebuggerClient();
    
    client.connect().then(() => {
        console.log('🚀 Chrome debugger test client ready');
        console.log('📊 Monitoring for debugging events...');
        
        // Keep alive for testing
        setTimeout(() => {
            console.log('⏰ Test completed, disconnecting...');
            client.disconnect();
            process.exit(0);
        }, 30000);
        
    }).catch(error => {
        console.error('❌ Failed to connect to Chrome debugger:', error);
        console.log('💡 Make sure the Chrome debugger is running first');
        process.exit(1);
    });
    
    // Graceful shutdown
    process.on('SIGINT', () => {
        console.log('\n🛑 Shutting down test client...');
        client.disconnect();
        process.exit(0);
    });
}

module.exports = ChromeDebuggerClient;