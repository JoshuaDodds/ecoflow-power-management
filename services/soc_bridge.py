#!/usr/bin/env python3
"""
EcoFlow Cloud MQTT Bridge (River 3 Plus / Simplified)

Focus: Reliable Shutdown Signals ONLY.
- SoC (Tag 6)
- Grid Status (Tag 27)
- Temperature (Tag 16)

Removes all experimental Wattage logic.
"""

import json
import os
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# Standard 'Quota' Request (Ask for data refresh)
# We will focus on making this reliable in the next phase.
HEARTBEAT_PAYLOAD_HEX = "0a00"
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("soc_bridge")


def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    val = 0
    while True:
        if i >= len(buf): raise ValueError("truncated varint")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80): return val, i
        shift += 7


def _extract_tags_with_depth(payload: bytes, depth=0, max_depth=4) -> List[Tuple[int, int, int]]:
    results = []
    if depth > max_depth: return results
    i = 0
    while i < len(payload):
        try:
            tag, i = _read_varint(payload, i)
            field = tag >> 3
            wtype = tag & 0x7
            if wtype == 0:
                val, i = _read_varint(payload, i)
                results.append((field, val, depth))
            elif wtype == 2:
                ln, i = _read_varint(payload, i)
                if ln > 0:
                    try:
                        sub = _extract_tags_with_depth(payload[i:i + ln], depth + 1, max_depth)
                        results.extend(sub)
                    except:
                        pass
                i += ln
            elif wtype == 1:
                i += 8
            elif wtype == 5:
                i += 4
            else:
                break
        except:
            break
    return results


# =============================
# State Management
# =============================

class DeviceState:
    def __init__(self, device_id):
        self.device_id = device_id
        self.soc = 0.0
        self.soc_modules = []
        self.grid_connected = False
        self.temp_celsius = 0.0
        self.last_update = 0

    def update(self, updates: dict):
        if "grid_connected" in updates:
            self.grid_connected = updates["grid_connected"]

        if "temp_celsius" in updates:
            self.temp_celsius = updates["temp_celsius"]

        self.last_update = time.time()

    def update_soc(self, soc_list: List[int]):
        valid = [s for s in soc_list if 0 <= s <= 100]
        if not valid: return

        # Simple Glitch Filter (Ignore single outliers >10% jump)
        if self.soc > 0 and abs(valid[0] - self.soc) > 10 and len(valid) == 1:
            return

        self.soc_modules = valid
        self.soc = round(sum(valid) / len(valid), 2)

    def to_json(self):
        return {
            "ts": int(self.last_update * 1000),
            "device": self.device_id,
            "soc": self.soc,
            "soc_modules": self.soc_modules,
            "grid_connected": self.grid_connected,
            "temp_celsius": self.temp_celsius
        }


devices: Dict[str, DeviceState] = {}
devices_lock = threading.Lock()

# =============================
# MQTT & Heartbeat
# =============================

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "ecoflow-soc-bridge")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")


def heartbeat_loop(client: mqtt.Client):
    # This is the simplified Quota request.
    # The next phase will focus exclusively on making this work reliably without the App.
    payload = bytes.fromhex(HEARTBEAT_PAYLOAD_HEX)
    logger.info(f"Heartbeat Active. Sending every 10s.")
    while True:
        time.sleep(10)
        with devices_lock:
            target_devs = list(devices.keys())
        for dev in target_devs:
            try:
                # Sending to both common command topics to be sure
                client.publish(f"{ECOFLOW_BASE}/{dev}/quota", payload)
                client.publish(f"{ECOFLOW_BASE}/{dev}/get", payload)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")


def on_connect(client, userdata, flags, reason_code, properties=None):
    logger.info("Connected to MQTT.")
    client.subscribe(f"{ECOFLOW_BASE}/+/data")


def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) != 3: return
    device_id = parts[1]

    with devices_lock:
        if device_id not in devices:
            devices[device_id] = DeviceState(device_id)
        dev_state = devices[device_id]

    all_tags = _extract_tags_with_depth(msg.payload, max_depth=4)

    raw_socs = []
    updates = {}

    for tag, val, depth in all_tags:
        # SoC: Tag 6 @ Depth >= 2
        if tag == 6 and depth >= 2:
            raw_socs.append(val)

        # Grid Status: Tag 27 (0=True, 127=False)
        if tag == 27:
            updates["grid_connected"] = (val == 0)

        # Temp: Tag 16 @ Depth 2 (Unit 0.01 C)
        if tag == 16 and depth == 2:
            updates["temp_celsius"] = val / 100.0

    # Apply Updates
    if raw_socs: dev_state.update_soc(raw_socs)
    if updates: dev_state.update(updates)

    # Publish Clean State
    if raw_socs or updates:
        client.publish(f"{ECOFLOW_BASE}/{device_id}/json/state", json.dumps(dev_state.to_json()))


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)

    hb_thread = threading.Thread(target=heartbeat_loop, args=(client,), daemon=True)
    hb_thread.start()

    client.loop_forever()


if __name__ == "__main__":
    main()