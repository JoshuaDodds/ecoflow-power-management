# Tools Directory

This directory contains utility scripts for advanced users and legacy configurations.

## 🔧 Available Tools

### `ecoflow_get_mqtt_login.sh`

**Status:** ⚠️ **Legacy / Optional**

This script obtains MQTT credentials from EcoFlow and generates Mosquitto bridge configuration.

**Important:** You do **NOT** need this script for standard deployment. The `ecoflow_cloud_bridge.py` service handles the EcoFlow cloud connection automatically.

#### When to Use This Script

Use this script **only if** you want to:
- Configure Mosquitto to bridge directly to EcoFlow cloud (bypassing the Python service)
- Use a different MQTT broker architecture
- Debug MQTT connection issues
- Understand the underlying MQTT protocol

#### When NOT to Use This Script

**Skip this script if:**
- You're following the standard setup guide ([SETUP.md](../SETUP.md))
- You're using the `ecoflow_cloud_bridge.py` service (default)
- You're new to the project

#### Usage

```bash
./ecoflow_get_mqtt_login.sh
```

The script will:
1. Prompt for your EcoFlow username/password
2. Obtain MQTT broker credentials
3. Generate Mosquitto bridge configuration
4. Output configuration snippets for `/etc/mosquitto/conf.d/`

#### Example Output

```conf
connection bridge-ecoflow-study
    address mqtt-e.ecoflow.com:8883
    remote_username <username>
    remote_password <password>
    remote_clientid <client-id>
    topic "" both 0 bridge-ecoflow/Study/data /app/device/property/R631ZEB4WH123456
    # ... more topic mappings
```

---

### `generate_curl.py`

Generates signed API requests for EcoFlow Developer API.

**Usage:**
```bash
python3 generate_curl.py
```

Requires `ECOFLOW_ACCESS_KEY` and `ECOFLOW_SECRET_KEY` in `.env` file.

---

## 📖 Standard Setup

For standard deployment, **ignore these tools** and follow: **[SETUP.md](../SETUP.md)**

The standard setup uses:
- `ecoflow_cloud_bridge.py` - Handles EcoFlow cloud connection
- Local Mosquitto - Simple pub/sub broker (no bridge configuration needed)
- Python services - Handle all MQTT communication

---

## 🔍 Architecture Comparison

### Standard Setup (Recommended)
```
EcoFlow Cloud ←→ ecoflow_cloud_bridge.py ←→ Local Mosquitto ←→ Services/Agents
```
- ✅ Simpler configuration
- ✅ Automatic credential management
- ✅ Better error handling
- ✅ Integrated with orchestrator

### Legacy Setup (Using ecoflow_get_mqtt_login.sh)
```
EcoFlow Cloud ←→ Mosquitto Bridge ←→ Local Mosquitto ←→ Services/Agents
```
- ⚠️ Manual bridge configuration required
- ⚠️ Manual credential management
- ⚠️ Separate from orchestrator
- ✅ Lower Python overhead

---

## 🆘 Support

For questions about these tools, please open an issue on GitHub.
