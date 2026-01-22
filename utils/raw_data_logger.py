#!/usr/bin/env python3
"""
Raw Protobuf Data Logger

Captures raw protobuf messages and logs both:
1. Raw hex bytes
2. Decoded field values
3. All tag 6 occurrences (SOC candidates)

This helps identify parsing issues by correlating anomalous SOC values
with their raw byte representation.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
import paho.mqtt.client as mqtt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.lib.ecoflow_river3plus import EcoFlowDevice

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("raw_data_logger")

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")
LOG_DIR = os.getenv("LOG_DIR", "/tmp/ecoflow_raw_logs")

# Create log directory
os.makedirs(LOG_DIR, exist_ok=True)

class RawMessageLogger:
    """Logs raw protobuf messages with detailed analysis"""
    
    def __init__(self, serial_number: str):
        self.sn = serial_number
        self.device = EcoFlowDevice(serial_number)
        self.message_count = 0
        self.log_file = os.path.join(LOG_DIR, f"{serial_number}_{int(time.time())}.jsonl")
        logger.info(f"[{self.sn}] Logging to: {self.log_file}")
    
    def parse_all_tag6_values(self, payload: bytes) -> list:
        """Find ALL occurrences of tag 6 (SOC) in the payload"""
        tag6_values = []
        
        i = 0
        while i < len(payload):
            try:
                # Read tag
                tag_val = 0
                shift = 0
                tag_start = i
                
                while True:
                    if i >= len(payload):
                        break
                    b = payload[i]
                    i += 1
                    tag_val |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                
                field = tag_val >> 3
                wtype = tag_val & 0x7
                
                # Read value based on wire type
                if wtype == 0:  # Varint
                    val = 0
                    shift = 0
                    val_start = i
                    
                    while True:
                        if i >= len(payload):
                            break
                        b = payload[i]
                        i += 1
                        val |= (b & 0x7F) << shift
                        if not (b & 0x80):
                            break
                        shift += 7
                    
                    # Check if this is tag 6
                    if field == 6:
                        tag6_values.append({
                            "offset": tag_start,
                            "tag": tag_val,
                            "field": field,
                            "value": val,
                            "bytes": payload[tag_start:i].hex()
                        })
                
                elif wtype == 2:  # Length-delimited
                    length = 0
                    shift = 0
                    while True:
                        if i >= len(payload):
                            break
                        b = payload[i]
                        i += 1
                        length |= (b & 0x7F) << shift
                        if not (b & 0x80):
                            break
                        shift += 7
                    
                    # Skip the data
                    i += length
                
                elif wtype == 1:  # 64-bit
                    i += 8
                elif wtype == 5:  # 32-bit
                    i += 4
                else:
                    # Unknown wire type, stop parsing
                    break
                    
            except:
                break
        
        return tag6_values
    
    def log_message(self, payload: bytes):
        """Log a single message with full analysis"""
        self.message_count += 1
        timestamp = time.time()
        
        # Decode using the device library
        valid_data = self.device.update_from_protobuf(payload)
        device_state = self.device.to_json()
        
        # Find all tag 6 values
        all_tag6 = self.parse_all_tag6_values(payload)
        
        # Create log entry
        log_entry = {
            "timestamp": timestamp,
            "iso_time": datetime.fromtimestamp(timestamp).isoformat(),
            "message_number": self.message_count,
            "device": self.sn,
            "raw_hex": payload.hex(),
            "raw_length": len(payload),
            "decoded_state": device_state,
            "valid_data": valid_data,
            "all_tag6_occurrences": all_tag6,
            "tag6_count": len(all_tag6)
        }
        
        # Write to JSONL file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        # Log to console if SOC changed or multiple tag 6 values found
        if len(all_tag6) > 0:
            soc_values = [t["value"] for t in all_tag6]
            logger.info(
                f"[{self.sn}] MSG #{self.message_count}: "
                f"SOC={device_state.get('soc')}% | "
                f"Tag6 values: {soc_values} | "
                f"Hex length: {len(payload)} bytes"
            )
            
            # Warn if multiple different tag 6 values found
            if len(set(soc_values)) > 1:
                logger.warning(
                    f"[{self.sn}] ⚠️  MULTIPLE DIFFERENT TAG 6 VALUES: {soc_values}"
                )

# --- MQTT Handlers ---
loggers = {}

def on_connect(client, userdata, flags, rc, props=None):
    logger.info("Connected to Local MQTT")
    client.subscribe(f"{ECOFLOW_BASE}/+/data")
    logger.info(f"Subscribed to: {ECOFLOW_BASE}/+/data")

def on_message(client, userdata, msg):
    try:
        # Extract serial number from topic
        parts = msg.topic.split("/")
        if len(parts) < 3:
            return
        sn = parts[1]
        
        # Create logger for new device
        if sn not in loggers:
            logger.info(f"Discovered device: {sn}")
            loggers[sn] = RawMessageLogger(sn)
        
        # Log the message
        loggers[sn].log_message(msg.payload)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("RAW PROTOBUF DATA LOGGER")
    logger.info("=" * 80)
    logger.info(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    logger.info(f"Topic: {ECOFLOW_BASE}/+/data")
    logger.info(f"Log Directory: {LOG_DIR}")
    logger.info("=" * 80)
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="raw-data-logger")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        logger.info("Starting MQTT loop...")
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("\nStopping logger...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
