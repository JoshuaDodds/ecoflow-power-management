#!/usr/bin/env python3
"""
EcoFlow Diff Hunter (Target: STUDY)
Identifies unknown tags by comparing "State A" (Plugged In) vs "State B" (Unplugged).
Filters strictly for the 'Study' device.
"""
import os
import time
import sys
import threading
from typing import Dict, Tuple
import paho.mqtt.client as mqtt

# --- Config ---
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

# Only process topics containing this string (Case Insensitive)
TARGET_DEVICE_KEYWORD = "STUDY"

# --- Global State ---
latest_state = {}  # { "dDepth_tTag": value }
lock = threading.Lock()


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


def scan_payload(payload: bytes, depth=0):
    """Recursively extracts all integer tags."""
    i = 0
    local_found = {}
    while i < len(payload):
        try:
            tag, i = _read_varint(payload, i)
            field = tag >> 3
            wtype = tag & 0x7

            if wtype == 0:  # Varint
                val, i = _read_varint(payload, i)
                # Filter massive/negative junk
                if val < 999999:
                    local_found[f"d{depth}_t{field}"] = val
            elif wtype == 2:  # Length Delimited
                ln, i = _read_varint(payload, i)
                if ln > 0:
                    # Recurse
                    sub = scan_payload(payload[i:i + ln], depth + 1)
                    local_found.update(sub)
                i += ln
            elif wtype == 1:
                i += 8
            elif wtype == 5:
                i += 4
            else:
                break
        except Exception:
            break
    return local_found


# --- MQTT ---
def on_message(client, userdata, msg):
    # 1. Filter for Data
    if not msg.topic.endswith("/data"): return

    # 2. Strict Filter for STUDY device
    if TARGET_DEVICE_KEYWORD.lower() not in msg.topic.lower():
        return

    vals = scan_payload(msg.payload)
    with lock:
        latest_state.update(vals)


# --- Interactive Mode ---
def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ef-diff-study")
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(f"{ECOFLOW_BASE}/+/data")

    # Start BG Thread
    t = threading.Thread(target=client.loop_forever)
    t.daemon = True
    t.start()

    print("\n=== EcoFlow Diff Hunter (Target: STUDY) ===")
    print("1. Ensure 'STUDY' device is PLUGGED IN (AC Connected).")
    print("2. Waiting 10s to build baseline...")
    time.sleep(10)

    with lock:
        snapshot_a = latest_state.copy()

    if not snapshot_a:
        print("\n[ERROR] No data received from 'STUDY'. Check if device name matches exactly.")
        sys.exit(1)

    print(f"   Baseline captured ({len(snapshot_a)} tags found).")

    input("\n>>> ACTION: UNPLUG the AC Cable now, then press ENTER...")
    print("   Listening for updates (10s)...")
    time.sleep(10)

    with lock:
        snapshot_b = latest_state.copy()

    print("\n=== Analysis Results (Study Unit) ===")
    print(f"{'TAG':<20} | {'PLUGGED':<10} | {'UNPLUGGED':<10} | {'DIFF'}")
    print("-" * 60)

    found_any = False
    for tag, val_a in snapshot_a.items():
        val_b = snapshot_b.get(tag, val_a)  # Default to A if no update (unchanged)

        diff = val_a - val_b

        # We want to see significant changes (like 2300 -> 0)
        # Filter out tiny jitters (less than 5)
        if abs(diff) > 5:
            # Highlight Voltage-like drops (2000+)
            if val_a > 2000 and val_b < 100:
                print(f"{tag:<20} | {val_a:<10} | {val_b:<10} | {diff} (Likely Voltage!)")
            else:
                print(f"{tag:<20} | {val_a:<10} | {val_b:<10} | {diff}")
            found_any = True

    if not found_any:
        print("No significant changes detected.")


if __name__ == "__main__":
    main()