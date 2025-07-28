#!/usr/bin/env python3
"""
Test script for progress tracking functionality
"""
import asyncio
import requests
import time
import sys
from pathlib import Path

def test_progress_endpoints():
    """Test the progress tracking endpoints"""
    base_url = "http://localhost:8000/api/v1"
    
    print("🧪 Testing Progress Tracking System")
    print("=" * 50)
    
    # 1. Test health check
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ Backend is running")
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Make sure it's running.")
        return False
    
    # 2. Check initial progress status
    print("\n📊 Checking initial progress status...")
    response = requests.get(f"{base_url}/progress")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Active tasks: {data['data']['active_count']}")
        print(f"✅ Total tasks: {data['data']['total_count']}")
    else:
        print(f"❌ Failed to get progress status: {response.status_code}")
    
    # 3. Start market data fetch
    print("\n🚀 Starting market data fetch...")
    response = requests.post(f"{base_url}/market-data/fetch")
    if response.status_code == 200:
        data = response.json()
        task_id = data.get('task_id')
        print(f"✅ Task started: {task_id}")
        
        # 4. Monitor progress
        print("\n📈 Monitoring progress...")
        for i in range(30):  # Monitor for up to 60 seconds
            try:
                response = requests.get(f"{base_url}/progress/{task_id}")
                if response.status_code == 200:
                    task_data = response.json()['data']
                    progress = task_data['progress'] * 100
                    status = task_data['status']
                    step = task_data['current_step']
                    
                    print(f"📊 {progress:.1f}% - {status} - {step}")
                    
                    if status in ['completed', 'error']:
                        print(f"🎯 Task {status}!")
                        if status == 'error':
                            print(f"❌ Error: {task_data.get('error', 'Unknown error')}")
                        break
                        
                else:
                    print(f"❌ Failed to get task progress: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error monitoring progress: {e}")
                
            time.sleep(2)
        
        # 5. Get final task updates
        print(f"\n📋 Getting task updates...")
        response = requests.get(f"{base_url}/progress/{task_id}/updates?limit=5")
        if response.status_code == 200:
            updates = response.json()['updates']
            print(f"✅ Got {len(updates)} recent updates")
            for update in updates[-3:]:  # Show last 3
                print(f"   • {update['step']} ({update['progress']*100:.0f}%)")
        
    else:
        print(f"❌ Failed to start market data fetch: {response.status_code}")
        return False
    
    print("\n🎉 Progress tracking test completed!")
    return True

if __name__ == "__main__":
    success = test_progress_endpoints()
    if success:
        print("\n💡 Progress tracking is working! Check the dashboard at:")
        print("   http://localhost:8000")
    else:
        print("\n💡 Make sure the backend is running:")
        print("   cd trading-assistant/backend")
        print("   python run_local.py") 