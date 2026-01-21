# Setup Guide

Complete step-by-step guide to deploy EcoFlow Power Management from scratch.

**Target Audience:** Users with basic CLI experience (can install packages, edit config files, run commands)

---

## Prerequisites

Before starting, ensure you have:
- [ ] **EcoFlow Device** (tested with River 3 Plus, likely works with others)
- [ ] **EcoFlow Account** (from mobile app)
- [ ] **Developer API Access** (see instructions below)
- [ ] **Linux/macOS/Windows** machine to run the orchestrator
- [ ] **Network access** between orchestrator and agents

---

## Step 1: Install Local MQTT Broker

The system requires a local MQTT broker for internal communication between services and agents.

### Option A: Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### Option B: macOS
```bash
brew install mosquitto
brew services start mosquitto
```

### Option C: Windows
1. Download Mosquitto from: https://mosquitto.org/download/
2. Install using the Windows installer
3. Start the Mosquitto service from Services panel

### Option D: Docker
```bash
docker run -d --name mosquitto \
  -p 1883:1883 \
  -v mosquitto-data:/mosquitto/data \
  -v mosquitto-logs:/mosquitto/log \
  eclipse-mosquitto:latest
```

### Verify MQTT Broker is Running
```bash
# Test connection (should connect without errors)
mosquitto_sub -h localhost -t test -v
# Press Ctrl+C to exit
```

---

## Step 2: Configure MQTT Broker (Basic)

**Important:** You do **NOT** need to configure Mosquitto bridges. The `ecoflow_cloud_bridge.py` service handles the EcoFlow cloud connection.

### Basic Configuration (Optional)

If you want to enable authentication or logging, create `/etc/mosquitto/conf.d/local.conf`:

```conf
# Allow anonymous connections (default)
allow_anonymous true

# Listen on all interfaces
listener 1883 0.0.0.0

# Optional: Enable logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
```

Restart Mosquitto after changes:
```bash
sudo systemctl restart mosquitto
```

---

## Step 3: Obtain EcoFlow Developer API Credentials

### Developer API Credentials

1. Visit the EcoFlow Developer Portal:
   - **EU:** https://developer-eu.ecoflow.com
   - **US:** https://developer-us.ecoflow.com

2. **Apply for access** (usually auto-approved within 24 hours)
   - Use your EcoFlow account email
   - Company: Personal/Individual
   - Use case: "Home automation and power monitoring"

3. **Log in** after approval (or try after 24 hours)

4. **Create API Keys:**
   - Navigate to "Access Key Management"
   - Click "Create Access Key"
   - **Save both immediately** (Secret Key shown only once):
     ```
     Access Key:  AK_xxxxxxxxxxxxxxxxxxxxxxxxxx
     Secret Key:  SK_yyyyyyyyyyyyyyyyyyyyyyyyyy
     ```

---

## Step 4: Install EcoFlow Power Management

### Clone Repository
```bash
git clone https://github.com/JoshuaDodds/ecoflow-power-management.git
cd ecoflow-power-management
```

### Install Python Dependencies
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 5: Configure Environment

### Copy Example Configuration
```bash
cp .env-example .env
```

### Edit `.env` File
```bash
nano .env  # or use your preferred editor
```

### Required Configuration
```bash
# ============================================================================
# ECOFLOW DEVELOPER API CREDENTIALS
# ============================================================================

# Developer API (From Developer Portal)
ECOFLOW_ACCESS_KEY="AK_xxxxxxxxxxxxxxxxxxxxxxxxxx"
ECOFLOW_SECRET_KEY="SK_yyyyyyyyyyyyyyyyyyyyyyyyyy"

# Device Serial Numbers (comma-separated)
# Find these in your EcoFlow mobile app
ECOFLOW_DEVICE_LIST="R631ZEB4WH123456,R631ZEB4WH789012"

# ============================================================================
# LOCAL MQTT BROKER
# ============================================================================

MQTT_HOST=localhost  # Or IP address of your MQTT broker
MQTT_PORT=1883

# ============================================================================
# POLICY CONFIGURATION
# ============================================================================

# Shutdown threshold (battery percentage)
POLICY_SOC_MIN=10

# Safety timer (seconds) - condition must persist this long
POLICY_DEBOUNCE_SEC=180

# Cooldown between commands (seconds)
POLICY_COOLDOWN_SEC=300

# ============================================================================
# DEVICE-TO-AGENT MAPPING
# ============================================================================

# Map device names to agent IDs
# Device names come from EcoFlow app (e.g., "Study", "Office")
# Agent IDs must match the AGENT_ID on each client machine

# Single-line format (recommended):
DEVICE_TO_AGENTS_JSON={"Study":["pc-study","nas-study"],"Office":["pc-office"]}

# Or multi-line format (more readable):
# DEVICE_TO_AGENTS_JSON='{
#   "Study": ["pc-study", "nas-study"],
#   "Office": ["pc-office"]
# }'
```

---

## Step 6: Test Configuration

### Validate Configuration
```bash
python3 -c "from utils.config_validator import ConfigValidator; ConfigValidator.validate_all(); ConfigValidator.print_config_summary()"
```

You should see:
```
======================================================================
📋 Configuration Summary
======================================================================
  Access Key:      AK_xxxxx***
  Devices:         2 configured
  MQTT Broker:     localhost:1883
  Policy:          Shutdown at 10% (debounce: 180s)
  Agent Mapping:   2 devices → 3 agents
======================================================================
```

---

## Step 7: Run the Orchestrator

### Start the Orchestrator
```bash
python3 main.py
```

### Expected Output
```
2026-01-21 09:00:00,000 [INFO] orchestrator: --- EcoFlow Power Management Orchestrator v0.1.0-alpha Starting ---

======================================================================
📋 Configuration Summary
======================================================================
  ...
======================================================================

2026-01-21 09:00:01,000 [INFO] orchestrator: Found service: soc_bridge
2026-01-21 09:00:01,000 [INFO] orchestrator: Found service: policy_engine
2026-01-21 09:00:01,000 [INFO] orchestrator: Found service: ecoflow_cloud
2026-01-21 09:00:01,000 [INFO] ecoflow_cloud: ✅ Acquired EcoFlow Cloud MQTT Credentials.
2026-01-21 09:00:01,000 [INFO] ecoflow_cloud: ✅ Connected to EcoFlow Cloud!
2026-01-21 09:00:01,000 [INFO] soc_bridge: New Device Discovered: Study
2026-01-21 09:00:01,000 [INFO] policy_engine: Connected to MQTT broker
```

### Verify Data Flow
```bash
# In another terminal, subscribe to device state
mosquitto_sub -h localhost -t "bridge-ecoflow/+/json/state" -v
```

You should see JSON messages with battery state, grid status, etc.

---

## Step 8: Deploy Agents

Agents run on the machines you want to protect (PCs, servers, NAS).

### Choose Your Platform
- **Linux:** See [`agents/linux/README.md`](agents/linux/README.md)
- **Windows:** See [`agents/windows/README.md`](agents/windows/README.md)
- **macOS:** See [`agents/macos/README.md`](agents/macos/README.md)

### Quick Agent Setup Example (Linux)
```bash
# On the client machine
cd agents/linux

# Configure
export AGENT_ID="pc-study"  # Must match DEVICE_TO_AGENTS_JSON
export MQTT_BROKER="192.168.1.100"  # IP of orchestrator machine
export MQTT_PORT="1883"

# Test
python3 shutdown-listener.py
```

---

## Troubleshooting

### MQTT Connection Issues

**Problem:** `Connection refused` errors

**Solutions:**
1. Verify Mosquitto is running:
   ```bash
   sudo systemctl status mosquitto
   ```

2. Check firewall allows port 1883:
   ```bash
   sudo ufw allow 1883/tcp
   ```

3. Test connectivity from agent machine:
   ```bash
   mosquitto_sub -h <orchestrator-ip> -p 1883 -t test
   ```

### EcoFlow Cloud Connection Issues

**Problem:** `Failed to acquire MQTT credentials`

**Solutions:**
1. Verify Developer API credentials in `.env` are correct
2. Ensure Developer API keys are from correct region (EU vs US)
3. Check you have access to the Developer Portal

### No Device Data

**Problem:** Orchestrator starts but no device data appears

**Solutions:**
1. Verify device serial numbers in `ECOFLOW_DEVICE_LIST` are correct
2. Check devices are online in EcoFlow mobile app
3. Wait 5 minutes for initial heartbeat/wakeup cycle

---

## Advanced: Docker Deployment

See [`DOCKER.md`](DOCKER.md) for containerized deployment instructions.

---

## Next Steps

1. **Test the system** with simulated events:
   ```bash
   python3 simulations/simulate_critical_event.py
   ```

2. **Monitor logs** to understand the policy engine behavior

3. **Configure agents** on all machines you want to protect

4. **Test shutdown/abort** commands in a safe environment

---

## Important Notes

### About `ecoflow_get_mqtt_login.sh`

The `tools/ecoflow_get_mqtt_login.sh` script is **NOT required** for standard deployment. It's a legacy tool for advanced users who want to configure Mosquitto bridges directly instead of using the `ecoflow_cloud_bridge.py` service.

**You can ignore this script unless you specifically want to:**
- Bypass the Python cloud bridge service
- Configure Mosquitto to bridge directly to EcoFlow cloud
- Use a different MQTT broker architecture

### Architecture

```
┌─────────────────┐
│ EcoFlow Cloud   │
└────────┬────────┘
         │ (MQTT/TLS)
         ↓
┌─────────────────────────┐
│ ecoflow_cloud_bridge.py │ ← Handles cloud connection
└────────┬────────────────┘
         │ (publishes to local MQTT)
         ↓
┌─────────────────┐
│ Local Mosquitto │ ← Simple pub/sub broker
└────┬───────┬────┘
     │       │
     ↓       ↓
┌─────────┐ ┌──────────────┐
│ Agents  │ │ soc_bridge   │
│         │ │ policy_engine│
└─────────┘ └──────────────┘
```

**Key Point:** The Python service handles the complex EcoFlow cloud connection. Your local Mosquitto broker only needs basic pub/sub functionality.
