#!/usr/bin/env python3
"""
EcoFlow Cloud MQTT protobuf -> JSON metrics bridge (schema-less, hardened)

- Subscribes to:
    bridge-ecoflow/+/data
    bridge-ecoflow/+/get_reply
    bridge-ecoflow/+/set_reply

- Decodes nested protobuf without .proto files
- Extracts SoC from field #6 (varint)
- Supports multi-battery devices
- Filters invalid SoC values (default 0–100)
- Publishes:
    bridge-ecoflow/<DEVICE>/json/state
    bridge-ecoflow/<DEVICE>/json/state/modules
"""

import json
import os
import time
from typing import Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt


# =============================
# Protobuf wire helpers
# =============================

def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
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
        if shift > 63:
            raise ValueError("varint too long")


def _split_framed_payload(payload: bytes) -> List[bytes]:
    frames = []
    i = 0
    try:
        while i < len(payload):
            ln, j = _read_varint(payload, i)
            i = j
            if ln < 0 or i + ln > len(payload):
                raise ValueError
            frames.append(payload[i:i + ln])
            i += ln
        return frames if frames else [payload]
    except Exception:
        return [payload]


def _unwrap_field1_once(msg: bytes) -> Optional[bytes]:
    i = 0
    try:
        while i < len(msg):
            tag, i = _read_varint(msg, i)
            field = tag >> 3
            wtype = tag & 0x7

            if wtype == 0:
                _, i = _read_varint(msg, i)
            elif wtype == 1:
                i += 8
            elif wtype == 2:
                ln, i = _read_varint(msg, i)
                if i + ln > len(msg):
                    return None
                val = msg[i:i + ln]
                i += ln
                if field == 1:
                    return val
            elif wtype == 5:
                i += 4
            else:
                return None
        return None
    except Exception:
        return None


def unwrap_field1(msg: bytes, depth: int) -> Optional[bytes]:
    cur = msg
    for _ in range(depth):
        cur = _unwrap_field1_once(cur)
        if cur is None:
            return None
    return cur


def _extract_varints_for_field(msg: bytes, field_id: int) -> List[int]:
    out = []
    i = 0
    while i < len(msg):
        try:
            tag, i = _read_varint(msg, i)
            field = tag >> 3
            wtype = tag & 0x7

            if wtype == 0:
                v, i = _read_varint(msg, i)
                if field == field_id:
                    out.append(v)
            elif wtype == 1:
                i += 8
            elif wtype == 2:
                ln, i = _read_varint(msg, i)
                i += ln
            elif wtype == 5:
                i += 4
            else:
                break
        except Exception:
            break
    return out


# =============================
# Aggregation
# =============================

def _now_ms() -> int:
    return int(time.time() * 1000)


class Aggregator:
    def __init__(self, window_sec: float):
        self.window_sec = window_sec
        self.buf: Dict[str, dict] = {}

    def add(self, device: str, src: str, leaf: str, socs: List[int]):
        if device not in self.buf:
            self.buf[device] = {"t0": time.time(), "items": []}
        self.buf[device]["items"].append((_now_ms(), src, leaf, socs))

    def pop_ready(self):
        out = []
        now = time.time()
        for dev in list(self.buf):
            if now - self.buf[dev]["t0"] < self.window_sec:
                continue
            items = self.buf[dev]["items"]
            if not items:
                del self.buf[dev]
                continue

            ts, src, leaf, _ = items[-1]
            merged = []
            for _, _, _, socs in items:
                for v in socs:
                    if not merged or merged[-1] != v:
                        merged.append(v)

            out.append((dev, ts, src, leaf, merged))
            del self.buf[dev]
        return out


# =============================
# MQTT
# =============================

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "ecoflow-soc-bridge")
ECOFLOW_BASE = os.getenv("ECOFLOW_BASE", "bridge-ecoflow")
AGG_WINDOW_SEC = float(os.getenv("AGG_WINDOW_SEC", "1.0"))

SOC_MIN = int(os.getenv("SOC_MIN", "0"))
SOC_MAX = int(os.getenv("SOC_MAX", "100"))

agg = Aggregator(AGG_WINDOW_SEC)


def _topic_parts(topic: str):
    p = topic.split("/")
    if len(p) != 3 or p[0] != ECOFLOW_BASE:
        return None
    return p[1], p[2]


def on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe(f"{ECOFLOW_BASE}/+/data")
    client.subscribe(f"{ECOFLOW_BASE}/+/get_reply")
    client.subscribe(f"{ECOFLOW_BASE}/+/set_reply")


def on_message(client, userdata, msg):
    tp = _topic_parts(msg.topic)
    if not tp:
        return
    device, leaf = tp

    frames = _split_framed_payload(msg.payload)
    extracted: List[int] = []

    for frame in frames:
        state = unwrap_field1(frame, depth=2)
        if not state:
            continue

        vals = _extract_varints_for_field(state, field_id=6)

        # HARD FILTER: only plausible SoC percentages
        vals = [v for v in vals if SOC_MIN <= v <= SOC_MAX]

        extracted.extend(vals)

    if extracted:
        agg.add(device, msg.topic, leaf, extracted)

    for dev, ts, src, leaf2, socs in agg.pop_ready():
        soc = round(sum(socs) / len(socs), 2)
        soc_min = min(socs)

        base = f"{ECOFLOW_BASE}/{dev}/json/state"

        client.publish(
            base,
            json.dumps({
                "ts": ts,
                "device": dev,
                "src_topic": src,
                "leaf": leaf2,
                "soc": soc,
                "soc_min": soc_min,
                "soc_modules": socs,
            }, separators=(",", ":"))
        )

        client.publish(
            f"{base}/modules",
            json.dumps({
                "ts": ts,
                "device": dev,
                "src_topic": src,
                "leaf": leaf2,
                "soc_modules": [
                    {"module": f"idx{i}", "soc": v}
                    for i, v in enumerate(socs)
                ],
            }, separators=(",", ":"))
        )


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=MQTT_CLIENT_ID)

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
