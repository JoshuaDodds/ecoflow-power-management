import os
import json
import time
import logging
import uuid
import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PolicyEngine")

class PolicyEngine:
    def __init__(self):
        # Load configuration from environment variables
        self.mqtt_host = os.environ.get("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))

        try:
            self.policy_soc_min = int(os.environ["POLICY_SOC_MIN"])
            self.policy_debounce_sec = int(os.environ["POLICY_DEBOUNCE_SEC"])
            self.policy_cooldown_sec = int(os.environ["POLICY_COOLDOWN_SEC"])
            self.device_to_agents = json.loads(os.environ["DEVICE_TO_AGENTS_JSON"])
        except (KeyError, ValueError) as e:
            logger.error(f"Missing or invalid configuration: {e}")
            raise

        # State tracking
        # {device_id: {"start_time": float, "last_trigger": float}}
        self.device_states = {}

        # MQTT Client setup
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def run(self):
        logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}...")
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"Failed to connect or run MQTT client: {e}")
            raise

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            topic = "bridge-ecoflow/+/json/state"
            client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            device = payload.get("device")
            soc_min = payload.get("soc_min")

            if device is not None and soc_min is not None:
                self.evaluate_policy(device, soc_min)
            else:
                logger.debug(f"Ignored message with missing fields: {payload}")

        except json.JSONDecodeError:
            logger.warning(f"Failed to decode JSON payload: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def evaluate_policy(self, device, soc_min):
        now = time.time()

        # Initialize state for new device if needed
        if device not in self.device_states:
            self.device_states[device] = {
                "start_time": None,      # When soc_min first dropped below threshold
                "last_trigger": 0.0      # When the last shutdown command was sent
            }

        state = self.device_states[device]

        if soc_min <= self.policy_soc_min:
            # Condition met: soc_min is low
            if state["start_time"] is None:
                # First time dropping below threshold
                state["start_time"] = now
                logger.info(f"Device {device} SoC ({soc_min}) below threshold ({self.policy_soc_min}). Starting debounce timer.")
            else:
                # Already below threshold, check debounce
                duration = now - state["start_time"]
                if duration >= self.policy_debounce_sec:
                    # Debounce period passed, check cooldown
                    time_since_last_trigger = now - state["last_trigger"]
                    if time_since_last_trigger >= self.policy_cooldown_sec:
                        # Cooldown passed, trigger shutdown
                        logger.info(f"Device {device} SoC ({soc_min}) low for {duration:.1f}s. Triggering shutdown.")
                        self.trigger_shutdown(device, soc_min)
                        state["last_trigger"] = now
                    else:
                        logger.debug(f"Device {device} SoC low, but in cooldown ({time_since_last_trigger:.1f}s < {self.policy_cooldown_sec}s).")
        else:
            # Condition not met: soc_min is healthy
            if state["start_time"] is not None:
                logger.info(f"Device {device} SoC ({soc_min}) recovered above threshold. Resetting debounce.")
                state["start_time"] = None

    def trigger_shutdown(self, device, soc_min):
        agents = self.device_to_agents.get(device, [])
        if not agents:
            logger.warning(f"No agents configured for device {device}")
            return

        command_id = str(uuid.uuid4())
        payload = {
            "id": command_id,
            "action": "shutdown",
            "delay_sec": 60,
            "reason": f"EcoFlow {device} soc_min <= {self.policy_soc_min}",
            "ttl_sec": 300
        }

        for agent_id in agents:
            topic = f"power-manager/{agent_id}/cmd"
            payload_json = json.dumps(payload)
            logger.info(f"Publishing shutdown command to {topic}: {payload_json}")
            self.client.publish(topic, payload_json)

if __name__ == "__main__":
    try:
        engine = PolicyEngine()
        engine.run()
    except KeyboardInterrupt:
        logger.info("Stopping Policy Engine...")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        exit(1)
