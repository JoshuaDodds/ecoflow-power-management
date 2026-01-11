#!/usr/bin/env python3
import os
import json
import time
from typing import List, Tuple, Optional, Dict, Any

import paho.mqtt.client as mqtt
from google.protobuf.message import DecodeError

import powerstream_pb2


MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "")
MQTT_PASS = os.environ.get("MQTT_PASS", "")

# Subscribe to multiple mirrored topics per device
# bridge-ecoflow/<device>/{data,get_reply,set_reply}
SUB_TOPIC = os.environ.get("SUB_TOPIC", "bridge-ecoflow/+/#")

PUB_ROOT = os.environ.get("PUB_ROOT", "bridge-ecoflow")
PUBLISH_RAW_HEX = os.environ.get("PUBLISH_RAW_HEX", "0") == "1"


def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if i >= len(buf):
            raise ValueError("varint truncated")
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, i
        shift += 7
        if shift > 64:
            raise ValueError("varint too long")


def extract_len_delimited_field1_messages(payload: bytes) -> List[bytes]:
    """
    EcoFlow frames we saw look like repeated field #1 length-delimited:
      0a <len> <inner> [0a <len> <inner>]...
    """
    out: List[bytes] = []
    i = 0
    while i < len(payload):
        if payload[i] != 0x0A:
            break
        i += 1
        try:
            length, i = _read_varint(payload, i)
        except ValueError:
            break
        if length <= 0 or i + length > len(payload):
            break
        out.append(payload[i : i + length])
        i += length
    return out


def parse_topic(topic: str) -> Tuple[str, str]:
    # bridge-ecoflow/<device>/<leaf...>
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "bridge-ecoflow":
        device = parts[1]
        leaf = "/".join(parts[2:])
        return device, leaf
    return "unknown", topic


def pub_topic(device: str, leaf: str, suffix: str) -> str:
    # bridge-ecoflow/<device>/json/<leaf>/<suffix>
    # leaf like "data" or "get_reply"
    safe_leaf = leaf.replace("/", "_")
    return f"{PUB_ROOT}/{device}/json/{safe_leaf}/{suffix}"


def decode_inverter_heartbeat(inner: bytes) -> Dict[str, Any]:
    msg = powerstream_pb2.InverterHeartbeat()
    msg.ParseFromString(inner)

    # Fields that were actually present on the wire:
    present = [fd.name for fd, _ in msg.ListFields()]

    # For optional fields, HasField is meaningful
    has_bat_soc = False
    try:
        has_bat_soc = msg.HasField("bat_soc")
    except Exception:
        pass

    decoded = {
        "present_fields": present,
        "has_bat_soc": has_bat_soc,
        "bat_soc": getattr(msg, "bat_soc", None),
        "inv_status": getattr(msg, "inv_status", None),
        "llc_status": getattr(msg, "llc_status", None),
        "pv1_status": getattr(msg, "pv1_status", None),
        "pv1_input_volt": getattr(msg, "pv1_input_volt", None),
        "pv1_op_volt": getattr(msg, "pv1_op_volt", None),
        "inv_warning_code": getattr(msg, "inv_warning_code", None),
        "pv1_warning_code": getattr(msg, "pv1_warning_code", None),
        "pv2_warning_code": getattr(msg, "pv2_warning_code", None),
        "bat_warning_code": getattr(msg, "bat_warning_code", None),
        "inv_error_code": getattr(msg, "inv_error_code", None),
        "pv1_error_code": getattr(msg, "pv1_error_code", None),
        "pv2_error_code": getattr(msg, "pv2_error_code", None),
        "bat_error_code": getattr(msg, "bat_error_code", None),
        "llc_error_code": getattr(msg, "llc_error_code", None),
        "llc_warning_code": getattr(msg, "llc_warning_code", None),
    }
    return decoded


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"[mqtt] connect failed rc={rc}")
        return
    print(f"[mqtt] connected {MQTT_HOST}:{MQTT_PORT} subscribing {SUB_TOPIC}")
    client.subscribe(SUB_TOPIC, qos=0)


def on_message(client, userdata, msg):
    now = int(time.time())
    device, leaf = parse_topic(msg.topic)

    # Only process the ecoflow mirrored leaves we care about (read-only)
    if leaf not in ("data", "get_reply", "set_reply"):
        return

    payload: bytes = msg.payload
    inners = extract_len_delimited_field1_messages(payload)

    if not inners:
        diag = {
            "ts": now,
            "src_topic": msg.topic,
            "device": device,
            "leaf": leaf,
            "note": "no_field1_len_delimited_frames_found",
            "payload_len": len(payload),
        }
        client.publish(pub_topic(device, leaf, "diagnostic"), json.dumps(diag), qos=0, retain=False)
        return

    for idx, inner in enumerate(inners):
        base = {
            "ts": now,
            "src_topic": msg.topic,
            "device": device,
            "leaf": leaf,
            "frame_index": idx,
            "inner_len": len(inner),
        }
        if PUBLISH_RAW_HEX:
            base["raw_hex"] = inner.hex()

        # Try decode as InverterHeartbeat (we'll add more types next)
        try:
            decoded = decode_inverter_heartbeat(inner)
            out = {**base, "type": "InverterHeartbeat", "decoded": decoded}
            client.publish(pub_topic(device, leaf, "heartbeat"), json.dumps(out), qos=0, retain=False)
        except DecodeError as e:
            err = {**base, "type": "InverterHeartbeat", "error": f"DecodeError: {e}"}
            client.publish(pub_topic(device, leaf, "decode_error"), json.dumps(err), qos=0, retain=False)


def main():
    client = mqtt.Client(client_id=os.environ.get("CLIENT_ID", "ecoflow-bridge-proto"), clean_session=True)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
