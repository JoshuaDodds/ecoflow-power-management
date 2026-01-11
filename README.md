# EcoFlow Power Management

## Overview

**EcoFlow Power Management** is a lightweight, MQTT-based power-aware shutdown system for heterogeneous environments (Linux, Windows, NAS).

It consumes EcoFlow device telemetry from a local MQTT broker, derives a **normalized battery State-of-Charge (SoC)**, and—when configurable thresholds are reached—**initiates clean, host-local shutdown procedures** across machines powered by those devices.

The system is intentionally:
- **Simple**
- **Observable**
- **Vendor-agnostic**
- **Fail-safe**

No direct SSH, WinRM, or remote execution is required.  
All coordination happens over MQTT.

---

## Design Principles

- **Read-only by default**  
  The system never writes to EcoFlow Cloud unless explicitly enabled.

- **MQTT as the only control plane**  
  All services and agents communicate exclusively via MQTT topics.

- **Flat, explicit services**  
  One Python file per service. No hidden frameworks.

- **Host-local execution**  
  Each machine decides how to shut itself down.

- **Windows without Python**  
  Windows shutdown is handled via native `.bat` / PowerShell scripts.

---

## High-Level Architecture

```text
EcoFlow Cloud
     │
     ▼
Mosquitto Bridge
     │
     ▼
┌──────────────────────┐
│ soc_bridge service   │
│ (protobuf → JSON)    │
└──────────────────────┘
     │
     ▼
bridge-ecoflow/<device>/json/state
     │
     ▼
┌──────────────────────┐
│ policy_engine        │
│ (threshold logic)    │
└──────────────────────┘
     │
     ▼
power-manager/<host>/cmd
     │
     ▼
┌──────────────────────┐
│ host agents          │
│ (Linux / Windows)    │
└──────────────────────┘
```

---

## Repository Layout

```text
ecoflow-power-management/
├── LICENSE
├── README.md
├── Makefile
├── .env.example
├── docker/
│   └── entrypoint.sh
├── services/
│   └── soc_bridge.py
├── agents/
│   └── host_agent.py
└── archive/
    └── ecoflow-bridge-proto/
```

### Active Components

- `services/soc_bridge.py`  
  Production-ready telemetry decoder. Converts EcoFlow protobuf into stable JSON.

- `services/policy_engine.py` *(planned)*  
  Watches SoC, applies thresholds, publishes shutdown commands.

- `agents/host_agent.py` *(Linux only)*  
  Executes pre-shutdown and shutdown commands.

- **Windows agent (no Python)**  
  Implemented via `.bat` / PowerShell subscribed to MQTT.

---

## Telemetry Contract (Stable)

### Input Topic

```text
bridge-ecoflow/<DEVICE>/json/state
```

### Example Payload

```json
{
  "ts": 1768088715859,
  "device": "STUDY",
  "soc": 85.5,
  "soc_min": 85,
  "soc_modules": [86, 85]
}
```

### Semantics

- `soc` → headline SoC (average)
- `soc_min` → most conservative value (use for shutdown decisions)
- `soc_modules`
  - One value → all parallel batteries equal
  - Multiple values → module divergence detected

---

## Command Topics

### Shutdown Command

```text
power-manager/<host>/cmd
```

Payload:

```json
{
  "id": "shutdown-1768089900",
  "action": "shutdown",
  "delay_sec": 60,
  "reason": "EcoFlow STUDY soc_min <= 20",
  "ttl_sec": 300
}
```

### Acknowledgement (Optional)

```text
power-manager/<host>/ack
```

---

## Environment Configuration (`.env`)

All configuration is done via environment variables.

### Shared MQTT Configuration

```env
MQTT_HOST=mosquitto
MQTT_PORT=1883
MQTT_USER=
MQTT_PASS=
```

### Policy Configuration

```env
POLICY_SOC_MIN=20
POLICY_DEBOUNCE_SEC=60
POLICY_COOLDOWN_SEC=600
DEVICE_TO_AGENTS_JSON={"STUDY":["pc-study","nas-thecus"]}
```

### Host Agent Configuration

```env
AGENT_ID=pc-study
PRE_SHUTDOWN_CMD_1="microk8s stop"
SHUTDOWN_CMD="shutdown -h now"
```

---

## Windows 11 Support (No Python)

Windows machines do not require Python.

### Recommended Approach

- Use **PowerShell + Task Scheduler**
- Subscribe to MQTT using:
  - `mosquitto_sub.exe` (official Mosquitto Windows build)

### Example `shutdown-listener.ps1`

```powershell
mosquitto_sub.exe -h mosquitto `
  -t power-manager/pc-study/cmd |
ForEach-Object {
    Write-Host "Shutdown command received"
    Stop-Service microk8s -Force
    shutdown.exe /s /t 60 /f /c "EcoFlow low battery"
}
```

### Run at Startup

- Task Scheduler
- Trigger: At startup
- Run as: SYSTEM
- Action: `powershell.exe -File shutdown-listener.ps1`

This keeps Windows fully native, auditable, and dependency-free.

---

## Why This Works Reliably

- MQTT is already present and resilient
- EcoFlow telemetry is eventually consistent
- Battery modules only emit deltas when diverging (intentional behavior)
- Conservative `soc_min` avoids false safety margins
- Shutdown logic is local and deterministic

---

## Roadmap

### Phase 1 (Current)

- ✅ SoC decoding and normalization
- ✅ Multi-battery handling
- ✅ Read-only EcoFlow integration

### Phase 2 (Next)

- Policy engine (thresholds, debounce, cooldown)
- Host agents (Linux + Windows)
- Audit / event stream

### Phase 3 (Optional)

- Startup coordination
- Capacity-weighted SoC
- Alerting / notifications

---

## Non-Goals

- No remote execution (SSH, WinRM)
- No Windows binaries
- No tight coupling between hosts
- No vendor SDK dependency

---

## Status

**Ready for production telemetry.**  
Policy engine and agents are intentionally simple and forthcoming.
