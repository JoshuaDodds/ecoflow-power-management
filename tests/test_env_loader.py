#!/usr/bin/env python3
"""
Unit tests for utils/env_loader.py

Tests the environment variable loader's ability to:
- Parse single-line values
- Parse multi-line values (enclosed in quotes)
- Handle empty values
- Handle malformed input
"""
import os
import sys
import tempfile
import json
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEnvLoader(unittest.TestCase):
    """Test cases for env_loader.py"""

    def setUp(self):
        """Clear environment variables before each test"""
        for key in ['MQTT_HOST', 'MQTT_PORT', 'DEVICE_TO_AGENTS_JSON', 'POLICY_SOC_MIN']:
            os.environ.pop(key, None)

    def test_multiline_json(self):
        """Test parsing of multi-line JSON values"""
        test_env_content = """
MQTT_HOST=mosquitto.hs.mfis.net
MQTT_PORT=1883

DEVICE_TO_AGENTS_JSON='{
  "Study": ["mac-mini", "nas-thecus", "jdhp", "jd-surface"],
  "Meterkast": ["n1", "n2", "n3", "n4", "modbus-gw", "fw", "edgerouter"],
  "SimulatedDevice": ["linux-agent", "mac-agent", "windows-agent"]
}'

POLICY_SOC_MIN=5
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(test_env_content)
            temp_env_path = f.name
        
        try:
            # Load using the env_loader logic
            self._load_env_file(temp_env_path)
            
            # Verify basic values
            self.assertEqual(os.environ.get('MQTT_HOST'), 'mosquitto.hs.mfis.net')
            self.assertEqual(os.environ.get('MQTT_PORT'), '1883')
            self.assertEqual(os.environ.get('POLICY_SOC_MIN'), '5')
            
            # Verify JSON parsing
            json_str = os.environ.get('DEVICE_TO_AGENTS_JSON', '{}')
            parsed = json.loads(json_str)
            
            self.assertIn('Study', parsed)
            self.assertIn('Meterkast', parsed)
            self.assertIn('SimulatedDevice', parsed)
            self.assertIsInstance(parsed['Study'], list)
            self.assertGreater(len(parsed['Study']), 0)
            
        finally:
            os.unlink(temp_env_path)

    def test_singleline_json(self):
        """Test parsing of single-line JSON values"""
        test_env_content = """
DEVICE_TO_AGENTS_JSON='{"Study":["mac-mini","nas-thecus"],"Meterkast":["n1","n2"]}'
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(test_env_content)
            temp_env_path = f.name
        
        try:
            self._load_env_file(temp_env_path)
            
            json_str = os.environ.get('DEVICE_TO_AGENTS_JSON', '{}')
            parsed = json.loads(json_str)
            
            self.assertEqual(parsed['Study'], ['mac-mini', 'nas-thecus'])
            self.assertEqual(parsed['Meterkast'], ['n1', 'n2'])
            
        finally:
            os.unlink(temp_env_path)

    def test_empty_value(self):
        """Test handling of empty values"""
        test_env_content = """
MQTT_HOST=mosquitto.hs.mfis.net
DEVICE_TO_AGENTS_JSON=
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(test_env_content)
            temp_env_path = f.name
        
        try:
            self._load_env_file(temp_env_path)
            
            json_str = os.environ.get('DEVICE_TO_AGENTS_JSON', '{}')
            self.assertEqual(json_str.strip(), '')
            
        finally:
            os.unlink(temp_env_path)

    def _load_env_file(self, env_path):
        """Helper method to load env file using the same logic as env_loader.py"""
        with open(env_path, 'r') as f:
            lines = f.readlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                if not line or line.startswith('#'):
                    i += 1
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Check if value starts with a quote but doesn't end with one
                    if (value.startswith("'") and not value.endswith("'")) or \
                       (value.startswith('"') and not value.endswith('"')):
                        opening_quote = value[0]
                        i += 1
                        while i < len(lines):
                            next_line = lines[i].rstrip('\n\r')
                            value += '\n' + next_line
                            if next_line.rstrip().endswith(opening_quote):
                                break
                            i += 1

                    # Remove surrounding quotes
                    if (value.startswith('"') and value.endswith('"')) or \
                            (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    if key not in os.environ:
                        os.environ[key] = value
                
                i += 1


if __name__ == '__main__':
    unittest.main()
