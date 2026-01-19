# Linux Agent

This directory contains the Linux agent for the EcoFlow Power Management system.

## Requirements

- Bash (included with all Linux distributions)
- Mosquitto client tools (`mosquitto_sub`)
- `sudo` privileges for shutdown commands

## Installation

1. Install Mosquitto client:
```bash
# Debian/Ubuntu
sudo apt install mosquitto-clients

# RHEL/CentOS/Fedora
sudo yum install mosquitto

# Arch Linux
sudo pacman -S mosquitto
```

2. Configure environment variables (optional - can use .env file):
```bash
export MQTT_BROKER="mosquitto.local"
export MQTT_PORT="1883"
export AGENT_ID="linux-agent"
```

3. Make the script executable:
```bash
chmod +x shutdown-listener.sh
```

