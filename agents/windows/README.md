# Windows Agent

This directory contains the Windows agent for the EcoFlow Power Management system.

## Requirements

- Windows 10/11 or Windows Server
- PowerShell 5.1+ (included with Windows)
- Mosquitto for Windows client tools

## Installation

1. **Download Mosquitto for Windows**:
   - Visit: [https://mosquitto.org/download/](https://mosquitto.org/download/)
   - Download: `mosquitto-X.Y.Z-install-windows-x64.exe`
   - Run the installer (includes `mosquitto_sub.exe` and `mosquitto_pub.exe`)

2. **Configure environment variables** (optional):
   - Open PowerShell as Administrator
   - Set variables:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('MQTT_BROKER', 'mosquitto.local', 'Machine')
   [System.Environment]::SetEnvironmentVariable('AGENT_ID', 'windows-pc', 'Machine')
   ```

## Running the Agent

### Manual Execution
```powershell
# Run as Administrator
.\shutdown-listener.ps1
```

### As a Windows Service (Recommended)

Use **Task Scheduler** to run at startup:

1. Open Task Scheduler
2. Create Task → General tab:
   - Name: `EcoFlow Power Agent`
   - Run whether user is logged on or not
   - Run with highest privileges
   - Configure for: Windows 10

3. Triggers tab:
   - New → Begin the task: At startup

4. Actions tab:
   - New → Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-ExecutionPolicy Bypass -File "C:\path\to\agents\windows\shutdown-listener.ps1"`
   - Start in: `C:\path\to\agents\windows`

5. Conditions tab:
   - Uncheck "Start the task only if the computer is on AC power"

6. Settings tab:
   - If the task fails, restart every: 1 minute
   - Attempt to restart up to: 3 times

## Configuration

Edit the script or set environment variables:

- `MQTT_BROKER`: MQTT broker hostname (default: `mosquitto.local`)
- `MQTT_PORT`: MQTT broker port (default: `1883`)
- `AGENT_ID`: Unique identifier for this agent (default: `windows-agent`)

The agent will subscribe to: `power-manager/{AGENT_ID}/cmd`

## Optional: Hyper-V Integration

If you run Hyper-V virtual machines, uncomment the service stop line in the script to gracefully shut down VMs before system shutdown.
