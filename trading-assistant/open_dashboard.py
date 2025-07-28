#!/usr/bin/env python3
"""
Quick launcher for the AI Trading Assistant Dashboard
"""
import webbrowser
import time
import sys
from pathlib import Path

def main():
    print("🚀 AI Trading Assistant - Dashboard Launcher")
    print("=" * 50)
    
    # Check if backend is running
    dashboard_url = "http://localhost:8000"
    print(f"📱 Opening dashboard: {dashboard_url}")
    print(f"📚 API docs: {dashboard_url}/docs")
    print("=" * 50)
    
    # Open dashboard in browser
    try:
        webbrowser.open(dashboard_url)
        print("✅ Dashboard opened in browser!")
        print("\n💡 Make sure your backend server is running:")
        print("   cd trading-assistant/backend")
        print("   python run_local.py")
        print("\n🔄 Dashboard features:")
        print("   • Live position monitoring")
        print("   • Market data collection")
        print("   • Real-time P&L tracking")
        print("   • Symbol analysis")
        print("\n⚡ The dashboard auto-refreshes every 30 seconds")
        print("\n🛑 Press Ctrl+C to exit")
        
        # Keep script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Dashboard launcher stopped")
            
    except Exception as e:
        print(f"❌ Error opening dashboard: {e}")
        print(f"💡 Manually open: {dashboard_url}")

if __name__ == "__main__":
    main() 