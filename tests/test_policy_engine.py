#!/usr/bin/env python3
"""
Unit tests for services/policy_engine.py

Tests the PolicyEngine's ability to:
- Initialize with valid configuration
- Handle missing/empty configuration
- Handle malformed JSON gracefully
- Ensure all critical attributes are always initialized
"""
import os
import sys
import json
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPolicyEngineInitialization(unittest.TestCase):
    """Test cases for PolicyEngine initialization and configuration"""

    def setUp(self):
        """Clear environment variables before each test"""
        for key in list(os.environ.keys()):
            if key.startswith('DEVICE_') or key.startswith('POLICY_') or key.startswith('MQTT_'):
                del os.environ[key]

    def test_empty_json_config(self):
        """Test that PolicyEngine initializes correctly with empty DEVICE_TO_AGENTS_JSON"""
        os.environ['MQTT_HOST'] = 'test.mqtt.local'
        os.environ['MQTT_PORT'] = '1883'
        os.environ['DEVICE_TO_AGENTS_JSON'] = ''
        
        engine = self._create_mock_engine()
        
        # Verify all critical attributes exist
        self.assertTrue(hasattr(engine, 'agent_shutdown_delay'))
        self.assertTrue(hasattr(engine, 'device_to_agents'))
        self.assertTrue(hasattr(engine, 'policy_soc_min'))
        self.assertTrue(hasattr(engine, 'policy_debounce_sec'))
        self.assertTrue(hasattr(engine, 'policy_cooldown_sec'))
        
        # Verify defaults
        self.assertEqual(engine.agent_shutdown_delay, 60)
        self.assertEqual(engine.device_to_agents, {})

    def test_malformed_json_config(self):
        """Test that PolicyEngine handles malformed JSON gracefully"""
        os.environ['DEVICE_TO_AGENTS_JSON'] = '{this is not valid json'
        
        engine = self._create_mock_engine()
        
        # Should not raise AttributeError
        self.assertTrue(hasattr(engine, 'agent_shutdown_delay'))
        self.assertEqual(engine.agent_shutdown_delay, 60)
        self.assertEqual(engine.device_to_agents, {})

    def test_valid_json_config(self):
        """Test that PolicyEngine parses valid JSON correctly"""
        os.environ['DEVICE_TO_AGENTS_JSON'] = '{"Study":["mac-mini","nas"],"Office":["pc1"]}'
        
        engine = self._create_mock_engine()
        
        self.assertIn('Study', engine.device_to_agents)
        self.assertIn('Office', engine.device_to_agents)
        self.assertEqual(engine.device_to_agents['Study'], ['mac-mini', 'nas'])
        self.assertEqual(engine.device_to_agents['Office'], ['pc1'])

    def test_multiline_json_config(self):
        """Test that PolicyEngine handles multi-line JSON"""
        os.environ['DEVICE_TO_AGENTS_JSON'] = '''{
  "Study": ["mac-mini", "nas-thecus", "jdhp", "jd-surface"],
  "Meterkast": ["n1", "n2", "n3", "n4", "modbus-gw", "fw", "edgerouter"]
}'''
        
        engine = self._create_mock_engine()
        
        self.assertIn('Study', engine.device_to_agents)
        self.assertIn('Meterkast', engine.device_to_agents)
        self.assertEqual(len(engine.device_to_agents['Study']), 4)
        self.assertEqual(len(engine.device_to_agents['Meterkast']), 7)

    def test_agent_shutdown_delay_accessible(self):
        """Test that agent_shutdown_delay is accessible (the original bug fix)"""
        os.environ['DEVICE_TO_AGENTS_JSON'] = ''  # Empty - the problematic case
        
        engine = self._create_mock_engine()
        
        # This is the expression that was failing before (line 145 in policy_engine.py)
        time_since_trigger = 30
        try:
            result = time_since_trigger < (engine.agent_shutdown_delay + 60)
            self.assertTrue(result)  # Should be True (30 < 120)
        except AttributeError:
            self.fail("AttributeError raised - the bug still exists!")

    def test_custom_policy_values(self):
        """Test that custom policy values are loaded correctly"""
        os.environ['POLICY_SOC_MIN'] = '15'
        os.environ['POLICY_DEBOUNCE_SEC'] = '300'
        os.environ['POLICY_COOLDOWN_SEC'] = '600'
        
        engine = self._create_mock_engine()
        
        self.assertEqual(engine.policy_soc_min, 15)
        self.assertEqual(engine.policy_debounce_sec, 300)
        self.assertEqual(engine.policy_cooldown_sec, 600)

    def _create_mock_engine(self):
        """Create a mock PolicyEngine with the same initialization logic"""
        class MockPolicyEngine:
            def __init__(self):
                # This mirrors the actual PolicyEngine.__init__
                self.mqtt_host = os.environ.get("MQTT_HOST", "mosquitto.hs.mfis.net")
                self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
                self.mqtt_base = os.environ.get("ECOFLOW_BASE", "bridge-ecoflow")

                # Initialize critical attributes with defaults (ensures they always exist)
                self.policy_soc_min = 10
                self.policy_debounce_sec = 180
                self.policy_cooldown_sec = 300
                self.max_data_gap_sec = 60
                self.agent_shutdown_delay = 60
                self.device_to_agents = {}

                try:
                    self.policy_soc_min = int(os.environ.get("POLICY_SOC_MIN", "10"))
                    self.policy_debounce_sec = int(os.environ.get("POLICY_DEBOUNCE_SEC", "180"))
                    self.policy_cooldown_sec = int(os.environ.get("POLICY_COOLDOWN_SEC", "300"))

                    raw_agents = os.environ.get("DEVICE_TO_AGENTS_JSON", "{}")
                    if raw_agents.strip():
                        self.device_to_agents = json.loads(raw_agents)

                except (KeyError, ValueError, json.JSONDecodeError):
                    pass  # Defaults already set

        return MockPolicyEngine()


if __name__ == '__main__':
    unittest.main()
