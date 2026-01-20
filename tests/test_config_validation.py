#!/usr/bin/env python3
"""
Unit tests for configuration validation.

Tests the config_validator module's ability to:
- Detect missing required environment variables
- Validate JSON formatting
- Provide helpful error messages
"""
import os
import sys
import unittest
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigValidation(unittest.TestCase):
    """Test cases for configuration validation"""

    def setUp(self):
        """Save original environment and clear test variables"""
        self.original_env = os.environ.copy()
        
        # Clear all EcoFlow-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('ECOFLOW_') or key.startswith('MQTT_') or \
               key.startswith('POLICY_') or key.startswith('DEVICE_'):
                del os.environ[key]

    def tearDown(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_valid_configuration(self):
        """Test that valid configuration passes validation"""
        # Set all required variables
        os.environ['ECOFLOW_USERNAME'] = 'test@example.com'
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1,DEVICE2'
        os.environ['MQTT_HOST'] = 'localhost'
        os.environ['MQTT_PORT'] = '1883'
        
        from utils.config_validator import ConfigValidator
        
        # Should not raise any exceptions
        result = ConfigValidator.validate_all()
        self.assertTrue(result)

    def test_missing_username(self):
        """Test that missing username is detected"""
        # Set all except username
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1'
        os.environ['MQTT_HOST'] = 'localhost'
        
        from utils.config_validator import ConfigValidator
        
        # Should exit with error
        with self.assertRaises(SystemExit) as cm:
            ConfigValidator.validate_all()
        
        self.assertEqual(cm.exception.code, 1)

    def test_invalid_mqtt_port(self):
        """Test that invalid MQTT port is detected"""
        # Set all required variables
        os.environ['ECOFLOW_USERNAME'] = 'test@example.com'
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1'
        os.environ['MQTT_HOST'] = 'localhost'
        os.environ['MQTT_PORT'] = 'not-a-number'
        
        from utils.config_validator import ConfigValidator
        
        # Should exit with error
        with self.assertRaises(SystemExit) as cm:
            ConfigValidator.validate_all()
        
        self.assertEqual(cm.exception.code, 1)

    def test_invalid_json(self):
        """Test that invalid JSON in DEVICE_TO_AGENTS_JSON is detected"""
        # Set all required variables
        os.environ['ECOFLOW_USERNAME'] = 'test@example.com'
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1'
        os.environ['MQTT_HOST'] = 'localhost'
        os.environ['DEVICE_TO_AGENTS_JSON'] = '{invalid json'
        
        from utils.config_validator import ConfigValidator
        
        # Should exit with error
        with self.assertRaises(SystemExit) as cm:
            ConfigValidator.validate_all()
        
        self.assertEqual(cm.exception.code, 1)

    def test_valid_json(self):
        """Test that valid JSON passes validation"""
        # Set all required variables
        os.environ['ECOFLOW_USERNAME'] = 'test@example.com'
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1'
        os.environ['MQTT_HOST'] = 'localhost'
        os.environ['DEVICE_TO_AGENTS_JSON'] = '{"Device1":["agent1","agent2"]}'
        
        from utils.config_validator import ConfigValidator
        
        # Should not raise any exceptions
        result = ConfigValidator.validate_all()
        self.assertTrue(result)

    def test_config_summary_no_crash(self):
        """Test that config summary doesn't crash with valid config"""
        # Set all required variables
        os.environ['ECOFLOW_USERNAME'] = 'test@example.com'
        os.environ['ECOFLOW_PASSWORD'] = 'testpass'
        os.environ['ECOFLOW_ACCESS_KEY'] = 'AK_test123'
        os.environ['ECOFLOW_SECRET_KEY'] = 'SK_test456'
        os.environ['ECOFLOW_DEVICE_LIST'] = 'DEVICE1,DEVICE2'
        os.environ['MQTT_HOST'] = 'localhost'
        os.environ['DEVICE_TO_AGENTS_JSON'] = '{"Device1":["agent1"]}'
        
        from utils.config_validator import ConfigValidator
        
        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output
        
        try:
            ConfigValidator.print_config_summary()
            output = captured_output.getvalue()
            
            # Verify some expected content
            self.assertIn('Configuration Summary', output)
            self.assertIn('MQTT Broker', output)
            self.assertIn('localhost', output)
        finally:
            sys.stdout = sys.__stdout__


if __name__ == '__main__':
    unittest.main()
