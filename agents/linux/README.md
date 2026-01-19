# Linux Agent

This directory contains the Linux agent for the EcoFlow Power Management system.

## Requirements

- Python 3.7+
- `paho-mqtt` library
- `sudo` privileges for shutdown commands

## Installation

1. Install dependencies:
```bash
pip install paho-mqtt
```

2. Configure environment variables (optional):
```bash
export MQTT_BROKER="mosquitto.local"
export MQTT_PORT="1883"
export AGENT_ID="linux-agent"
```

3. Make the script executable:
```bash
chmod +x shutdown-listener.py
```

