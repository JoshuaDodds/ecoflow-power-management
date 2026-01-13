#!/usr/bin/env python3
"""
EcoFlow Tag Hunter
identifies ProtoBuf tags by looking for specific value ranges known by the user.
"""
import os
import time
import sys
import threading
from typing import Tuple, List, Dict
import paho.mqtt.client as mqtt

# --- Configuration ---
# Update these ranges based on your actual loads (Watts * 10)
# Example: 100W load -> search for 1000 +/- tolerance
TARGETS = {
    "VOLTAGE_230V":  (2150, 2450),   # 215V - 245V
    "LOAD_METERKAST": (850, 1150),   # 85W - 115W (User said ~92-100W)
    "LOAD_STUDY":    (1800, 3000),   # 180W - 300W (User said ~192-280W)
    "SOC":           (80, 90)        # 0% - 100%
}

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

# --- Helpers (Standard Varint Decoder) ---
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

def scan_payload(payload: bytes, depth=0) -> Dict[str, int]:
    """Recursively scans for integer values."""
    results = {}
    i = 0
    while i < len(payload):
        try:
            tag, i = _read_varint(payload, i)
            field = tag >> 3
            wtype = tag & 0x7

            if wtype == 0: # Varint
                val, i = _read_varint(payload, i)
                results[f"d{depth}_t{field}"] = val
            elif wtype == 2: # Length Delimited
                ln, i = _read_varint(payload, i)
                # Try recursive scan
                if ln > 0:
                    try:
                        sub_results = scan_payload(payload[i:i+ln], depth + 1)
                        results.update(sub_results)
                    except:
                        pass
                i += ln
            elif wtype == 1: i += 8
            elif wtype == 5: i += 4
            else: break
        except Exception:
            break
    return results

# --- Main Logic ---
known_candidates = {k: set() for k in TARGETS}

def on_message(client, userdata, msg):
    if not msg.topic.endswith("/data"): return

    # Decode everything
    values = scan_payload(msg.payload)

    # Check against targets
    for tag, val in values.items():
        # Handle "Signed" values appearing as Unsigned large ints
        real_val = val
        if val > 4294900000: real_val = val - 4294967296

        for label, (low, high) in TARGETS.items():
            if low <= real_val <= high:
                if tag not in known_candidates[label]:
                    print(f"MATCH FOUND: {label} could be {tag} (Value: {real_val})")
                    known_candidates[label].add(tag)

def main():
    print("--- EcoFlow Tag Hunter ---")
    print(f"Listening for values in ranges: {TARGETS}")
    print("Keep this running for 30 seconds...")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ef-hunter")
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(f"{ECOFLOW_BASE}/+/data")

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\n--- SUMMARY OF CANDIDATES ---")
        for label, tags in known_candidates.items():
            print(f"{label}: {tags}")

if __name__ == "__main__":
    main()

