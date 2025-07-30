#!/bin/bash

# Real-Time Browser-AI Debugging Startup Script

echo "🚀 Starting Real-Time Browser-AI Debugging Session"
echo "=================================================="

# Check if Chrome debugger is already running
if pgrep -f "manual-chrome-debugger.js" > /dev/null; then
    echo "✅ Chrome debugger already running"
else
    echo "🔧 Starting Chrome debugger..."
    node manual-chrome-debugger.js &
    sleep 3
fi

echo ""
echo "📋 Next Steps:"
echo "1. Start Chrome with debugging:"
echo "   google-chrome --remote-debugging-port=9222"
echo ""
echo "2. Navigate to your trading assistant:"
echo "   http://localhost:8000"
echo ""
echo "3. Monitor real-time debugging output in terminal"
echo ""
echo "🔗 Available Interfaces:"
echo "   📊 WebSocket: ws://localhost:8081"
echo "   🌐 Chrome DevTools: http://localhost:9222"
echo "   🤖 AI Debugger: Active and monitoring"
echo ""
echo "💡 Tip: Open Chrome DevTools (F12) to see additional debugging info"
echo ""