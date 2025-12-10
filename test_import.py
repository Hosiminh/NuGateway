#!/usr/bin/env python3
"""
Test script to check if ModbusReader is properly imported
"""

import sys
import os

print("=" * 60)
print("🔍 ModbusReader Import Test")
print("=" * 60)
print(f"Python: {sys.version}")
print(f"Current dir: {os.getcwd()}")
print("=" * 60)

# Try importing modbus_reader module
try:
    import modbus_reader
    print("✅ modbus_reader module imported successfully")
    print(f"   Module file: {modbus_reader.__file__}")
    
    # Check what's in the module
    print("\n📋 Available in modbus_reader module:")
    attrs = [attr for attr in dir(modbus_reader) if not attr.startswith('_')]
    for attr in attrs:
        obj = getattr(modbus_reader, attr)
        obj_type = type(obj).__name__
        print(f"   - {attr} ({obj_type})")
    
    # Try importing ModbusReader class
    print("\n🔍 Checking for ModbusReader class...")
    if hasattr(modbus_reader, 'ModbusReader'):
        from modbus_reader import ModbusReader
        print("✅ ModbusReader class found!")
        print(f"   Class: {ModbusReader}")
        
        # Check methods
        print("\n📋 ModbusReader methods:")
        methods = [m for m in dir(ModbusReader) if not m.startswith('_')]
        for method in methods[:10]:  # Show first 10
            print(f"   - {method}")
        if len(methods) > 10:
            print(f"   ... and {len(methods) - 10} more")
    else:
        print("❌ ModbusReader class NOT found in module")
        print("\n💡 Available classes:")
        for attr in attrs:
            obj = getattr(modbus_reader, attr)
            if isinstance(obj, type):
                print(f"   - {attr}")
    
except ImportError as e:
    print(f"❌ Failed to import modbus_reader: {e}")
    print("\n💡 Make sure modbus_reader.py is in the same directory")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
