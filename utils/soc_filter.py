"""
SOC Anomaly Filter

Filters erroneous SOC readings using multi-tier validation:
1. Plausibility check (rate limiting)
2. Confirmation window (require multiple consecutive readings)
3. Median filter (smooth out noise)
"""
import time
import statistics
import logging
from typing import Optional

logger = logging.getLogger("soc_filter")


class SOCFilter:
    """Filter anomalous SOC readings using multi-tier validation"""
    
    def __init__(self, device_name: str):
        self.device_name = device_name
        
        # Tier 1: Plausibility check
        self.max_change_per_minute = 10.0  # Max % change per minute
        
        # Tier 2: Confirmation window
        self.confirmation_threshold = 5.0  # % change requiring confirmation
        self.required_confirmations = 5  # Consecutive readings needed
        self.pending_soc = None
        self.confirmation_count = 0
        self.confirmed_soc = None
        
        # Tier 3: Median filter
        self.window_size = 5
        self.recent_readings = []
        
        # Tracking
        self.last_valid_soc = None
        self.last_valid_time = None
        self.last_gap_reset = None
    
    def filter(self, raw_soc: float, timestamp: float = None) -> Optional[float]:
        """
        Filter SOC reading through multi-tier validation.
        
        Args:
            raw_soc: Raw SOC value from device (0-100)
            timestamp: Unix timestamp (defaults to current time)
        
        Returns:
            Filtered SOC value, or None if rejected
        """
        if timestamp is None:
            timestamp = time.time()
        
        # First reading - accept and initialize
        if self.last_valid_soc is None:
            logger.info(f"[{self.device_name}] SOC Filter initialized: {raw_soc}%")
            self._accept_reading(raw_soc, timestamp)
            return raw_soc
        
        # Check for large time gap (device was offline)
        time_delta = timestamp - self.last_valid_time
        if time_delta > 300:  # 5 minutes
            logger.info(
                f"[{self.device_name}] Large time gap detected ({time_delta:.0f}s), "
                f"resetting confirmation window"
            )
            self._reset_confirmation()
            self.last_gap_reset = timestamp
        
        # Tier 1: Plausibility check
        if not self._is_plausible(raw_soc, timestamp):
            logger.warning(
                f"[{self.device_name}] REJECTED: Implausible SOC change "
                f"{self.last_valid_soc:.1f}% → {raw_soc:.1f}% in {time_delta:.1f}s "
                f"({self._calculate_change_rate(raw_soc, timestamp):.1f}%/min, "
                f"max: {self.max_change_per_minute}%/min)"
            )
            return None  # Reject this reading
        
        # Tier 2: Confirmation window
        confirmed = self._check_confirmation(raw_soc)
        if not confirmed:
            logger.info(
                f"[{self.device_name}] PENDING: SOC {raw_soc:.1f}% awaiting confirmation "
                f"({self.confirmation_count}/{self.required_confirmations})"
            )
            return self.confirmed_soc  # Return last confirmed value
        
        # Tier 3: Median filter
        filtered_soc = self._apply_median_filter(raw_soc)
        
        logger.debug(
            f"[{self.device_name}] FILTERED: raw={raw_soc:.1f}%, "
            f"window={[round(r, 1) for r in self.recent_readings]}, "
            f"median={filtered_soc:.1f}%"
        )
        
        # Update tracking
        self._accept_reading(filtered_soc, timestamp)
        
        return filtered_soc
    
    def _is_plausible(self, new_soc: float, timestamp: float) -> bool:
        """Check if SOC change is physically plausible"""
        if self.last_valid_soc is None:
            return True
        
        # Small changes (<= 3.0%) are always plausible regardless of time
        # This handles rapid toggling between batteries (e.g. 90% -> 89% -> 90%)
        # and normal charging/discharging noise.
        soc_delta = abs(new_soc - self.last_valid_soc)
        if soc_delta <= 3.0:
            return True

        change_rate = self._calculate_change_rate(new_soc, timestamp)
        return change_rate <= self.max_change_per_minute
    
    def _calculate_change_rate(self, new_soc: float, timestamp: float) -> float:
        """Calculate SOC change rate in %/minute"""
        if self.last_valid_soc is None or self.last_valid_time is None:
            return 0.0
        
        time_delta = timestamp - self.last_valid_time
        if time_delta <= 0:
            return 0.0
        
        soc_delta = abs(new_soc - self.last_valid_soc)
        change_per_minute = (soc_delta / time_delta) * 60
        
        return change_per_minute
    
    def _check_confirmation(self, new_soc: float) -> bool:
        """
        Check if SOC change is confirmed by consecutive readings.
        
        Returns:
            True if confirmed, False if still pending
        """
        # Small change - no confirmation needed
        if self.confirmed_soc is not None:
            change = abs(new_soc - self.confirmed_soc)
            if change <= self.confirmation_threshold:
                self._reset_confirmation()
                self.confirmed_soc = new_soc
                return True
        
        # Large change - require confirmation
        if self.pending_soc is None or abs(new_soc - self.pending_soc) > 0.5:
            # New pending value
            self.pending_soc = new_soc
            self.confirmation_count = 1
            return False
        else:
            # Same pending value
            self.confirmation_count += 1
            if self.confirmation_count >= self.required_confirmations:
                logger.info(
                    f"[{self.device_name}] CONFIRMED: SOC change "
                    f"{self.confirmed_soc:.1f}% → {new_soc:.1f}% "
                    f"after {self.confirmation_count} consecutive readings"
                )
                self.confirmed_soc = new_soc
                self._reset_confirmation()
                return True
            return False
    
    def _apply_median_filter(self, new_soc: float) -> float:
        """Apply median filter to smooth out noise"""
        self.recent_readings.append(new_soc)
        
        # Keep only last N readings
        if len(self.recent_readings) > self.window_size:
            self.recent_readings.pop(0)
        
        # Return median
        return statistics.median(self.recent_readings)
    
    def _accept_reading(self, soc: float, timestamp: float):
        """Accept a reading and update tracking"""
        self.last_valid_soc = soc
        self.last_valid_time = timestamp
        if self.confirmed_soc is None:
            self.confirmed_soc = soc
    
    def _reset_confirmation(self):
        """Reset confirmation window"""
        self.pending_soc = None
        self.confirmation_count = 0
