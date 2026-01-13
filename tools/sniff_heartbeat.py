#!/usr/bin/env python3
"""
EcoFlow Heartbeat Sniffer
Captures commands sent FROM the App TO the Device.
Use this to find the "Keep Alive" payload.
"""
import os
import time
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

def on_message(client, userdata, msg):
    # We want /set or /get (Commands from App)
    if not (msg.topic.endswith("/set") or msg.topic.endswith("/get")):
        return
        
    print(f"\n--- COMMAND DETECTED on {msg.topic} ---")
    print(f"Payload (Hex): {msg.payload.hex()}")
    print("-" * 40)
    print("^ COPY THIS HEX STRING ^")

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ef-sniffer")
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    
    # Subscribe to command topics
    client.subscribe(f"{ECOFLOW_BASE}/+/set")
    client.subscribe(f"{ECOFLOW_BASE}/+/get")
    
    print("Listening for App Commands... Open your EcoFlow App now!")
    client.loop_forever()

if __name__ == "__main__":
    main()

