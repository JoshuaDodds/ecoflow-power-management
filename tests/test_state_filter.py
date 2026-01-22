#!/usr/bin/env python3
"""
Unit tests for BooleanStateFilter

Tests the state_filter module's ability to filter transient false readings
in binary state values like grid_connected.
"""
import sys
import os
import time
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.state_filter import BooleanStateFilter


class TestBooleanStateFilter(unittest.TestCase):
    """Test cases for BooleanStateFilter"""
    
    def test_initialization(self):
        """Test filter initialization"""
        filter = BooleanStateFilter("TestDevice", "test_state")
        
        # First reading should be accepted immediately
        result = filter.filter(True, time.time())
        self.assertTrue(result)
        self.assertEqual(filter.confirmed_state, True)
    
    def test_stable_state(self):
        """Test that stable state passes through unchanged"""
        filter = BooleanStateFilter("TestDevice", "test_state", required_confirmations=5)
        
        # Initialize with True
        t = time.time()
        filter.filter(True, t)
        
        # Multiple readings of same state should pass through
        for i in range(10):
            result = filter.filter(True, t + i)
            self.assertTrue(result)
    
    def test_transient_false_reading(self):
        """Test that transient false reading is rejected"""
        filter = BooleanStateFilter("TestDevice", "grid_connected", required_confirmations=5)
        
        # Initialize with True (grid connected)
        t = time.time()
        filter.filter(True, t)
        
        # Single False reading (transient glitch)
        result = filter.filter(False, t + 1)
        # Should return confirmed state (True), not the transient False
        self.assertTrue(result)
        
        # Back to True
        result = filter.filter(True, t + 2)
        self.assertTrue(result)
    
    def test_confirmed_state_change(self):
        """Test that confirmed state change is accepted"""
        filter = BooleanStateFilter("TestDevice", "grid_connected", required_confirmations=5)
        
        # Initialize with True
        t = time.time()
        filter.filter(True, t)
        
        # Send 5 consecutive False readings (should confirm after 5)
        for i in range(4):
            result = filter.filter(False, t + i + 1)
            # Should still return True (not yet confirmed)
            self.assertTrue(result, f"Reading {i+1} should still return True")
        
        # 5th reading should confirm the change
        result = filter.filter(False, t + 5)
        self.assertFalse(result, "5th reading should confirm change to False")
        
        # Verify confirmed state changed
        self.assertEqual(filter.confirmed_state, False)
    
    def test_rapid_oscillation(self):
        """Test that rapid oscillation is filtered"""
        filter = BooleanStateFilter("TestDevice", "grid_connected", required_confirmations=5)
        
        # Initialize with True
        t = time.time()
        filter.filter(True, t)
        
        # Rapid oscillation: True, False, True, False, True, False
        readings = [False, True, False, True, False, True]
        for i, reading in enumerate(readings):
            result = filter.filter(reading, t + i + 1)
            # Should always return True (confirmed state) since oscillation prevents confirmation
            self.assertTrue(result, f"Oscillating reading {i+1} should return confirmed state (True)")
    
    def test_real_world_scenario(self):
        """Test real-world scenario: grid lost with transient reconnect"""
        filter = BooleanStateFilter("TestDevice", "grid_connected", required_confirmations=5)
        
        # Initialize with True (grid connected)
        t = time.time()
        result = filter.filter(True, t)
        self.assertTrue(result)
        
        # Grid actually lost - 5 consecutive False readings
        for i in range(5):
            result = filter.filter(False, t + i + 1)
        
        # Should now be confirmed as False
        self.assertFalse(result)
        
        # Transient True reading (brief reconnect glitch)
        result = filter.filter(True, t + 6)
        # Should still return False (not confirmed)
        self.assertFalse(result)
        
        # Back to False
        result = filter.filter(False, t + 7)
        self.assertFalse(result)
    
    def test_time_gap_reset(self):
        """Test that large time gap resets confirmation window"""
        filter = BooleanStateFilter("TestDevice", "grid_connected", required_confirmations=5)
        
        # Initialize with True
        t = time.time()
        filter.filter(True, t)
        
        # Start state change (3 False readings)
        for i in range(3):
            filter.filter(False, t + i + 1)
        
        # Large time gap (6 minutes)
        t_after_gap = t + 360
        
        # Next reading should reset confirmation window
        result = filter.filter(False, t_after_gap)
        # Should still return True since confirmation was reset
        self.assertTrue(result)
        
        # Verify confirmation count was reset
        self.assertEqual(filter.confirmation_count, 1)
    
    def test_custom_confirmation_threshold(self):
        """Test custom confirmation threshold"""
        # Use 3 confirmations instead of default 5
        filter = BooleanStateFilter("TestDevice", "test_state", required_confirmations=3)
        
        # Initialize with True
        t = time.time()
        filter.filter(True, t)
        
        # Send 3 consecutive False readings
        for i in range(2):
            result = filter.filter(False, t + i + 1)
            self.assertTrue(result)  # Not yet confirmed
        
        # 3rd reading should confirm
        result = filter.filter(False, t + 3)
        self.assertFalse(result)  # Confirmed


if __name__ == '__main__':
    unittest.main()
