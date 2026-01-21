#!/usr/bin/env python3
"""
EcoFlow Policy Engine (Orchestrator Compatible)
- Role: Decision Maker.
- Logic: TRIGGER if (Grid=False AND SOC < Limit) holds TRUE for > Debounce.
- Safety: If condition clears and a shutdown was pending, send ABORT.
"""

import os
import sys
import json
import time
import logging
import uuid
import threading
import paho.mqtt.client as mqtt

# --- Import Utils ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import env_loader
from utils.notifier import Notifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("policy_engine")


class PolicyEngine:
    def __init__(self):
        # Load configuration from environment variables
        self.mqtt_host = os.environ.get("MQTT_HOST", "mosquitto.hs.mfis.net")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        self.mqtt_base = os.environ.get("ECOFLOW_BASE", "bridge-ecoflow")

        # Initialize critical attributes with defaults (ensures they always exist)
        self.policy_soc_min = 10
        self.policy_debounce_sec = 180
        self.policy_cooldown_sec = 300
        self.max_data_gap_sec = 60
        self.agent_shutdown_delay = 60
        self.device_to_agents = {}
        
        # Initialize notifier
        self.notifier = Notifier()
        
        # Track SOC levels for 2% increment alerts
        self.last_soc_alert = {}  # {device: last_alerted_soc}

        try:
            self.policy_soc_min = int(os.environ.get("POLICY_SOC_MIN", "10"))
            self.policy_debounce_sec = int(os.environ.get("POLICY_DEBOUNCE_SEC", "180"))
            self.policy_cooldown_sec = int(os.environ.get("POLICY_COOLDOWN_SEC", "300"))

            # JSON Mapping: {"Meterkast": ["agent1"], "Study": ["agent2"]}
            raw_agents = os.environ.get("DEVICE_TO_AGENTS_JSON", "{}")
            if raw_agents.strip():  # Only parse if not empty
                self.device_to_agents = json.loads(raw_agents)
            else:
                logger.warning("DEVICE_TO_AGENTS_JSON is empty - no agents will be managed")

            logger.info(
                f"Policy Active: Shutdown if SOC < {self.policy_soc_min}% AND Grid=Lost for > {self.policy_debounce_sec}s")
            logger.info(f"Managed Agents: {self.device_to_agents}")

        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Configuration Error: {e}")
            logger.warning("Using default configuration values")

        # State tracking
        self.device_states = {}

        # MQTT Client setup
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ecoflow-policy-engine")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Track data staleness notifications
        self.staleness_notified = {}  # {device: timestamp_of_last_notification}

    def run(self):
        logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}...")
        try:
            # Start staleness monitoring thread
            staleness_thread = threading.Thread(target=self.monitor_staleness, daemon=True)
            staleness_thread.start()
            
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"Failed to connect or run MQTT client: {e}")
            time.sleep(5)
    
    def monitor_staleness(self):
        """Background thread to monitor data staleness"""
        STALE_THRESHOLD = 300  # 5 minutes in seconds
        CHECK_INTERVAL = 60    # Check every minute
        NOTIFICATION_COOLDOWN = 3600  # Don't re-notify for 1 hour
        
        while True:
            try:
                time.sleep(CHECK_INTERVAL)
                now = time.time()
                
                for device, state in self.device_states.items():
                    last_msg_ts = state.get("last_msg_ts", 0)
                    time_since_msg = now - last_msg_ts
                    
                    # Check if data is stale
                    if time_since_msg > STALE_THRESHOLD:
                        # Check if we've already notified recently
                        last_notified = self.staleness_notified.get(device, 0)
                        if now - last_notified > NOTIFICATION_COOLDOWN:
                            minutes = int(time_since_msg / 60)
                            self.notifier.data_stale(device, minutes)
                            self.staleness_notified[device] = now
                            logger.warning(f"[{device}] Data stale: no updates for {minutes} minutes")
                    else:
                        # Data is fresh, reset notification flag
                        if device in self.staleness_notified:
                            del self.staleness_notified[device]
                            
            except Exception as e:
                logger.error(f"Staleness monitoring error: {e}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            topic = f"{self.mqtt_base}/+/json/state"
            client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            device = payload.get("device")
            soc = payload.get("soc")
            grid_connected = payload.get("grid_connected")

            if device and soc is not None and grid_connected is not None:
                self.evaluate_policy(device, soc, grid_connected)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def evaluate_policy(self, device, soc, grid_connected):
        now = time.time()

        if device not in self.device_states:
            self.device_states[device] = {
                "start_time": None,
                "last_msg_ts": now,
                "last_trigger": 0.0,
                "grid_lost_since": None  # Track when grid was lost for notifications
            }

        state = self.device_states[device]

        # Gap Check
        time_since_msg = now - state["last_msg_ts"]
        state["last_msg_ts"] = now

        if time_since_msg > self.max_data_gap_sec:
            if state["start_time"] is not None:
                logger.warning(f"[{device}] DATA GAP DETECTED. Resetting safety timer.")
                state["start_time"] = None
            return

        # Critical Check
        danger_condition = (not grid_connected) and (soc <= self.policy_soc_min)
        grid_lost = not grid_connected
        
        # Notify on grid loss (once per event)
        if grid_lost and state.get("grid_lost_since") is None:
            state["grid_lost_since"] = now
            self.notifier.grid_lost(device)
            logger.info(f"[{device}] Grid power lost - notification sent")
        
        # Notify on grid restoration
        if not grid_lost and state.get("grid_lost_since") is not None:
            self.notifier.grid_restored(device)
            logger.info(f"[{device}] Grid power restored - notification sent")
            state["grid_lost_since"] = None
        
        # SOC warnings (every 2% drop when near threshold)
        if soc < self.policy_soc_min + 10:  # Start warnings 10% above threshold
            last_alert = self.last_soc_alert.get(device, 100)
            if soc <= last_alert - 2:  # 2% drop
                self.notifier.soc_warning(device, soc, self.policy_soc_min)
                self.last_soc_alert[device] = soc
                logger.info(f"[{device}] SOC warning sent: {soc}%")

        if danger_condition:
            # --- DANGER ---
            if state["start_time"] is None:
                state["start_time"] = now
                logger.warning(
                    f"[{device}] TIMER START: Grid Lost & SoC {soc}%. Waiting {self.policy_debounce_sec}s...")
            else:
                duration = now - state["start_time"]
                if duration > self.policy_debounce_sec:
                    time_since_last_trigger = now - state["last_trigger"]

                    if time_since_last_trigger >= self.policy_cooldown_sec:
                        logger.error(f"[{device}] SHUTDOWN TRIGGERED. Sending Kill Command.")
                        agents = self.device_to_agents.get(device, [])
                        self.send_command(device, "shutdown", f"Critical: Grid Lost & SoC {soc}%")
                        self.notifier.shutdown_sent(device, agents)
                        state["last_trigger"] = now

        else:
            # --- SAFE ---
            if state["start_time"] is not None:
                duration = time.time() - state["start_time"]
                logger.info(f"[{device}] ABORT TIMER: Condition cleared after {duration:.1f}s.")
                state["start_time"] = None

            # ABORT LOGIC
            time_since_trigger = now - state["last_trigger"]
            if time_since_trigger < (self.agent_shutdown_delay + 60) and state["last_trigger"] > 0:
                logger.info(f"[{device}] RECOVERY DETECTED: Sending ABORT to cancel pending shutdowns.")
                self.send_command(device, "abort", "Power Restored / Battery Safe")
                state["last_trigger"] = 0.0

    def send_command(self, device, action, reason):
        agents = self.device_to_agents.get(device, [])
        if not agents:
            return

        command_id = str(uuid.uuid4())
        payload = {
            "id": command_id,
            "action": action,  # "shutdown" or "abort"
            "delay_sec": self.agent_shutdown_delay,
            "reason": reason,
            "ttl_sec": 300
        }

        for agent_id in agents:
            topic = f"power-manager/{agent_id}/cmd"
            payload_json = json.dumps(payload)
            logger.info(f"Publishing {action.upper()} -> {topic}")
            self.client.publish(topic, payload_json, qos=2)


# --- Entry Point for Orchestrator ---
def main():
    try:
        engine = PolicyEngine()
        engine.run()
    except KeyboardInterrupt:
        logger.info("Stopping Policy Engine...")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
