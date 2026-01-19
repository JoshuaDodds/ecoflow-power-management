#!/bin/bash
# EcoFlow Power Management - macOS Agent
# Listens for shutdown commands via MQTT and executes system shutdown.
# Requires: Mosquitto client (install via: brew install mosquitto)

# ========== CONFIGURATION ==========
MQTT_BROKER="${MQTT_BROKER:-mosquitto.local}"
MQTT_PORT="${MQTT_PORT:-1883}"
AGENT_ID="${AGENT_ID:-macos-agent}"
MQTT_TOPIC="power-manager/${AGENT_ID}/cmd"

# ========== LOGGING FUNCTION ==========
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ========== MAIN SCRIPT ==========
log "Starting EcoFlow macOS Agent"
log "Agent ID: ${AGENT_ID}"
log "Broker: ${MQTT_BROKER}:${MQTT_PORT}"
log "Topic: ${MQTT_TOPIC}"

# Check if mosquitto_sub is available
if ! command -v mosquitto_sub &> /dev/null; then
    log "ERROR: mosquitto_sub not found"
    log "Please install Mosquitto client: brew install mosquitto"
    exit 1
fi

log "Listening for commands..."

# Listen indefinitely for MQTT messages
mosquitto_sub -h "${MQTT_BROKER}" -p "${MQTT_PORT}" -t "${MQTT_TOPIC}" | while read -r message; do
    log "Received message: ${message}"
    
    # Extract action from JSON using grep/sed (no jq dependency)
    action=$(echo "${message}" | grep -o '"action"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)".*/\1/')
    
    case "${action}" in
        shutdown)
            log "SHUTDOWN command received!"
            log "Initiating system shutdown in 60 seconds..."
            
            # macOS shutdown command (requires sudo)
            # -h: halt
            # +1: delay 1 minute
            sudo shutdown -h +1 "EcoFlow Critical Battery Shutdown"
            ;;
            
        abort)
            log "ABORT command received!"
            log "Canceling pending shutdown..."
            
            # Cancel pending shutdown on macOS
            sudo killall shutdown 2>/dev/null || log "No pending shutdown to cancel"
            ;;
            
        *)
            log "Unknown action: ${action}"
            ;;
    esac
done

log "MQTT listener stopped unexpectedly"
