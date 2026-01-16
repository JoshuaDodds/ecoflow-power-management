#!/usr/bin/env python3
"""
EcoFlow Critical Event Simulator
- Simulates a device going from Normal -> Grid Lost -> Critical Battery -> Shutdown -> Power Restore.
- Used to verify Policy Engine logic without physical hardware draining.
"""

import time
import json
import os
import paho.mqtt.client as mqtt

# --- Configuration ---
# Match these to your actual broker
MQTT_HOST = "mosquitto.hs.mfis.net"
MQTT_PORT = 1883
TOPIC = "bridge-ecoflow/SimulatedDevice/json/state"

# Test Timing (Should be >= POLICY_DEBOUNCE_SEC to trigger)
TEST_DURATION_SEC = 200

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_start()


def publish_state(soc, grid, text):
    payload = {
        "device": "SimulatedDevice",
        "soc": soc,
        "grid_connected": grid,
        "temp_celsius": 35.0,
        "ac_in_watts": 0 if not grid else 500
    }
    client.publish(TOPIC, json.dumps(payload))
    print(f"SENT: SOC={soc}% Grid={grid} | {text}")


print("--- STARTING SIMULATION ---")
print("PREREQ: Add 'SimulatedDevice' to your .env DEVICE_TO_AGENTS_JSON mapping.")
print("Example: DEVICE_TO_AGENTS_JSON='{..., \"SimulatedDevice\": [\"test-agent\"]}'")
print("---------------------------")

try:
    # 1. BASELINE: Everything Normal
    print("\n[PHASE 1] Normal Operation (10s)")
    for i in range(5):
        publish_state(soc=90, grid=True, text="Normal")
        time.sleep(2)

    # 2. GRID LOST: But SOC is high (Should NOT trigger timer)
    print("\n[PHASE 2] Grid Lost, SOC High (10s) - Expect NO Timer")
    for i in range(5):
        publish_state(soc=90, grid=False, text="Grid Lost")
        time.sleep(2)

    # 3. CRITICAL: Grid Lost AND SOC Low (Start Timer)
    print(f"\n[PHASE 3] Critical Start! (SOC 5%) - Timer Should Start")
    print(f"Running for {TEST_DURATION_SEC} seconds (Real-time)...")

    start_time = time.time()
    while (time.time() - start_time) < TEST_DURATION_SEC:
        elapsed = int(time.time() - start_time)
        publish_state(soc=5, grid=False, text=f"CRITICAL (Timer: {elapsed}s)")
        time.sleep(5)

    print("\n[CHECK] Look at Policy Engine logs. You should see a SHUTDOWN command.")

    # 4. RECOVERY: Power returns
    print("\n[PHASE 4] Power Restored! - Expect ABORT command")
    for i in range(5):
        publish_state(soc=5, grid=True, text="Power Restored")
        time.sleep(2)

    print("\n--- SIMULATION COMPLETE ---")

except KeyboardInterrupt:
    print("Stopped.")
    client.disconnect()
