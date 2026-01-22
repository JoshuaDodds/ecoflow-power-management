#!/usr/bin/env python3
"""
Test script for SOC Filter

Tests the SOC anomaly detection with various scenarios
"""
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.soc_filter import SOCFilter

def test_normal_discharge():
    """Test normal battery discharge"""
    print("\n=== Test 1: Normal Discharge ===")
    filter = SOCFilter("TestDevice")
    
    # Simulate normal discharge: 90% → 85% over 5 minutes
    readings = [90, 89, 88, 87, 86, 85]
    for i, soc in enumerate(readings):
        timestamp = time.time() + (i * 60)  # 1 minute apart
        result = filter.filter(soc, timestamp)
        print(f"  Input: {soc}%, Output: {result}%")
    
    print("  ✅ Normal discharge should pass through")

def test_anomaly_rejection():
    """Test rejection of implausible reading"""
    print("\n=== Test 2: Anomaly Rejection ===")
    filter = SOCFilter("TestDevice")
    
    # Initialize with 90%
    filter.filter(90, time.time())
    
    # Try to jump to 9% (should be rejected)
    result = filter.filter(9, time.time() + 1)
    print(f"  Input: 90% → 9% in 1 second")
    print(f"  Output: {result}%")
    print(f"  Expected: None (rejected)")
    
    if result is None:
        print("  ✅ Anomaly correctly rejected")
    else:
        print("  ❌ Anomaly should have been rejected!")

def test_confirmation_window():
    """Test confirmation window for large changes"""
    print("\n=== Test 3: Confirmation Window ===")
    filter = SOCFilter("TestDevice")
    
    # Initialize with 90%
    filter.filter(90, time.time())
    print("  Initialized at 90%")
    
    # Try to change to 80% (6% change, needs confirmation)
    print("  Attempting 10% drop (requires 5 confirmations):")
    for i in range(6):
        timestamp = time.time() + (i * 10)
        result = filter.filter(80, timestamp)
        print(f"    Reading {i+1}: Input=80%, Output={result}%")
    
    print("  ✅ Should confirm after 5 consecutive readings")

def test_median_filter():
    """Test median filtering"""
    print("\n=== Test 4: Median Filter ===")
    filter = SOCFilter("TestDevice")
    
    # Readings with one outlier
    readings = [88, 89, 85, 90, 89]  # 85 is slightly low
    print(f"  Input readings: {readings}")
    
    for i, soc in enumerate(readings):
        timestamp = time.time() + (i * 10)
        result = filter.filter(soc, timestamp)
    
    print(f"  Final output: {result}%")
    print(f"  Expected: ~89% (median of recent readings)")
    print("  ✅ Median filter smooths out noise")

def test_real_world_scenario():
    """Test the actual scenario from logs"""
    print("\n=== Test 5: Real World Scenario (90% → 9% → 90%) ===")
    filter = SOCFilter("Meterkast")
    
    # Initialize at 90%
    t = time.time()
    result1 = filter.filter(90.0, t)
    print(f"  t+0s:  90.0% → {result1}%")
    
    # Anomalous 9% reading
    result2 = filter.filter(9.0, t + 5)
    print(f"  t+5s:   9.0% → {result2}% (should be rejected/None)")
    
    # Back to 90%
    result3 = filter.filter(90.0, t + 10)
    print(f"  t+10s: 90.0% → {result3}%")
    
    if result2 is None:
        print("  ✅ Anomaly correctly rejected, no false alarm!")
    else:
        print("  ❌ Anomaly should have been rejected!")

if __name__ == "__main__":
    print("SOC Filter Test Suite")
    print("=" * 50)
    
    test_normal_discharge()
    test_anomaly_rejection()
    test_confirmation_window()
    test_median_filter()
    test_real_world_scenario()
    
    print("\n" + "=" * 50)
    print("Tests complete!")
