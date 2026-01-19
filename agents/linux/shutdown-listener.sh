#!/bin/bash
# EcoFlow Power Management - Linux Agent
# Listens for shutdown commands via MQTT and executes system shutdown.
# Requires: Mosquitto client (install via: apt install mosquitto-clients)

# ========== LOAD .ENV FILE ==========
# Load environment variables from .env file if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Clear any existing PRE_SHUTDOWN_CMD variables to prevent stale values
for i in {1..9}; do
    unset "PRE_SHUTDOWN_CMD_${i}"
done

if [ -f "$ENV_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Loading configuration from .env file..."
    while IFS='=' read -r key value; do
        # Skip comments, empty lines, and PowerShell-style variables
        if [[ -n "$key" && ! "$key" =~ ^[[:space:]]*# && ! "$key" =~ ^\$ ]]; then
            # Remove leading/trailing whitespace and quotes
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
            export "$key=$value"
        fi
    done < "$ENV_FILE"
fi

# ========== CONFIGURATION ==========
MQTT_BROKER="${MQTT_BROKER:-${MQTT_HOST:-mosquitto.local}}"
MQTT_PORT="${MQTT_PORT:-1883}"
AGENT_ID="${AGENT_ID:-linux-agent}"
MQTT_TOPIC="power-manager/${AGENT_ID}/cmd"

# Pre-shutdown commands (executed in order before shutdown)
PRE_SHUTDOWN_CMDS=()
for i in {1..9}; do
    var_name="PRE_SHUTDOWN_CMD_${i}"
    cmd="${!var_name}"
    if [ -n "$cmd" ]; then
        PRE_SHUTDOWN_CMDS+=("$cmd")
    fi
done

# Shutdown and abort commands (customizable)
SHUTDOWN_CMD="${SHUTDOWN_CMD:-sudo shutdown -h +1}"
ABORT_CMD="${ABORT_CMD:-sudo shutdown -c}"

# ========== LOGGING FUNCTION ==========
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ========== MAIN SCRIPT ==========
log "Starting EcoFlow Linux Agent"
log "Agent ID: ${AGENT_ID}"
log "Broker: ${MQTT_BROKER}:${MQTT_PORT}"
log "Topic: ${MQTT_TOPIC}"

# Check if mosquitto_sub is available
if ! command -v mosquitto_sub &> /dev/null; then
    log "ERROR: mosquitto_sub not found"
    log "Please install Mosquitto client: sudo apt install mosquitto-clients"
    exit 1
fi

log "Listening for commands..."

# Listen indefinitely for MQTT messages
# Use -F to get formatted output with one message per line
mosquitto_sub -h "${MQTT_BROKER}" -p "${MQTT_PORT}" -t "${MQTT_TOPIC}" -F '%p' | while read -r message; do
    log "Received message: ${message}"
    
    # Extract action from JSON using grep/sed (no jq dependency)
    action=$(echo "${message}" | grep -o '"action"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)".*/\1/')
    
    case "${action}" in
        shutdown)
            log "SHUTDOWN command received!"
            
            # Execute pre-shutdown commands
            if [ ${#PRE_SHUTDOWN_CMDS[@]} -gt 0 ]; then
                log "Executing ${#PRE_SHUTDOWN_CMDS[@]} pre-shutdown command(s)..."
                for idx in "${!PRE_SHUTDOWN_CMDS[@]}"; do
                    cmd="${PRE_SHUTDOWN_CMDS[$idx]}"
                    num=$((idx + 1))
                    log "Pre-shutdown ${num}/${#PRE_SHUTDOWN_CMDS[@]}: ${cmd}"
                    
                    if eval "${cmd}" 2>&1 | while IFS= read -r line; do log "  ${line}"; done; then
                        log "Command succeeded"
                    else
                        exit_code=$?
                        log "Command failed with exit code ${exit_code}"
                    fi
                done
            fi
            
            # Execute shutdown command
            log "Initiating system shutdown..."
            log "Command: ${SHUTDOWN_CMD}"
            eval "${SHUTDOWN_CMD}"
            ;;
            
        abort)
            log "ABORT command received!"
            log "Canceling pending shutdown..."
            log "Command: ${ABORT_CMD}"
            
            # Cancel pending shutdown
            eval "${ABORT_CMD}" 2>/dev/null || log "No pending shutdown to cancel"
            ;;
            
        *)
            if [ -n "${action}" ]; then
                log "Unknown action: ${action}"
            fi
            ;;
    esac
done

log "MQTT listener stopped unexpectedly"
