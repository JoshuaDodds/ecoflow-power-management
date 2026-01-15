#!/usr/bin/env python3
"""
EcoFlow Cloud Bridge (Direct MQTT Tunnel)

- PURPOSE: Bridges EcoFlow Cloud MQTT <-> Local MQTT.
- AUTH: Uses Official API (GET /certification) to get cloud credentials.
- WAKEUP: Sends 'Cmd 0' (Quota) directly to Cloud MQTT (Bypassing broken HTTP).
"""

import os
import sys
import time
import json
import random
import logging
import requests
import ssl
import hmac
import hashlib
import threading
import paho.mqtt.client as mqtt

# --- Import Utils ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import env_loader

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ECOFLOW_API_URL = "https://api-e.ecoflow.com"
LOCAL_MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto.hs.mfis.net")
LOCAL_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Protobuf "Android" Suffix for wakeup packets
ANDROID_SUFFIX = bytes.fromhex("ba0107616e64726f6964")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("ecoflow_cloud")

ACCESS_KEY = os.getenv("ECOFLOW_ACCESS_KEY", "").strip()
SECRET_KEY = os.getenv("ECOFLOW_SECRET_KEY", "").strip()
DEVICE_LIST_STR = os.getenv("ECOFLOW_DEVICE_LIST", "")


# ==============================================================================
# 1. AUTHENTICATION (Get Cloud MQTT Creds)
# ==============================================================================
class EcoFlowSigner:
    @staticmethod
    def get_headers(access_key, secret_key):
        """Sign request for GET /certification"""
        nonce = str(random.randint(10000, 1000000))
        timestamp = str(int(time.time() * 1000))

        # MyMapUtil logic: sort, then append auth
        sign_str = f"accessKey={access_key}&nonce={nonce}&timestamp={timestamp}"

        signature = hmac.new(
            secret_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            "Content-Type": "application/json;charset=UTF-8",
            "accessKey": access_key,
            "nonce": nonce,
            "timestamp": timestamp,
            "sign": signature
        }


def get_cloud_creds():
    """Fetches MQTT credentials from EcoFlow API."""
    try:
        url = f"{ECOFLOW_API_URL}/iot-open/sign/certification"
        headers = EcoFlowSigner.get_headers(ACCESS_KEY, SECRET_KEY)

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "0":
                logger.info("✅ Acquired EcoFlow Cloud MQTT Credentials.")
                return data.get("data")
            else:
                logger.error(f"API Error: {data.get('message')}")
        else:
            logger.error(f"HTTP Error: {resp.status_code}")
    except Exception as e:
        logger.error(f"Auth Exception: {e}")
    return None


# ==============================================================================
# 2. PACKET FORGER (Protobuf)
# ==============================================================================
def encode_varint(val: int) -> bytes:
    out = []
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            break
    return bytes(out)


def forge_packet(cmd_id: int) -> bytes:
    """Creates the raw bytes to wake the device."""
    seq = int(time.time())
    # Header: Src=32, Dst=32, Seq=Time, Type=Android
    header = b'\x10\x20\x18\x20\x70' + encode_varint(seq) + ANDROID_SUFFIX
    # Payload: CmdId
    payload = b'\x08' + encode_varint(cmd_id)
    # Wrap
    return b'\x0a' + encode_varint(len(header)) + header + b'\x12' + encode_varint(len(payload)) + payload


# ==============================================================================
# 3. THE BRIDGE
# ==============================================================================
class CloudBridge:
    def __init__(self, creds):
        self.creds = creds
        self.cloud_client = None
        self.local_client = None
        self.devices = [s.strip() for s in DEVICE_LIST_STR.split(",") if s.strip()]

    def start(self):
        # 1. Setup Local MQTT (To pump data into your system)
        self.local_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ecoflow-bridge-local")
        try:
            self.local_client.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, 60)
            self.local_client.loop_start()
            logger.info(f"Connected to Local MQTT: {LOCAL_MQTT_HOST}")
        except Exception as e:
            logger.error(f"Local MQTT Failed: {e}")

        # 2. Setup Cloud MQTT
        c_user = self.creds['certificateAccount']
        c_pass = self.creds['certificatePassword']
        c_host = self.creds['url']
        c_port = int(self.creds['port'])

        self.cloud_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                        client_id=f"android-{random.randint(1000, 9999)}")
        self.cloud_client.username_pw_set(c_user, c_pass)
        self.cloud_client.tls_set(cert_reqs=ssl.CERT_NONE)
        self.cloud_client.tls_insecure_set(True)

        self.cloud_client.on_connect = self.on_cloud_connect
        self.cloud_client.on_message = self.on_cloud_message

        logger.info(f"Connecting to Cloud MQTT: {c_host}:{c_port}...")
        self.cloud_client.connect(c_host, c_port, 60)

        # Start Threads
        threading.Thread(target=self.cloud_client.loop_forever, daemon=True).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()

        # Keep main thread alive
        while True: time.sleep(1)

    def on_cloud_connect(self, client, userdata, flags, rc, props=None):
        logger.info("✅ Connected to EcoFlow Cloud!")
        for sn in self.devices:
            # Subscribe to device data topics
            topic = f"/app/device/property/{sn}"
            client.subscribe(topic)
            logger.info(f"Subscribed: {topic}")

    def on_cloud_message(self, client, userdata, msg):
        # Forward everything to Local MQTT
        if self.local_client:
            # Remap topic to local format: bridge-ecoflow/{sn}/data
            # Incoming: /app/device/property/{sn}
            try:
                parts = msg.topic.split('/')
                sn = parts[-1]
                local_topic = f"bridge-ecoflow/{sn}/data"
                self.local_client.publish(local_topic, msg.payload)
                # logger.info(f"Forwarded data for {sn}") # Uncomment for verbose debug
            except:
                pass

    def heartbeat_loop(self):
        """Sends the wakeup packets into the Cloud Tunnel."""
        while True:
            time.sleep(5)  # Wait for connection
            if not self.cloud_client.is_connected(): continue

            logger.info("--- Sending Cloud Heartbeats ---")
            pkt = forge_packet(0)  # Cmd 0 = Get All

            for sn in self.devices:
                # Topic: /app/{user_id}/{sn}/quota (Standard for App)
                # Note: We use the credential account as the user ID context
                topic = f"/app/{self.creds['certificateAccount']}/{sn}/quota"
                self.cloud_client.publish(topic, pkt)
                logger.info(f"[{sn}] Sent Wakeup -> Cloud")

            time.sleep(300)


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    if not ACCESS_KEY or not SECRET_KEY:
        logger.error("Missing Developer API credentials. Sign up and configure them here: https://developer-eu.ecoflow.com/us")
        return

    # 1. Get Certs
    creds = get_cloud_creds()
    if not creds:
        logger.error("Could not get Cloud Credentials. Exiting.")
        return

    # 2. Start Bridge
    bridge = CloudBridge(creds)
    bridge.start()


if __name__ == "__main__":
    main()
