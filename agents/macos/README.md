# macOS Agent

This directory contains the macOS agent for the EcoFlow Power Management system.

## Requirements

- macOS 10.14+
- Mosquitto client tools
- `sudo` privileges for shutdown commands

## Installation

1. **Install Mosquitto client** using Homebrew:
```bash
brew install mosquitto
```

2. **Configure environment variables** (optional):
```bash
# Add to ~/.zshrc or ~/.bash_profile
export MQTT_BROKER="mosquitto.local"
export MQTT_PORT="1883"
export AGENT_ID="macos-agent"
```

3. **Make the script executable**:
```bash
chmod +x shutdown-listener.sh
```

## Running the Agent

### Manual Execution
```bash
sudo ./shutdown-listener.sh
```

### As a LaunchDaemon (Recommended)

Create `/Library/LaunchDaemons/com.ecoflow.agent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ecoflow.agent</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/agents/macos/shutdown-listener.sh</string>
    </array>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>MQTT_BROKER</key>
        <string>mosquitto.local</string>
        <key>AGENT_ID</key>
        <string>macos-agent</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>/var/log/ecoflow-agent.log</string>
    
    <key>StandardErrorPath</key>
    <string>/var/log/ecoflow-agent.error.log</string>
</dict>
</plist>
```

Load and start the daemon:
```bash
sudo cp com.ecoflow.agent.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.ecoflow.agent.plist
sudo chmod 644 /Library/LaunchDaemons/com.ecoflow.agent.plist
sudo launchctl load /Library/LaunchDaemons/com.ecoflow.agent.plist
```

Check status:
```bash
sudo launchctl list | grep ecoflow
tail -f /var/log/ecoflow-agent.log
```

## Configuration

Set these environment variables before running:

- `MQTT_BROKER`: MQTT broker hostname (default: `mosquitto.local`)
- `MQTT_PORT`: MQTT broker port (default: `1883`)
- `AGENT_ID`: Unique identifier for this agent (default: `macos-agent`)

The agent will subscribe to: `power-manager/{AGENT_ID}/cmd`

## Troubleshooting

If the shutdown command requires a password, configure passwordless sudo for shutdown:

```bash
sudo visudo
# Add this line:
%admin ALL=(ALL) NOPASSWD: /sbin/shutdown
```
