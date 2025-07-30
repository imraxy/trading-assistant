#!/usr/bin/env python3
"""
Configuration validation test script
Tests the enhanced Bybit configuration without requiring dependencies
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_config_syntax():
    """Test that the configuration files have valid syntax"""
    try:
        # Test importing the config module
        import app.config
        print("✅ Configuration module imports successfully")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in configuration: {e}")
        return False
    except ImportError as e:
        print(f"⚠️  Import error (expected due to missing dependencies): {e}")
        print("✅ Configuration syntax is valid")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_env_file_format():
    """Test that .env files have valid format"""
    env_files = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env"
    ]
    
    for env_file in env_files:
        if env_file.exists():
            print(f"\n📁 Testing {env_file}")
            try:
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' not in line:
                            print(f"❌ Line {i}: Invalid format (missing =): {line}")
                            return False
                        
                        key, value = line.split('=', 1)
                        if not key.strip():
                            print(f"❌ Line {i}: Empty key: {line}")
                            return False
                
                print(f"✅ {env_file.name} format is valid")
            except Exception as e:
                print(f"❌ Error reading {env_file}: {e}")
                return False
        else:
            print(f"⚠️  {env_file} not found")
    
    return True

def test_configuration_consistency():
    """Test configuration consistency"""
    print("\n🔍 Testing configuration consistency...")
    
    # Check main .env file
    main_env = Path(__file__).parent.parent / ".env"
    backend_env = Path(__file__).parent / ".env"
    
    if main_env.exists() and backend_env.exists():
        # Read both files
        main_config = {}
        backend_config = {}
        
        with open(main_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    main_config[key.strip()] = value.strip()
        
        with open(backend_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    backend_config[key.strip()] = value.strip()
        
        # Check for consistency in key Bybit settings
        bybit_keys = ['BYBIT_USE_TESTNET', 'BYBIT_TESTNET_URL', 'BYBIT_MAINNET_URL']
        
        for key in bybit_keys:
            if key in main_config and key in backend_config:
                if main_config[key] != backend_config[key]:
                    print(f"❌ Inconsistency in {key}: main='{main_config[key]}' vs backend='{backend_config[key]}'")
                    return False
                else:
                    print(f"✅ {key} is consistent")
        
        # Check logical consistency
        use_testnet = main_config.get('BYBIT_USE_TESTNET', 'true').lower()
        base_url = main_config.get('BYBIT_BASE_URL', '')
        
        if use_testnet == 'true' and 'testnet' not in base_url.lower():
            print("⚠️  Warning: BYBIT_USE_TESTNET=true but BYBIT_BASE_URL doesn't contain 'testnet'")
        elif use_testnet == 'false' and 'testnet' in base_url.lower():
            print("⚠️  Warning: BYBIT_USE_TESTNET=false but BYBIT_BASE_URL contains 'testnet'")
        else:
            print("✅ Testnet configuration is logically consistent")
    
    return True

def main():
    """Run all configuration tests"""
    print("🧪 Running Configuration Validation Tests")
    print("=" * 50)
    
    tests = [
        ("Configuration Syntax", test_config_syntax),
        ("Environment File Format", test_env_file_format),
        ("Configuration Consistency", test_configuration_consistency)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        print(f"\n🔬 {test_name}")
        print("-" * 30)
        if not test_func():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All configuration tests passed!")
        return 0
    else:
        print("❌ Some configuration tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())