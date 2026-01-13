#!/usr/bin/env python3
"""
EcoFlow Deep Monitor
Continuously watches traffic and prints the structure of ANY new message type.
Use this to capture the specific "Power Status" packet which appears periodically.
"""
import os
import sys
import hashlib
import time
import paho.mqtt.client as mqtt

# --- Config ---
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")
TARGET_DEVICE = "STUDY"  # Case insensitive

# --- State ---
seen_fingerprints = set()


# --- Helper: Recursive Decoder ---
def _read_varint(buf: bytes, i: int):
    shift = 0
    val = 0
    while True:
        if i >= len(buf): raise ValueError("EOF")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80): return val, i
        shift += 7


def decode_tree(payload: bytes, indent=0) -> str:
    """Returns a string representation of the tree for printing"""
    out = []
    i = 0
    while i < len(payload):
        try:
            tag, i = _read_varint(payload, i)
            field = tag >> 3
            wtype = tag & 0x7

            prefix = "  " * indent + f"├── [{field}] "

            if wtype == 0:  # Varint
                val, i = _read_varint(payload, i)
                out.append(f"{prefix}Int: {val}")

            elif wtype == 2:  # Length Delimited
                ln, i = _read_varint(payload, i)
                data = payload[i: i + ln]

                # Speculative recursion check
                is_nested = False
                if ln > 0:
                    try:
                        # Try to decode inner; if it fails or looks junk, treat as bytes
                        sub_out = decode_tree(data, indent + 1)
                        if sub_out:
                            out.append(f"{prefix}Container (len={ln}):")
                            out.append(sub_out)
                            is_nested = True
                    except:
                        is_nested = False

                if not is_nested:
                    # Show hex for short bytes
                    hex_s = data.hex()[:20] + "..." if len(data) > 10 else data.hex()
                    out.append(f"{prefix}Bytes: {hex_s}")

                i += ln

            elif wtype == 1:  # 64-bit
                i += 8
                out.append(f"{prefix}64-bit data")
            elif wtype == 5:  # 32-bit
                i += 4
                out.append(f"{prefix}32-bit data")
            else:
                break  # Unknown

        except Exception:
            break

    return "\n".join(out)


def get_structure_fingerprint(payload: bytes) -> str:
    """Creates a hash based on the TAGS present (ignoring values)"""
    # Simple tag extraction for fingerprinting
    tags = []
    i = 0
    while i < len(payload):
        try:
            tag, i = _read_varint(payload, i)
            tags.append(str(tag >> 3))
            wtype = tag & 0x7
            if wtype == 0:
                _read_varint(payload, i)
            elif wtype == 2:
                ln, i = _read_varint(payload, i)
                i += ln
            elif wtype == 1:
                i += 8
            elif wtype == 5:
                i += 4
            else:
                break
        except:
            break
    return "-".join(tags)


# --- MQTT Handler ---
def on_message(client, userdata, msg):
    if TARGET_DEVICE.lower() not in msg.topic.lower(): return
    if not msg.topic.endswith("/data"): return

    # 1. Generate Fingerprint (Signature of fields)
    fp = get_structure_fingerprint(msg.payload)

    # 2. If new, print it!
    if fp not in seen_fingerprints:
        seen_fingerprints.add(fp)
        print(f"\n\n=== NEW MSG TYPE DETECTED [{len(msg.payload)} bytes] ===")
        print(f"Topic: {msg.topic}")
        print("Decoding...")
        print(decode_tree(msg.payload))
        print("==========================================")
    else:
        # Optional: Print dot for heartbeat
        sys.stdout.write(".")
        sys.stdout.flush()


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ef-monitor")
    if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(f"{ECOFLOW_BASE}/+/data")

    print(f"Listening for ALL message types from '{TARGET_DEVICE}'...")
    print("Wait ~30 seconds. You should see different structures appear.")
    client.loop_forever()


if __name__ == "__main__":
    main()