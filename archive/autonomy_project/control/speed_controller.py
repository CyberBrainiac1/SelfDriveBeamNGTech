"""
Longitudinal (speed) controller — throttle / brake.

Uses a PID with coast‑band: if the speed is within ±coast_band
of the target, neither throttle nor brake is applied.
"""

from __future__ import annotations
import time
from typing import Tuple

from config import CFG


class SpeedController:
    """PID speed controller producing (throttle, brake) each tick."""

    def __init__(self) -> None:
        c = CFG.speed
        self.kp = c.kp
        self.ki = c.ki
        self.kd = c.kd
        self.throttle_max = c.throttle_max
        self.brake_max = c.brake_max
        self.coast_band = c.coast_band_kph

        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_time: float = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = time.monotonic()

    def compute(self, target_kph: float, current_kph: float) -> Tuple[float, float]:
        """Return (throttle, brake) in [0, 1]."""
        now = time.monotonic()
        dt = now - self._prev_time
        if dt <= 0:
            dt = 1e-3
        self._prev_time = now

        error = target_kph - current_kph  # positive → too slow

        # Coast band
        if abs(error) < self.coast_band:
            self._prev_error = error
            return 0.0, 0.0

        self._integral += error * dt
        self._integral = max(-50.0, min(50.0, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        if output > 0:
            throttle = min(output, self.throttle_max)
            brake = 0.0
        else:
            throttle = 0.0
            brake = min(abs(output), self.brake_max)

        return throttle, brake
