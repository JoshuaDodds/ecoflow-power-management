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

# ========== CONFIGURATION ==========
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
AGENT_ID = os.getenv("AGENT_ID", "linux-agent")
MQTT_TOPIC = f"power-manager/{AGENT_ID}/cmd"

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
            print(f"[{datetime.now()}] Initiating system shutdown in 60 seconds...")
            
            # Execute shutdown command
            # -h: halt after shutdown
            # +1: delay 1 minute (gives time to abort if needed)
            subprocess.run([
                "sudo", "shutdown", "-h", "+1", 
                "EcoFlow Critical Battery Shutdown"
            ])
            
        elif action == "abort":
            print(f"[{datetime.now()}] ABORT command received!")
            print(f"[{datetime.now()}] Canceling pending shutdown...")
            
            # Cancel any pending shutdown
            subprocess.run(["sudo", "shutdown", "-c"])
            
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
