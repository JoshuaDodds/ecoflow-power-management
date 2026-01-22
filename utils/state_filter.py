"""
Boolean State Filter

Filters transient false readings in binary state values (e.g., grid_connected).
Uses confirmation window approach - requires N consecutive readings before
accepting a state change.
"""
import time
import logging
from typing import Optional
from collections import deque

logger = logging.getLogger("state_filter")


class BooleanStateFilter:
    """Filter transient false readings in boolean state values"""
    
    def __init__(self, device_name: str, state_name: str = "state", required_confirmations: int = 5):
        """
        Initialize boolean state filter.
        
        Args:
            device_name: Name of device for logging
            state_name: Name of the state being filtered (for logging)
            required_confirmations: Number of consecutive readings required to confirm state change
        """
        self.device_name = device_name
        self.state_name = state_name
        self.required_confirmations = required_confirmations
        
        # Current confirmed state
        self.confirmed_state: Optional[bool] = None
        
        # Confirmation window
        self.pending_state: Optional[bool] = None
        self.confirmation_count = 0
        
        # Recent readings for majority voting
        self.recent_readings = deque(maxlen=required_confirmations)
        
        # Tracking
        self.last_update_time: Optional[float] = None
    
    def filter(self, raw_value: bool, timestamp: float = None) -> bool:
        """
        Filter boolean state value through confirmation window.
        
        Args:
            raw_value: Raw boolean value from device
            timestamp: Unix timestamp (defaults to current time)
        
        Returns:
            Filtered boolean value (confirmed state)
        """
        if timestamp is None:
            timestamp = time.time()
        
        # First reading - accept and initialize
        if self.confirmed_state is None:
            logger.info(
                f"[{self.device_name}] {self.state_name} filter initialized: {raw_value}"
            )
            self._accept_reading(raw_value, timestamp)
            return raw_value
        
        # Add to recent readings
        self.recent_readings.append(raw_value)
        
        # Check for large time gap (device was offline)
        if self.last_update_time is not None:
            time_delta = timestamp - self.last_update_time
            if time_delta > 300:  # 5 minutes
                logger.info(
                    f"[{self.device_name}] Large time gap detected ({time_delta:.0f}s), "
                    f"resetting {self.state_name} confirmation window"
                )
                self._reset_confirmation()
        
        # Check if state matches confirmed state
        if raw_value == self.confirmed_state:
            # State unchanged - reset any pending confirmation
            if self.pending_state is not None:
                logger.debug(
                    f"[{self.device_name}] {self.state_name} returned to confirmed state: {raw_value}"
                )
                self._reset_confirmation()
            self.last_update_time = timestamp
            return self.confirmed_state
        
        # State change detected - require confirmation
        if self.pending_state is None or self.pending_state != raw_value:
            # New pending state
            self.pending_state = raw_value
            self.confirmation_count = 1
            logger.info(
                f"[{self.device_name}] PENDING: {self.state_name} change "
                f"{self.confirmed_state} → {raw_value} awaiting confirmation "
                f"(1/{self.required_confirmations})"
            )
        else:
            # Same pending state - increment confirmation
            self.confirmation_count += 1
            logger.info(
                f"[{self.device_name}] PENDING: {self.state_name} change "
                f"{self.confirmed_state} → {raw_value} awaiting confirmation "
                f"({self.confirmation_count}/{self.required_confirmations})"
            )
            
            # Check if confirmed
            if self.confirmation_count >= self.required_confirmations:
                logger.warning(
                    f"[{self.device_name}] CONFIRMED: {self.state_name} change "
                    f"{self.confirmed_state} → {raw_value} "
                    f"after {self.confirmation_count} consecutive readings"
                )
                self._accept_reading(raw_value, timestamp)
                self._reset_confirmation()
                return raw_value
        
        # Not yet confirmed - return current confirmed state
        self.last_update_time = timestamp
        return self.confirmed_state
    
    def _accept_reading(self, value: bool, timestamp: float):
        """Accept a reading and update confirmed state"""
        self.confirmed_state = value
        self.last_update_time = timestamp
    
    def _reset_confirmation(self):
        """Reset confirmation window"""
        self.pending_state = None
        self.confirmation_count = 0
