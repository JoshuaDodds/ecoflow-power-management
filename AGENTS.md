# AI Agent Directives & Guardrails

This document provides context and guardrails for AI agents working on this codebase.

## 1. Core Directives
* **No Guessing on Grid State:** For `River 3 Plus` devices, **never** use Watts or Volts to guess grid connectivity. You MUST use Protobuf **Tag 27**.
    * `Tag 27 <= 1`: Connected.
    * `Tag 27 > 1`: Disconnected.
* **Safety First:** The Policy Engine is a critical safety component.
    * It must handle **Data Gaps** (>60s) by resetting all timers.
    * It must never assume state during a loss of telemetry.
* **Configuration:** Hardcoded values are forbidden for Logic/Rules. All thresholds (SOC, Timers) must be loaded from `os.environ` via `.env`.

## 2. Data Standard (Inter-Service)
Services communicate via MQTT using this JSON standard. Do not deviate.

**Topic:** `bridge-ecoflow/{DeviceName}/json/state`
```json
{
  "device": "Study",
  "soc": 45.5,
  "grid_connected": false
}
```

## 3. Command Standard (Policy -> Agent)
**Topic:** `power-manager/{AgentID}/cmd`
```json
{
  "id": "uuid-string",
  "action": "shutdown",  // or "abort"
  "reason": "Critical: Grid Lost & SoC 5%",
  "delay_sec": 60,
  "ttl_sec": 300
}
```

## 4. Known Issues / Context
* **River 3 Plus Parsing:** This device multiplexes "Status" and "BMS" reports on the same Protobuf ID.
    * **Imposter Packets:** You must filter packets where Tag 16 (Temp) is a small integer (0 < x < 100). These are Enums, not temperatures. Failure to filter these will corrupt Voltage and Grid state data.
* **Ghost Power:** The Inverter often reports ~14W input even when disconnected (if not using Tag 27). Do not trust `ac_in_watts` for connectivity.