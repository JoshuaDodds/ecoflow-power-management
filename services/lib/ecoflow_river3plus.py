"""
EcoFlow Device Abstraction Library (Heartbeat Edition)
Location: services/lib/ecoflow_river3plus.py

Responsibilities:
1. Structural Decoding: Parses protobuf into grouped dictionaries.
2. Signature Validation: Filters "Imposter" Status reports.
3. VISIBILITY: Returns True on ANY valid BMS packet so you see the device is alive.
"""

import time
import logging
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger("ecoflow_river3plus")

class EcoFlowDevice:
    def __init__(self, serial_number: str):
        self.sn = serial_number
        self.last_update = 0.0

        # --- State Attributes ---
        self.soc: float = 0.0
        self.soc_modules: List[int] = []
        self.ac_in_watts: float = 0.0
        self.grid_connected: bool = True
        self.temp_celsius: float = 0.0

    def update_from_protobuf(self, payload: bytes) -> bool:
        """
        Parses raw protobuf payload.
        Returns True if ANY valid data was found (Force Publish).
        """
        try:
            # 1. Parse into a list of message objects (dictionaries)
            messages = self._parse_proto_structure(payload)

            raw_socs = []
            valid_temps = []
            updates = {}

            # Track if we found ANY valid data in this packet
            packet_contains_valid_data = False

            for msg in messages:
                # Extract Potential Data
                m_soc = msg.get(6)
                m_watts = msg.get(28)
                m_grid = msg.get(27)
                m_temp = msg.get(16)

                # --- Power (Global Tag) ---
                if m_watts is not None:
                    # Tag 28 treated as unsigned 32-bit, scaled by 10.0
                    updates["ac_in_watts"] = float(m_watts) / 10.0
                    packet_contains_valid_data = True

                # --- Grid Logic (Strict Tag 27) ---
                # 0/1 = Connected. >1 = Disconnected.
                if m_grid is not None:
                    is_connected = (m_grid <= 1)
                    updates["grid_connected"] = is_connected
                    packet_contains_valid_data = True

                # --- Battery Module Signature Check ---
                if m_soc is not None:
                    is_valid_bms = True
                    
                    # 1. SOC Range Validation (MUST be 0-100%)
                    if not (0 <= m_soc <= 100):
                        is_valid_bms = False
                        logger.debug(f"[{self.sn}] Rejected SOC out of range: {m_soc}")
                    
                    # 2. Ghost Check: SoC 0 and Temp 0 (Empty Slot)
                    elif m_soc == 0:
                        if m_temp is None or m_temp == 0:
                            is_valid_bms = False
                    
                    # 3. Enum/Imposter Check
                    # Valid battery temps are in centidegrees (e.g., 25000 = 25.0°C)
                    # Values 0-100 likely represent status enums, not temperatures
                    elif m_temp is not None and (0 < m_temp < 100):
                        is_valid_bms = False
                    
                    # 4. Require Temperature for Valid BMS Module
                    # Valid battery modules ALWAYS report temperature (field 16)
                    # Ghost/disconnected modules typically don't report temperature
                    elif m_temp is None:
                        is_valid_bms = False
                        logger.debug(f"[{self.sn}] Rejected SOC without temp: {m_soc}%")

                    # 5. Aggregation
                    if is_valid_bms:
                        raw_socs.append(m_soc)
                        if m_temp is not None:
                            valid_temps.append(m_temp / 100.0)
                        packet_contains_valid_data = True
                        logger.debug(
                            f"[{self.sn}] ✓ Valid BMS: SOC={m_soc}%, "
                            f"Temp={m_temp/100.0 if m_temp else 'N/A'}°C"
                        )

            # --- Update State ---
            if updates:
                self._apply_updates(updates)

            if valid_temps:
                self.temp_celsius = sum(valid_temps) / len(valid_temps)

            if raw_socs:
                self._update_soc_latch(raw_socs)

            # --- ALWAYS RETURN TRUE if data was valid ---
            # This ensures we see the device in MQTT even if values are stable.
            if packet_contains_valid_data:
                self.last_update = time.time()
                return True

            return False

        except Exception as e:
            logger.error(f"[{self.sn}] Parse Error: {e}")
            return False

    def to_json(self) -> Dict[str, Any]:
        return {
            # "ts": int(self.last_update * 1000), # Commented as per request
            "device": self.sn,
            "soc": self.soc,
            "grid_connected": self.grid_connected,
            "temp_celsius": round(self.temp_celsius, 2)
        }

    # --- Logic: Signal Processing ---

    def _update_soc_latch(self, valid_socs: List[int]):
        """
        Latches to stable SOC.
        """
        valid_socs = [s for s in valid_socs if 0 <= s <= 100]
        if not valid_socs: return

        candidates = valid_socs

        if self.soc == 0.0:
            chosen = max(candidates)
        else:
            chosen = min(candidates, key=lambda x: abs(x - self.soc))

        self.soc = float(chosen)
        self.soc_modules = sorted(candidates, reverse=True)

    def _apply_updates(self, updates: Dict):
        """
        Applies updates immediately.
        """
        if "grid_connected" in updates:
            self.grid_connected = updates["grid_connected"]

        if "ac_in_watts" in updates:
            self.ac_in_watts = updates["ac_in_watts"]

    # --- Logic: Structured Protobuf Parser ---

    def _parse_proto_structure(self, payload: bytes) -> List[Dict[int, Any]]:
        messages = []
        current_msg = {}

        i = 0
        while i < len(payload):
            try:
                tag, i = self._read_varint(payload, i)
                field = tag >> 3
                wtype = tag & 0x7

                if wtype == 0: # Varint
                    val, i = self._read_varint(payload, i)
                    current_msg[field] = val
                elif wtype == 2: # Length Delimited
                    ln, i = self._read_varint(payload, i)
                    if ln > 0:
                        sub_payload = payload[i:i+ln]
                        # Try to parse as sub-message
                        sub_msgs = self._parse_proto_structure(sub_payload)
                        if sub_msgs:
                            messages.extend(sub_msgs)
                        else:
                            pass
                    i += ln
                elif wtype == 1: i += 8
                elif wtype == 5: i += 4
                else: break
            except: break

        if current_msg:
            messages.append(current_msg)
        return messages

    def _read_varint(self, buf: bytes, i: int) -> Tuple[int, int]:
        shift = 0
        val = 0
        while True:
            if i >= len(buf): raise ValueError("truncated varint")
            b = buf[i]
            i += 1
            val |= (b & 0x7F) << shift
            if not (b & 0x80): return val, i
            shift += 7