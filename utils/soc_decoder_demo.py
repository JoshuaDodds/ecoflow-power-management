#!/usr/bin/env python3
"""
SOC Decoding Fix - Demonstration Script

This script demonstrates the fix for implausible SOC readings caused by
invalid battery module data passing through validation.

BEFORE: Invalid modules (SOC without temperature) were accepted
AFTER:  Strict validation rejects modules missing temperature field
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.lib.ecoflow_river3plus import EcoFlowDevice

def demonstrate_fix():
    """Demonstrate the BMS validation fix"""
    
    print("=" * 80)
    print("SOC DECODING FIX DEMONSTRATION")
    print("=" * 80)
    
    device = EcoFlowDevice("DEMO_DEVICE")
    
    # Scenario: Device with extra battery module (like "Study")
    # The protobuf contains multiple nested messages:
    # - Main battery: SOC=90%, Temp=2500 (25°C)
    # - Ghost module: SOC=16%, Temp=None (disconnected slot)
    
    print("\n📦 Simulating multi-module protobuf message...")
    print("   Module 1: SOC=90%, Temp=25°C  ✓ Valid")
    print("   Module 2: SOC=16%, Temp=None  ✗ Ghost/Invalid")
    
    # Create test messages
    def create_message(soc, temp):
        parts = []
        # Field 6 (SOC)
        parts.extend([0x30, soc])
        # Field 16 (Temp) - only if provided
        if temp is not None:
            tag = (16 << 3) | 0
            parts.append(tag)
            # Encode varint
            val = temp
            while val > 0x7F:
                parts.append((val & 0x7F) | 0x80)
                val >>= 7
            parts.append(val & 0x7F)
        return bytes(parts)
    
    # Wrap in nested structure
    msg1 = create_message(90, 2500)  # Valid
    msg2 = create_message(16, None)   # Invalid - no temp
    
    # Create multi-message payload
    payload_parts = []
    # Message 1
    payload_parts.extend([0x0A, len(msg1)])  # Field 1, length-delimited
    payload_parts.extend(msg1)
    # Message 2
    payload_parts.extend([0x12, len(msg2)])  # Field 2, length-delimited
    payload_parts.extend(msg2)
    
    payload = bytes(payload_parts)
    
    print(f"\n🔍 Raw payload: {payload.hex()}")
    print(f"   Length: {len(payload)} bytes")
    
    # Process the message
    print("\n⚙️  Processing with ENHANCED BMS validation...")
    result = device.update_from_protobuf(payload)
    
    print(f"\n✅ Result:")
    print(f"   Valid data found: {result}")
    print(f"   Final SOC: {device.soc}%")
    print(f"   Temperature: {device.temp_celsius}°C")
    print(f"   Valid modules tracked: {device.soc_modules}")
    
    # Verify the fix
    print("\n" + "=" * 80)
    if device.soc == 90.0 and len(device.soc_modules) == 1:
        print("✅ FIX VERIFIED: Only valid module (90%) was accepted!")
        print("   Ghost module (16% without temp) was correctly rejected.")
        print("\n💡 This prevents implausible SOC jumps like 90% → 16%")
        return True
    else:
        print("❌ UNEXPECTED: Fix may not be working correctly")
        print(f"   Expected SOC=90%, got SOC={device.soc}%")
        print(f"   Expected 1 module, got {len(device.soc_modules)} modules")
        return False

def test_old_behavior_scenario():
    """Test a scenario that would have caused issues before the fix"""
    
    print("\n" + "=" * 80)
    print("REAL-WORLD SCENARIO TEST")
    print("=" * 80)
    
    device = EcoFlowDevice("STUDY")
    
    print("\n📊 Simulating the 'Study' device with extra battery module...")
    print("   (This device showed frequent implausible readings in logs)")
    
    # Simulate a sequence of messages
    test_cases = [
        (90, 2500, "Initial valid reading"),
        (89, 2480, "Normal discharge (valid)"),
        (16, None, "Ghost module data (SHOULD BE REJECTED)"),
        (88, 2460, "Continue normal discharge (valid)"),
        (24, None, "Another ghost reading (SHOULD BE REJECTED)"),
        (87, 2440, "Continue normal discharge (valid)"),
    ]
    
    print("\n🔄 Processing sequence of readings:\n")
    
    for soc, temp, description in test_cases:
        # Create simple message
        parts = [0x30, soc]  # Field 6
        if temp is not None:
            parts.extend([0x80, 0x01])  # Field 16 tag
            # Encode temp varint
            val = temp
            while val > 0x7F:
                parts.append((val & 0x7F) | 0x80)
                val >>= 7
            parts.append(val & 0x7F)
        
        payload = bytes(parts)
        prev_soc = device.soc
        device.update_from_protobuf(payload)
        
        status = "✓" if device.soc != prev_soc or soc == device.soc else "⊘"
        print(f"   {status} SOC={soc:3d}%, Temp={'N/A  ' if temp is None else f'{temp:4d}'} "
              f"-> Device SOC: {device.soc:5.1f}% | {description}")
    
    print("\n📈 Final state:")
    print(f"   SOC: {device.soc}%")
    print(f"   Temperature: {device.temp_celsius}°C")
    print(f"   Valid modules: {device.soc_modules}")
    
    # Verify smooth degradation (no jumps)
    expected_final = 87.0
    if device.soc == expected_final:
        print(f"\n✅ SUCCESS: Ghost readings were filtered out!")
        print(f"   SOC followed smooth path: 90% → 89% → 88% → 87%")
        print(f"   Anomalous values (16%, 24%) were correctly rejected")
        return True
    else:
        print(f"\n⚠️  Unexpected final SOC: {device.soc}% (expected {expected_final}%)")
        return False

if __name__ == "__main__":
    print("\n")
    success1 = demonstrate_fix()
    success2 = test_old_behavior_scenario()
    
    print("\n" + "=" * 80)
    if success1 and success2:
        print("🎉 ALL DEMONSTRATIONS PASSED!")
        print("\nThe enhanced BMS validation successfully filters out ghost/invalid")
        print("battery modules, preventing implausible SOC readings.")
    else:
        print("⚠️  Some demonstrations failed - please review results above")
    print("=" * 80 + "\n")
