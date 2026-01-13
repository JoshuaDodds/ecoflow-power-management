#!/usr/bin/env python3
"""
EcoFlow Protobuf Scanner (Universal Decoder)
Use this to identify which Tag ID corresponds to which value on your device.
"""
import os
import json
import time
import sys
from typing import Tuple, List
import paho.mqtt.client as mqtt

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

# --- Helpers ---
def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    val = 0
    while True:
        if i >= len(buf): raise ValueError("EOF")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80): return val, i
        shift += 7

def scan_fields(payload: bytes, depth=0):
    i = 0
    results = {}
    
    while i < len(payload):
        try:
            start_i = i
            tag, i = _read_varint(payload, i)
            field = tag >> 3
            wtype = tag & 0x7
            
            value = None
            
            if wtype == 0: # Varint (Int, Bool, Enum)
                val, i = _read_varint(payload, i)
                value = val
                # Heuristic: Large varints might be signed
                if val > 2147483647: value = f"{val} (raw) / {val-4294967296} (signed)"
                
            elif wtype == 1: # 64-bit
                i += 8
                value = "[64-bit Data]"
                
            elif wtype == 2: # Length Delimited (String, Bytes, Nested Msg)
                ln, i = _read_varint(payload, i)
                data = payload[i : i + ln]
                i += ln
                
                # RECURSIVE CHECK: Does this look like a nested message?
                # If it starts with a valid varint tag, we try to scan it.
                is_nested = False
                if ln > 0:
                    try:
                        # Attempt to scan sub-message
                        sub_scan = scan_fields(data, depth + 1)
                        if sub_scan: # If we found valid fields
                            value = sub_scan
                            is_nested = True
                    except:
                        pass
                
                if not is_nested:
                    value = f"[Bytes len={ln}]"

            elif wtype == 5: # 32-bit (Float usually)
                i += 4
                value = "[32-bit Data]"
            else:
                break
            
            results[f"Tag_{field}"] = value
            
        except Exception:
            break
            
    return results

# --- MQTT Handlers ---
def on_message(client, userdata, msg):
    # Only look at data topics
    if not msg.topic.endswith("/data"): return
    
    print(f"\n--- Message from {msg.topic} ---")
    
    # 1. Try generic scan
    decoded = scan_fields(msg.payload)
    
    # 2. Flatten for display
    def print_tree(d, indent=0):
        for k, v in d.items():
            if isinstance(v, dict):
                print("  " * indent + f"{k}:")
                print_tree(v, indent + 1)
            else:
                print("  " * indent + f"{k}: {v}")

    print_tree(decoded)
    print("-" * 30)

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ef-scanner")
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(f"{ECOFLOW_BASE}/+/data")
    print(f"Scanning {ECOFLOW_BASE}/+/data ... Press Ctrl+C to stop.")
    client.loop_forever()

if __name__ == "__main__":
    main()

