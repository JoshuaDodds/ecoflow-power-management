#!/usr/bin/env python3
"""
EcoFlow Cloud MQTT Bridge (MQTT-Only Wakeup)

- STRATEGY: Abandons HTTP Wakelock. Uses MQTT to request data.
- ACTION: Sends 'CmdId 0' (Get All) and 'CmdId 1' (Ping) via MQTT.
- PATH: Publishes to both .../set and .../get topics to ensure delivery.
"""

import json
import os
import sys
import time
import logging
import threading
from typing import Dict, List, Tuple

import paho.mqtt.client as mqtt

# --- Import Utils ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import env_loader

# ==============================================================================
# CONFIGURATION
# ==============================================================================
GRID_DEBOUNCE_SEC = 5.0

# "Android" Tag for Protobuf (Tag 23): ba 01 (Tag) + 07 (Len) + "android"
# We match the ClientID identity to avoid "Schizophrenic" rejection.
ANDROID_SUFFIX = bytes.fromhex("ba0107616e64726f6964")

# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("soc_bridge")

# --- Protobuf Helpers ---
def encode_varint(val: int) -> bytes:
    out = []
    while True:
        byte = val & 0x7F
        val >>= 7
        if val: out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)

def forge_packet(cmd_id: int) -> bytes:
    """
    Forges a standardized EcoFlow Packet.
    cmd_id 0 = Get All (Quota) -> Forces device to report everything.
    cmd_id 1 = Ping (Heartbeat) -> Keeps connection alive.
    """
    seq = int(time.time())
    
    # HEADER (Field 1):
    # Tag 2(Src)=32, Tag 3(Dst)=32, Tag 14(Seq)=Timestamp
    # Tag 23(Type)=3 (Request) + "android" string
    header_content = (
        b'\x10\x20' +            # Src: 32
        b'\x18\x20' +            # Dst: 32
        b'\x70' + encode_varint(seq) + # Seq
        ANDROID_SUFFIX           # Type 3 + "android"
    )

    # PAYLOAD (Field 2):
    # Tag 1 (08) = CmdID
    payload_content = b'\x08' + encode_varint(cmd_id)
    
    # Combine: 0a L [Header] 12 L [Payload]
    packet = (
        b'\x0a' + encode_varint(len(header_content)) + header_content +
        b'\x12' + encode_varint(len(payload_content)) + payload_content
    )
    return packet

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
                        sub = _extract_tags_with_depth(payload[i:i+ln], depth + 1, max_depth)
                        results.extend(sub)
                    except: pass
                i += ln
            elif wtype == 1: i += 8
            elif wtype == 5: i += 4
            else: break
        except: break
    return results

def to_signed_value(val: int) -> float:
    if val > 4294900000: return 0.0
    if val == 65535: return 0.0
    if val > 32768: return (val - 65536) / 10.0
    return val / 10.0

# =============================
# Device State
# =============================
class DeviceState:
    def __init__(self, device_id):
        self.device_id = device_id
        self.soc = 0.0
        self.soc_modules = []
        self.ac_in_watts = 0.0
        self.grid_connected = True
        self.temp_celsius = 0.0
        self.last_update = 0
        self.pending_grid_state = True
        self.debounce_start_time = 0.0
        
    def update_power(self, updates: dict):
        if "temp_celsius" in updates: 
            self.temp_celsius = updates["temp_celsius"]

        if "grid_connected" in updates:
            raw = updates["grid_connected"]
            if raw == self.grid_connected:
                self.debounce_start_time = 0.0
                self.pending_grid_state = raw
            else:
                if raw != self.pending_grid_state:
                    self.pending_grid_state = raw
                    self.debounce_start_time = time.time()
                
                if self.debounce_start_time > 0 and (time.time() - self.debounce_start_time) > GRID_DEBOUNCE_SEC:
                    self.grid_connected = raw
                    self.debounce_start_time = 0.0
                    logger.info(f"[{self.device_id}] Grid State Confirmed: {self.grid_connected}")

        if "ac_in_watts" in updates:
            raw = updates["ac_in_watts"]
            is_ghost = False
            if self.ac_in_watts > 10 and raw > 10:
                ratio = raw / self.ac_in_watts
                if 1.8 < ratio < 2.2: is_ghost = True
            if not is_ghost:
                self.ac_in_watts = raw

        self.last_update = time.time()
        
    def update_soc(self, soc_list: List[int]):
        valid = [s for s in soc_list if 0 <= s <= 100]
        if not valid: return
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
# MQTT Client
# =============================

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "ecoflow-soc-bridge")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

def on_connect(client, userdata, flags, reason_code, properties=None):
    logger.info("Connected to MQTT.")
    client.subscribe(f"{ECOFLOW_BASE}/+/data")
    # Also listen to replies to verify we are reaching the device
    client.subscribe(f"{ECOFLOW_BASE}/+/set_reply")
    client.subscribe(f"{ECOFLOW_BASE}/+/get_reply")

def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) != 3: return
    device_id = parts[1]
    
    with devices_lock:
        if device_id not in devices:
            devices[device_id] = DeviceState(device_id)
        dev_state = devices[device_id]

    try:
        all_tags = _extract_tags_with_depth(msg.payload, max_depth=4)
        raw_socs = []
        updates = {}
        
        for tag, val, depth in all_tags:
            if tag == 6 and depth >= 2: raw_socs.append(val)
            if tag == 28: updates["ac_in_watts"] = to_signed_value(val)
            if tag == 27: updates["grid_connected"] = (val == 0)
            if tag == 16 and depth == 2: updates["temp_celsius"] = val / 100.0

        if raw_socs: dev_state.update_soc(raw_socs)
        if updates: dev_state.update_power(updates)

        if raw_socs or updates:
            client.publish(f"{ECOFLOW_BASE}/{device_id}/json/state", json.dumps(dev_state.to_json()))
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def heartbeat_loop(client: mqtt.Client):
    logger.info(f"MQTT Heartbeat Active. PING(10s) + QUOTA(60s).")
    
    last_refresh = 0
    
    while True:
        try:
            now = time.time()
            
            # 1. PING (Cmd 1) - Keepalive
            pkt_ping = forge_packet(1)
            
            # 2. QUOTA (Cmd 0) - The "Wake Up" command
            pkt_quota = None
            if now - last_refresh > 60:
                pkt_quota = forge_packet(0)
                last_refresh = now
            
            with devices_lock:
                target_devs = list(devices.keys())
            
            for dev in target_devs:
                # Send PING
                client.publish(f"{ECOFLOW_BASE}/{dev}/set", pkt_ping)
                
                # Send QUOTA (Try both SET and GET topics to be sure)
                if pkt_quota:
                    client.publish(f"{ECOFLOW_BASE}/{dev}/quota", pkt_quota)
                    client.publish(f"{ECOFLOW_BASE}/{dev}/get", pkt_quota)
                    client.publish(f"{ECOFLOW_BASE}/{dev}/set", pkt_quota)
                    logger.info(f"[{dev}] Sent MQTT Wakeup (Cmd 0)")
                    
            time.sleep(10)
                
        except Exception as e:
            logger.error(f"Heartbeat Loop Error: {e}")
            time.sleep(5)

def main():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
        if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        
        hb_thread = threading.Thread(target=heartbeat_loop, args=(client,), daemon=True)
        hb_thread.start()
        
        client.loop_forever()
    except Exception as e:
        logger.error(f"Main Loop Crash: {e}")
        time.sleep(10)

if __name__ == "__main__":
    main()

