# EcoFlow Power Management - Windows Agent
# Listens for shutdown commands via MQTT and executes system shutdown.
# Requires: Mosquitto for Windows (mosquitto_sub.exe)
# Download from: https://mosquitto.org/download/

# ========== LOAD .ENV FILE ==========
# Load environment variables from .env file if it exists
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "Loading configuration from .env file..."
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        # Skip comments and empty lines
        if ($line -and -not $line.StartsWith('#') -and -not $line.StartsWith('$')) {
            if ($line -match '^([^=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                # Remove quotes if present
                $value = $value -replace '^["'']|["'']$', ''
                [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
            }
        }
    }
}

# ========== CONFIGURATION ==========
# Set these environment variables or modify directly:
$MQTT_BROKER = if ($env:MQTT_BROKER) { $env:MQTT_BROKER } else { if ($env:MQTT_HOST) { $env:MQTT_HOST } else { "mosquitto.local" } }
$MQTT_PORT = if ($env:MQTT_PORT) { $env:MQTT_PORT } else { "1883" }
$AGENT_ID = if ($env:AGENT_ID) { $env:AGENT_ID } else { "windows-agent" }
$MQTT_TOPIC = "power-manager/$AGENT_ID/cmd"

# Pre-shutdown commands (executed in order before shutdown)
$PRE_SHUTDOWN_CMDS = @()
for ($i = 1; $i -le 9; $i++) {
    $cmd = [System.Environment]::GetEnvironmentVariable("PRE_SHUTDOWN_CMD_$i")
    if ($cmd) {
        $PRE_SHUTDOWN_CMDS += $cmd
    }
}

# Shutdown and abort commands (customizable)
$SHUTDOWN_CMD = if ($env:SHUTDOWN_CMD) { $env:SHUTDOWN_CMD } else { "shutdown.exe /s /t 60 /f /c 'EcoFlow Critical Battery Shutdown'" }
$ABORT_CMD = if ($env:ABORT_CMD) { $env:ABORT_CMD } else { "shutdown.exe /a" }

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
                
                # Execute pre-shutdown commands
                if ($PRE_SHUTDOWN_CMDS.Count -gt 0) {
                    Write-Log "Executing $($PRE_SHUTDOWN_CMDS.Count) pre-shutdown command(s)..."
                    for ($i = 0; $i -lt $PRE_SHUTDOWN_CMDS.Count; $i++) {
                        $cmd = $PRE_SHUTDOWN_CMDS[$i]
                        $idx = $i + 1
                        Write-Log "Pre-shutdown $idx/$($PRE_SHUTDOWN_CMDS.Count): $cmd"
                        
                        try {
                            $result = Invoke-Expression $cmd 2>&1
                            if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
                                Write-Log "Command succeeded"
                                if ($result) {
                                    Write-Log "Output: $result"
                                }
                            } else {
                                Write-Log "Command failed with exit code $LASTEXITCODE"
                                if ($result) {
                                    Write-Log "Error: $result"
                                }
                            }
                        }
                        catch {
                            Write-Log "Command failed: $_"
                        }
                    }
                }
                
                # Execute shutdown command
                Write-Log "Initiating system shutdown..."
                Write-Log "Command: $SHUTDOWN_CMD"
                Invoke-Expression $SHUTDOWN_CMD
            }
            
            "abort" {
                Write-Log "ABORT command received!"
                Write-Log "Canceling pending shutdown..."
                Write-Log "Command: $ABORT_CMD"
                
                # Cancel any pending shutdown
                Invoke-Expression $ABORT_CMD
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
