/**
 * Simple HTTP server to serve files for testing the debug setup
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const BASE_DIR = path.join(__dirname, '..');

// MIME types
const mimeTypes = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon'
};

function getMimeType(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return mimeTypes[ext] || 'text/plain';
}

const server = http.createServer((req, res) => {
    let filePath = path.join(BASE_DIR, req.url === '/' ? '/trading-assistant/frontend/index.html' : req.url);
    
    // Security check - prevent directory traversal
    if (!filePath.startsWith(BASE_DIR)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    
    // Handle CORS for debug server communication
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    
    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }
    
    fs.readFile(filePath, (err, data) => {
        if (err) {
            if (err.code === 'ENOENT') {
                res.writeHead(404);
                res.end('File not found');
            } else {
                res.writeHead(500);
                res.end('Server error');
            }
            return;
        }
        
        const mimeType = getMimeType(filePath);
        res.writeHead(200, { 'Content-Type': mimeType });
        res.end(data);
    });
});

server.listen(PORT, () => {
    console.log(`🌐 File server running at http://localhost:${PORT}`);
    console.log(`📊 Trading Assistant: http://localhost:${PORT}/`);
    console.log(`🐛 Debug Dashboard: http://localhost:8080/dashboard`);
});

module.exports = server;