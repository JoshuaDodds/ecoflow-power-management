#!/usr/bin/env python3
import base64
import json
import os
import time
from typing import Any, Dict, List, Tuple

import paho.mqtt.client as mqtt


def read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    val = 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7
        if shift > 70:
            raise ValueError("varint too large")


def split_length_delimited_frames(payload: bytes) -> List[bytes]:
    frames: List[bytes] = []
    i = 0
    try:
        while i < len(payload):
            ln, j = read_varint(payload, i)
            if ln < 0 or j + ln > len(payload):
                return [payload]
            frames.append(payload[j : j + ln])
            i = j + ln
        return frames if frames else [payload]
    except ValueError:
        return [payload]


def protobuf_wire_dump(msg: bytes, max_len: int = 8192) -> Dict[str, Any]:
    out: Dict[str, Any] = {"len": len(msg), "fields": []}
    i = 0
    end = min(len(msg), max_len)

    while i < end:
        try:
            key, i = read_varint(msg, i)
        except ValueError:
            out["trailing_b64"] = base64.b64encode(msg[i:]).decode()
            break

        field_no = key >> 3
        wire = key & 0x7
        entry: Dict[str, Any] = {"field": field_no, "wire": wire}

        try:
            if wire == 0:  # varint
                v, i = read_varint(msg, i)
                entry["varint"] = v
            elif wire == 1:  # 64-bit
                if i + 8 > end:
                    raise ValueError("truncated 64-bit")
                entry["fixed64_hex"] = msg[i:i+8].hex()
                i += 8
            elif wire == 2:  # length-delimited
                ln, i = read_varint(msg, i)
                if i + ln > len(msg):
                    raise ValueError("truncated len")
                chunk = msg[i:i+ln]
                entry["len"] = ln
                preview = chunk[:64]
                try:
                    entry["utf8_preview"] = preview.decode("utf-8")
                except UnicodeDecodeError:
                    entry["b64_preview"] = base64.b64encode(preview).decode()
                # include full b64 for small blobs only
                if ln <= 1024:
                    entry["b64"] = base64.b64encode(chunk).decode()
                i += ln
            elif wire == 5:  # 32-bit
                if i + 4 > end:
                    raise ValueError("truncated 32-bit")
                entry["fixed32_hex"] = msg[i:i+4].hex()
                i += 4
            else:
                entry["unsupported_wire"] = True
                out["fields"].append(entry)
                break

        except ValueError:
            entry["decode_error"] = True
            out["fields"].append(entry)
            out["trailing_b64"] = base64.b64encode(msg[i:]).decode()
            break

        out["fields"].append(entry)

    return out


def extract_field1_len_delimited(payload: bytes) -> List[bytes]:
    # repeated: 0x0A <len> <bytes>
    inners: List[bytes] = []
    i = 0
    while i < len(payload):
        if payload[i] != 0x0A:
            break
        i += 1
        try:
            ln, i = read_varint(payload, i)
        except ValueError:
            break
        if ln <= 0 or i + ln > len(payload):
            break
        inners.append(payload[i:i+ln])
        i += ln
    return inners


def unwrap_field1_chain(payload: bytes, max_depth: int = 5) -> List[bytes]:
    """
    Keep unwrapping 'field 1 length-delimited' if the payload looks like:
      0a <len> <blob> [0a <len> <blob>]...
    If multiple blobs exist at a level, we follow only the first blob for chaining,
    but we also return all blobs at each level in the debug structure below.
    """
    chain: List[bytes] = [payload]
    cur = payload
    for _ in range(max_depth):
        blobs = extract_field1_len_delimited(cur)
        if not blobs:
            break
        # follow first blob as next level
        cur = blobs[0]
        chain.append(cur)
    return chain


def find_soc_candidates(dump: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return list of fields with varint values that look like SOC (%).
    """
    cands = []
    for f in dump.get("fields", []):
        if f.get("wire") == 0 and "varint" in f:
            v = f["varint"]
            if 0 <= v <= 100:
                cands.append({"field": f["field"], "value": v})
            # also consider scaled percent
            if 0 <= v <= 1000 and v % 10 == 0:
                cands.append({"field": f["field"], "value": v, "note": "maybe_percent_x10"})
            if 0 <= v <= 10000 and v % 100 == 0:
                cands.append({"field": f["field"], "value": v, "note": "maybe_percent_x100"})
    return cands


MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
SUB_TOPIC = os.environ.get("SUB_TOPIC", "bridge-ecoflow/+/+")
PUB_PREFIX = os.environ.get("PUB_PREFIX", "bridge-ecoflow")


def topic_to_device_leaf(topic: str) -> Tuple[str, str]:
    parts = topic.split("/")
    if len(parts) >= 3:
        return parts[1], parts[2]
    return "unknown", "unknown"


def on_connect(client, userdata, flags, rc):
    client.subscribe(SUB_TOPIC, qos=0)


def on_message(client, userdata, msg):
    ts = int(time.time())
    device, leaf = topic_to_device_leaf(msg.topic)
    if leaf not in ("data", "get_reply", "set_reply"):
        return

    frames = split_length_delimited_frames(msg.payload)

    for frame_index, frame in enumerate(frames):
        # Build a chain of nested field-1 blobs
        chain = unwrap_field1_chain(frame, max_depth=5)

        levels = []
        soc_summary = []
        for depth, blob in enumerate(chain):
            d = protobuf_wire_dump(blob)
            levels.append({"depth": depth, "len": len(blob), "dump": d})
            soc_summary.append({"depth": depth, "candidates": find_soc_candidates(d)})

        out = {
            "ts": ts,
            "src_topic": msg.topic,
            "device": device,
            "leaf": leaf,
            "frame_index": frame_index,
            "frame_len": len(frame),
            "levels": levels,
            "soc_candidates": soc_summary,
        }

        client.publish(
            f"{PUB_PREFIX}/{device}/json/{leaf}/rawN",
            json.dumps(out, separators=(",", ":")),
            qos=0,
            retain=False,
        )


def main():
    c = mqtt.Client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    c.loop_forever()


if __name__ == "__main__":
    main()
