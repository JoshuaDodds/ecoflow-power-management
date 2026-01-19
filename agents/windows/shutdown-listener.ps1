# EcoFlow Power Management - Windows Agent
# Listens for shutdown commands via MQTT and executes system shutdown.
# Requires: Mosquitto for Windows (mosquitto_sub.exe)
# Download from: https://mosquitto.org/download/

# ========== CONFIGURATION ==========
# Set these environment variables or modify directly:
$MQTT_BROKER = if ($env:MQTT_BROKER) { $env:MQTT_BROKER } else { "mosquitto.local" }
$MQTT_PORT = if ($env:MQTT_PORT) { $env:MQTT_PORT } else { "1883" }
$AGENT_ID = if ($env:AGENT_ID) { $env:AGENT_ID } else { "windows-agent" }
$MQTT_TOPIC = "power-manager/$AGENT_ID/cmd"

# ========== LOGGING FUNCTION ==========
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

# ========== MAIN SCRIPT ==========
Write-Log "Starting EcoFlow Windows Agent"
Write-Log "Agent ID: $AGENT_ID"
Write-Log "Broker: ${MQTT_BROKER}:${MQTT_PORT}"
Write-Log "Topic: $MQTT_TOPIC"
Write-Log "Listening for commands..."

# Check if mosquitto_sub.exe is available
$mosquittoPath = Get-Command mosquitto_sub.exe -ErrorAction SilentlyContinue

if (-not $mosquittoPath) {
    # Check common installation locations
    $commonPaths = @(
        "C:\Program Files\mosquitto\mosquitto_sub.exe",
        "C:\Program Files (x86)\mosquitto\mosquitto_sub.exe",
        "$env:ProgramFiles\mosquitto\mosquitto_sub.exe",
        "$env:ProgramFiles(x86)\mosquitto\mosquitto_sub.exe"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            Write-Log "Found mosquitto_sub.exe at: $path"
            $mosquittoPath = $path
            break
        }
    }
    
    if (-not $mosquittoPath) {
        Write-Log "ERROR: mosquitto_sub.exe not found in PATH or common installation locations"
        Write-Log "Please install Mosquitto for Windows from https://mosquitto.org/download/"
        Write-Log "Or add the Mosquitto installation directory to your PATH environment variable"
        exit 1
    }
} else {
    $mosquittoPath = $mosquittoPath.Source
}

# Listen indefinitely for MQTT messages
& $mosquittoPath -h $MQTT_BROKER -p $MQTT_PORT -t $MQTT_TOPIC | ForEach-Object {
    $message = $_
    Write-Log "Received message: $message"
    
    try {
        # Parse JSON command
        $command = $message | ConvertFrom-Json
        $action = $command.action
        
        switch ($action) {
            "shutdown" {
                Write-Log "SHUTDOWN command received!"
                Write-Log "Initiating system shutdown in 60 seconds..."
                
                # Optional: Stop critical services gracefully before shutdown
                # Uncomment if you run Hyper-V VMs:
                # Write-Log "Stopping Hyper-V Virtual Machine Management service..."
                # Stop-Service "vmms" -Force -ErrorAction SilentlyContinue
                
                # Execute shutdown
                shutdown.exe /s /t 60 /f /c "EcoFlow Critical Battery Shutdown"
            }
            
            "abort" {
                Write-Log "ABORT command received!"
                Write-Log "Canceling pending shutdown..."
                
                # Cancel any pending shutdown
                shutdown.exe /a
            }
            
            default {
                Write-Log "Unknown action: $action"
            }
        }
    }
    catch {
        Write-Log "Error processing message: $_"
    }
}

Write-Log "MQTT listener stopped unexpectedly"
