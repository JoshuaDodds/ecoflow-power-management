#!/usr/bin/env python3
"""
EcoFlow Power Management - Linux Agent
Listens for shutdown commands via MQTT and executes system shutdown.
"""

import os
import sys
import json
import subprocess
import paho.mqtt.client as mqtt
from datetime import datetime
from pathlib import Path

# ========== LOAD .ENV FILE ==========
# Load environment variables from .env file if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    print(f"[{datetime.now()}] Loading configuration from .env file...")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments, empty lines, and PowerShell-style variables
            if line and not line.startswith('#') and not line.startswith('$') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

# ========== CONFIGURATION ==========
MQTT_BROKER = os.getenv("MQTT_BROKER") or os.getenv("MQTT_HOST", "mosquitto.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
AGENT_ID = os.getenv("AGENT_ID", "linux-agent")
MQTT_TOPIC = f"power-manager/{AGENT_ID}/cmd"

# Pre-shutdown commands (executed in order before shutdown)
PRE_SHUTDOWN_CMDS = []
for i in range(1, 10):  # Support up to 9 pre-shutdown commands
    cmd = os.getenv(f"PRE_SHUTDOWN_CMD_{i}")
    if cmd:
        PRE_SHUTDOWN_CMDS.append(cmd)

# Shutdown and abort commands (customizable)
SHUTDOWN_CMD = os.getenv("SHUTDOWN_CMD", "sudo shutdown -h +1")
ABORT_CMD = os.getenv("ABORT_CMD", "sudo shutdown -c")

# ========== MQTT CALLBACKS ==========
def on_connect(client, userdata, flags, rc):
    """Called when connected to MQTT broker."""
    if rc == 0:
        print(f"[{datetime.now()}] Connected to MQTT broker at {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        print(f"[{datetime.now()}] Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"[{datetime.now()}] Connection failed with code {rc}")
        sys.exit(1)

def on_message(client, userdata, msg):
    """Called when a message is received on subscribed topic."""
    try:
        payload = msg.payload.decode('utf-8')
        print(f"[{datetime.now()}] Received message: {payload}")
        
        # Parse JSON command
        command = json.loads(payload)
        action = command.get("action")
        
        if action == "shutdown":
            print(f"[{datetime.now()}] SHUTDOWN command received!")
            
            # Execute pre-shutdown commands
            if PRE_SHUTDOWN_CMDS:
                print(f"[{datetime.now()}] Executing {len(PRE_SHUTDOWN_CMDS)} pre-shutdown command(s)...")
                for idx, cmd in enumerate(PRE_SHUTDOWN_CMDS, 1):
                    print(f"[{datetime.now()}] Pre-shutdown {idx}/{len(PRE_SHUTDOWN_CMDS)}: {cmd}")
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            print(f"[{datetime.now()}] ✓ Command succeeded")
                            if result.stdout:
                                print(f"[{datetime.now()}] Output: {result.stdout.strip()}")
                        else:
                            print(f"[{datetime.now()}] ✗ Command failed with code {result.returncode}")
                            if result.stderr:
                                print(f"[{datetime.now()}] Error: {result.stderr.strip()}")
                    except subprocess.TimeoutExpired:
                        print(f"[{datetime.now()}] ✗ Command timed out after 30 seconds")
                    except Exception as e:
                        print(f"[{datetime.now()}] ✗ Command failed: {e}")
            
            # Execute shutdown command
            print(f"[{datetime.now()}] Initiating system shutdown...")
            print(f"[{datetime.now()}] Command: {SHUTDOWN_CMD}")
            subprocess.run(SHUTDOWN_CMD, shell=True)
            
        elif action == "abort":
            print(f"[{datetime.now()}] ABORT command received!")
            print(f"[{datetime.now()}] Canceling pending shutdown...")
            print(f"[{datetime.now()}] Command: {ABORT_CMD}")
            
            # Cancel any pending shutdown
            subprocess.run(ABORT_CMD, shell=True)
            
        else:
            print(f"[{datetime.now()}] Unknown action: {action}")
            
    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] Failed to parse JSON: {e}")
    except Exception as e:
        print(f"[{datetime.now()}] Error processing message: {e}")

def on_disconnect(client, userdata, rc):
    """Called when disconnected from MQTT broker."""
    if rc != 0:
        print(f"[{datetime.now()}] Unexpected disconnection. Attempting to reconnect...")

# ========== MAIN ==========
def main():
    """Main entry point for the Linux agent."""
    print(f"[{datetime.now()}] Starting EcoFlow Linux Agent")
    print(f"[{datetime.now()}] Agent ID: {AGENT_ID}")
    print(f"[{datetime.now()}] Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"[{datetime.now()}] Topic: {MQTT_TOPIC}")
    
    # Create MQTT client
    client = mqtt.Client(client_id=f"{AGENT_ID}-{os.getpid()}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Connect to broker
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"[{datetime.now()}] Failed to connect to broker: {e}")
        sys.exit(1)
    
    # Start listening loop
    print(f"[{datetime.now()}] Listening for commands...")
    client.loop_forever()

if __name__ == "__main__":
    main()
