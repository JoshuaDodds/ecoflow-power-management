#!/usr/bin/env python3
"""
Test script for SOC Decoder BMS Validation

Tests the enhanced BMS validation logic that filters out invalid/ghost
battery modules to prevent implausible SOC readings.
"""

import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.lib.ecoflow_river3plus import EcoFlowDevice


class TestBMSValidation(unittest.TestCase):
    """Test cases for BMS validation logic"""
    
    def test_valid_module_with_temp(self):
        """Valid module: SOC=90, Temp=2500 should be accepted"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Create message with valid BMS module
        # Field 6 (SOC) = 90, Field 16 (Temp) = 2500 (represents 25.0°C after /100)
        payload = self._create_message(soc=90, temp=2500)
        
        result = device.update_from_protobuf(payload)
        
        self.assertTrue(result, "Valid BMS module should be accepted")
        self.assertEqual(device.soc, 90.0, "SOC should be set to 90%")
        self.assertAlmostEqual(device.temp_celsius, 25.0, places=1)
    
    def test_ghost_module_soc_zero_temp_zero(self):
        """Ghost module: SOC=0, Temp=0 should be rejected"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Initialize with valid data first
        device.update_from_protobuf(self._create_message(soc=90, temp=2500))
        initial_soc = device.soc
        
        # Send ghost module
        payload = self._create_message(soc=0, temp=0)
        device.update_from_protobuf(payload)
        
        # SOC should remain unchanged (ghost module rejected)
        self.assertEqual(device.soc, initial_soc, "Ghost module should not change SOC")
    
    def test_partial_module_soc_without_temp(self):
        """Partial module: SOC=16, Temp=None should be rejected (NEW VALIDATION)"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Initialize with valid data
        device.update_from_protobuf(self._create_message(soc=90, temp=2500))
        initial_soc = device.soc
        
        # Send partial module (SOC without temperature)
        payload = self._create_message(soc=16, temp=None)
        device.update_from_protobuf(payload)
        
        # SOC should remain unchanged (partial module rejected)
        self.assertEqual(device.soc, initial_soc, "Partial module without temp should be rejected")
    
    def test_out_of_range_high(self):
        """Out of range: SOC=150 should be rejected (NEW VALIDATION)"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Initialize with valid data
        device.update_from_protobuf(self._create_message(soc=90, temp=2500))
        initial_soc = device.soc
        
        # Send out-of-range SOC
        payload = self._create_message(soc=150, temp=2500)
        device.update_from_protobuf(payload)
        
        # SOC should remain unchanged
        self.assertEqual(device.soc, initial_soc, "SOC > 100 should be rejected")
    
    def test_out_of_range_negative(self):
        """Out of range: SOC=101 (just above valid) should be rejected (NEW VALIDATION)"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Initialize with valid data
        device.update_from_protobuf(self._create_message(soc=90, temp=2500))
        initial_soc = device.soc
        
        # Send out-of-range SOC (just above 100)
        payload = self._create_message(soc=101, temp=2500)
        device.update_from_protobuf(payload)
        
        # SOC should remain unchanged
        self.assertEqual(device.soc, initial_soc, "SOC=101 should be rejected")
    
    def test_multi_module_scenario(self):
        """Multi-module: Should handle multiple valid modules correctly"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Create payload with two valid battery modules
        # Module 1: SOC=90, Temp=2500 (25°C)
        # Module 2: SOC=89, Temp=2450 (24.5°C)
        msg1 = self._create_message_dict(soc=90, temp=2500)
        msg2 = self._create_message_dict(soc=89, temp=2450)
        
        payload = self._create_multi_message([msg1, msg2])
        
        result = device.update_from_protobuf(payload)
        
        self.assertTrue(result, "Multi-module message should be accepted")
        # SOC should be one of the valid modules (90 or 89)
        self.assertIn(device.soc, [89.0, 90.0], "SOC should be from valid modules")
        # Both modules should be tracked
        self.assertEqual(len(device.soc_modules), 2, "Both modules should be tracked")
        self.assertIn(90, device.soc_modules)
        self.assertIn(89, device.soc_modules)
    
    def test_multi_module_with_ghost(self):
        """Multi-module with ghost: Valid modules should be used, ghost ignored"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Module 1: Valid (90%, 25°C)
        # Module 2: Ghost (0%, 0°C)
        # Module 3: Invalid (16%, no temp)
        msg1 = self._create_message_dict(soc=90, temp=2500)
        msg2 = self._create_message_dict(soc=0, temp=0)      # Ghost
        msg3 = self._create_message_dict(soc=16, temp=None)  # Invalid
        
        payload = self._create_multi_message([msg1, msg2, msg3])
        
        result = device.update_from_protobuf(payload)
        
        self.assertTrue(result, "Should accept message with at least one valid module")
        self.assertEqual(device.soc, 90.0, "Should use valid module, ignore ghost/invalid")
        # Only valid module should be tracked
        self.assertEqual(len(device.soc_modules), 1, "Only valid module should be tracked")
        self.assertEqual(device.soc_modules[0], 90)
    
    def test_imposter_check_still_works(self):
        """Enum/Imposter check: 0 < Temp < 100 should still be rejected"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Initialize with valid data
        device.update_from_protobuf(self._create_message(soc=90, temp=2500))
        initial_soc = device.soc
        
        # Send imposter message (temp in range 0-100 indicates enum, not actual temp)
        payload = self._create_message(soc=50, temp=50)
        device.update_from_protobuf(payload)
        
        # SOC should remain unchanged
        self.assertEqual(device.soc, initial_soc, "Imposter message should be rejected")
    
    def test_edge_case_soc_boundaries(self):
        """Edge cases: SOC at boundaries (0%, 100%) with valid temp should work"""
        device = EcoFlowDevice("TEST_DEVICE")
        
        # Test SOC = 100%
        payload = self._create_message(soc=100, temp=2500)
        result = device.update_from_protobuf(payload)
        self.assertTrue(result)
        self.assertEqual(device.soc, 100.0, "SOC=100% should be valid")
        
        # Test SOC = 1% (not 0%, which is ghost check)
        payload = self._create_message(soc=1, temp=2500)
        result = device.update_from_protobuf(payload)
        self.assertTrue(result)
        self.assertEqual(device.soc, 1.0, "SOC=1% should be valid")
    
    # === Helper Methods ===
    
    def _create_message_dict(self, soc=None, temp=None, grid=None, power=None):
        """Create a message dictionary with the given field values"""
        msg = {}
        if soc is not None:
            msg[6] = soc
        if temp is not None:
            msg[16] = temp
        if grid is not None:
            msg[27] = grid
        if power is not None:
            msg[28] = power
        return msg
    
    def _create_message(self, soc=None, temp=None, grid=None, power=None):
        """Create a simple protobuf message with given values"""
        parts = []
        
        if soc is not None:
            parts.extend(self._encode_field(6, soc))
        if temp is not None:
            parts.extend(self._encode_field(16, temp))
        if grid is not None:
            parts.extend(self._encode_field(27, grid))
        if power is not None:
            parts.extend(self._encode_field(28, power))
        
        return bytes(parts)
    
    def _create_multi_message(self, message_dicts):
        """Create a protobuf payload with multiple nested messages"""
        parts = []
        
        for i, msg_dict in enumerate(message_dicts):
            # Create the inner message
            inner = []
            for field, value in msg_dict.items():
                inner.extend(self._encode_field(field, value))
            inner_bytes = bytes(inner)
            
            # Wrap in length-delimited field (use different field numbers for each)
            field_num = i + 1
            tag = (field_num << 3) | 2  # Wire type 2 = length-delimited
            parts.extend(self._encode_varint(tag))
            parts.extend(self._encode_varint(len(inner_bytes)))
            parts.extend(inner_bytes)
        
        return bytes(parts)
    
    def _encode_field(self, field_num, value):
        """Encode a field with varint value"""
        tag = (field_num << 3) | 0  # Wire type 0 = varint
        result = self._encode_varint(tag)
        result.extend(self._encode_varint(value if value >= 0 else 0))
        return result
    
    def _encode_varint(self, value):
        """Encode value as protobuf varint"""
        if value < 0:
            value = 0  # Treat negative as 0 for encoding
        
        result = []
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return result


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
