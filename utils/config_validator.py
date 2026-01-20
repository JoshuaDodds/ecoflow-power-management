"""
Configuration validation utilities for EcoFlow Power Management.

Validates required environment variables and provides helpful error messages.
"""
import os
import json
import sys


class ConfigValidator:
    """Validates configuration and provides helpful error messages"""
    
    REQUIRED_CREDENTIALS = [
        ("ECOFLOW_USERNAME", "Your EcoFlow account email"),
        ("ECOFLOW_PASSWORD", "Your EcoFlow account password"),
        ("ECOFLOW_ACCESS_KEY", "Developer API Access Key"),
        ("ECOFLOW_SECRET_KEY", "Developer API Secret Key"),
        ("ECOFLOW_DEVICE_LIST", "Comma-separated device serial numbers"),
    ]
    
    REQUIRED_MQTT = [
        ("MQTT_HOST", "Local MQTT broker hostname"),
    ]
    
    OPTIONAL_CONFIG = [
        ("MQTT_PORT", "1883", int),
        ("POLICY_SOC_MIN", "10", int),
        ("POLICY_DEBOUNCE_SEC", "180", int),
        ("POLICY_COOLDOWN_SEC", "300", int),
    ]
    
    @staticmethod
    def validate_all():
        """
        Validate all required configuration.
        Returns True if valid, exits with error message if invalid.
        """
        errors = []
        
        # Check required credentials
        for var_name, description in ConfigValidator.REQUIRED_CREDENTIALS:
            value = os.environ.get(var_name, "").strip()
            if not value:
                errors.append(
                    f"❌ {var_name} not found\n"
                    f"   → {description}\n"
                    f"   → Set this in your .env file"
                )
        
        # Check required MQTT config
        for var_name, description in ConfigValidator.REQUIRED_MQTT:
            value = os.environ.get(var_name, "").strip()
            if not value:
                errors.append(
                    f"❌ {var_name} not found\n"
                    f"   → {description}\n"
                    f"   → Set this in your .env file"
                )
        
        # Validate MQTT_PORT is a valid integer
        mqtt_port = os.environ.get("MQTT_PORT", "1883")
        try:
            int(mqtt_port)
        except ValueError:
            errors.append(
                f"❌ MQTT_PORT must be a valid integer\n"
                f"   → Current value: '{mqtt_port}'\n"
                f"   → Example: MQTT_PORT=1883"
            )
        
        # Validate DEVICE_TO_AGENTS_JSON if present
        device_json = os.environ.get("DEVICE_TO_AGENTS_JSON", "").strip()
        if device_json:
            try:
                json.loads(device_json)
            except json.JSONDecodeError as e:
                errors.append(
                    f"❌ DEVICE_TO_AGENTS_JSON contains invalid JSON\n"
                    f"   → Error: {e}\n"
                    f"   → Check your .env file for proper JSON formatting"
                )
        
        # If there are errors, print them and exit
        if errors:
            print("\n" + "="*70)
            print("⚠️  CONFIGURATION ERRORS DETECTED")
            print("="*70 + "\n")
            
            for error in errors:
                print(error)
                print()
            
            print("="*70)
            print("📖 For setup instructions, see:")
            print("   https://github.com/JoshuaDodds/ecoflow-power-management#setup")
            print("="*70 + "\n")
            
            sys.exit(1)
        
        return True
    
    @staticmethod
    def print_config_summary():
        """Print a summary of loaded configuration (without sensitive data)"""
        print("\n" + "="*70)
        print("📋 Configuration Summary")
        print("="*70)
        
        # Credentials (masked)
        username = os.environ.get("ECOFLOW_USERNAME", "")
        if username:
            masked_user = username[:3] + "***" + username.split("@")[-1] if "@" in username else "***"
            print(f"  EcoFlow User:    {masked_user}")
        
        access_key = os.environ.get("ECOFLOW_ACCESS_KEY", "")
        if access_key:
            print(f"  Access Key:      {access_key[:8]}***")
        
        # Devices
        devices = os.environ.get("ECOFLOW_DEVICE_LIST", "").split(",")
        device_count = len([d for d in devices if d.strip()])
        print(f"  Devices:         {device_count} configured")
        
        # MQTT
        mqtt_host = os.environ.get("MQTT_HOST", "localhost")
        mqtt_port = os.environ.get("MQTT_PORT", "1883")
        print(f"  MQTT Broker:     {mqtt_host}:{mqtt_port}")
        
        # Policy
        soc_min = os.environ.get("POLICY_SOC_MIN", "10")
        debounce = os.environ.get("POLICY_DEBOUNCE_SEC", "180")
        print(f"  Policy:          Shutdown at {soc_min}% (debounce: {debounce}s)")
        
        # Agent mapping
        device_json = os.environ.get("DEVICE_TO_AGENTS_JSON", "{}").strip()
        if device_json:
            try:
                mapping = json.loads(device_json)
                agent_count = sum(len(agents) for agents in mapping.values())
                print(f"  Agent Mapping:   {len(mapping)} devices → {agent_count} agents")
            except:
                pass
        
        print("="*70 + "\n")


if __name__ == "__main__":
    # For testing
    ConfigValidator.validate_all()
    ConfigValidator.print_config_summary()
