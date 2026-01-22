#!/usr/bin/env python3
"""
EcoFlow Local SOC Bridge (Thin Layer)
- ROLE: Connects Local MQTT <-> Device Library.
"""

import json
import os
import sys
import time
import logging
import threading
import paho.mqtt.client as mqtt

# Add services/lib to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.ecoflow_river3plus import EcoFlowDevice
from utils.soc_filter import SOCFilter
from utils.state_filter import BooleanStateFilter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("soc_bridge")

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")

# State Store
devices: dict[str, EcoFlowDevice] = {}
devices_lock = threading.Lock()

# SOC Filters (one per device)
soc_filters: dict[str, SOCFilter] = {}

# Grid Connected Filters (one per device)
grid_filters: dict[str, BooleanStateFilter] = {}


def on_connect(client, userdata, flags, rc, props=None):
    logger.info("Connected to Local MQTT.")
    client.subscribe(f"{ECOFLOW_BASE}/+/data")


def on_message(client, userdata, msg):
    try:
        parts = msg.topic.split("/")
        if len(parts) < 3: return
        sn = parts[1]

        with devices_lock:
            if sn not in devices:
                logger.info(f"New Device Discovered: {sn}")
                devices[sn] = EcoFlowDevice(sn)
            device = devices[sn]

        if device.update_from_protobuf(msg.payload):
            # Apply filtering to device state
            device_json = device.to_json()
            current_time = time.time()
            
            # Filter SOC reading
            raw_soc = device_json.get("soc")
            if raw_soc is not None:
                # Initialize filter for new device
                if sn not in soc_filters:
                    soc_filters[sn] = SOCFilter(sn)
                
                # Filter SOC reading
                filtered_soc = soc_filters[sn].filter(raw_soc, current_time)
                
                if filtered_soc is None:
                    # Rejected as anomaly - don't publish this update
                    logger.debug(f"[{sn}] Skipping publish due to rejected SOC reading")
                    return
                
                # Update device JSON with filtered SOC
                device_json["soc"] = filtered_soc
            
            # Filter grid_connected status
            raw_grid = device_json.get("grid_connected")
            if raw_grid is not None:
                # Initialize filter for new device
                if sn not in grid_filters:
                    grid_filters[sn] = BooleanStateFilter(sn, "grid_connected", required_confirmations=5)
                
                # Filter grid_connected status
                filtered_grid = grid_filters[sn].filter(raw_grid, current_time)
                
                # Update device JSON with filtered grid status
                device_json["grid_connected"] = filtered_grid
            
            payload_str = json.dumps(device_json)
            client.publish(f"{ECOFLOW_BASE}/{sn}/json/state", payload_str)

    except Exception as e:
        logger.error(f"Bridge Error: {e}")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ecoflow-soc-bridge-local")
    try:
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        logger.error(f"Startup Failed: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()