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

## Running as a Systemd Service (Recommended)

For production use, run the agent as a systemd service for automatic startup and restart on failure.

### Quick Setup

1. **Edit the service file** with your configuration:
```bash
# Copy the service file template
sudo cp ecoflow-agent.service /etc/systemd/system/

# Edit the service file
sudo nano /etc/systemd/system/ecoflow-agent.service
```

2. **Customize the environment variables** in the service file:
```ini
Environment="MQTT_HOST=your-mqtt-broker"
Environment="AGENT_ID=your-agent-id"
```

Or use a `.env` file (recommended):
```bash
# Create .env file in the agent directory
cp .env-example .env
nano .env

# Update the WorkingDirectory in the service file to point to where you installed
# The script will automatically load the .env file from its directory
```

3. **Update the script path** in the service file if you installed elsewhere:
```ini
WorkingDirectory=/your/install/path/agents/linux
ExecStart=/bin/bash /your/install/path/agents/linux/shutdown-listener.sh
```

4. **Enable and start the service**:
```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable ecoflow-agent

# Start the service now
sudo systemctl start ecoflow-agent

# Check the status
sudo systemctl status ecoflow-agent
```

### Service Management Commands

```bash
# View logs
sudo journalctl -u ecoflow-agent -f

# Restart the service
sudo systemctl restart ecoflow-agent

# Stop the service
sudo systemctl stop ecoflow-agent

# Disable auto-start on boot
sudo systemctl disable ecoflow-agent
```

### Service Features

The provided systemd service includes:
- ✅ **Auto-restart** on failure (10 second delay)
- ✅ **Start on boot** after network is available
- ✅ **Logging** to systemd journal
- ✅ **Environment variables** for configuration
- ✅ **Rate limiting** to prevent restart loops

---

## Manual Execution (For Testing)

For testing or one-time runs:
```bash
sudo ./shutdown-listener.sh
```

