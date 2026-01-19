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

## Running the Agent

### Manual Execution
```bash
sudo python3 shutdown-listener.py
```

### As a systemd Service (Recommended)

Create `/etc/systemd/system/ecoflow-agent.service`:

```ini
[Unit]
Description=EcoFlow Power Management Agent
After=network.target

[Service]
Type=simple
User=root
Environment="MQTT_BROKER=mosquitto.local"
Environment="AGENT_ID=linux-server"
ExecStart=/usr/bin/python3 /path/to/agents/linux/shutdown-listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ecoflow-agent
sudo systemctl start ecoflow-agent
sudo systemctl status ecoflow-agent
```

## Configuration

Set these environment variables before running:

- `MQTT_BROKER`: MQTT broker hostname (default: `mosquitto.local`)
- `MQTT_PORT`: MQTT broker port (default: `1883`)
- `AGENT_ID`: Unique identifier for this agent (default: `linux-agent`)

The agent will subscribe to: `power-manager/{AGENT_ID}/cmd`
