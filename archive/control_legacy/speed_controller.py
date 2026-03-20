"""
speed_controller.py
====================
PID speed controller producing throttle / brake outputs.
"""

from __future__ import annotations
import time
from typing import Tuple

from config import CFG


class SpeedController:
    def __init__(self) -> None:
        c = CFG.speed
        self.kp = c.kp
        self.ki = c.ki
        self.kd = c.kd
        self.coast_band = c.coast_band_kph
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = time.monotonic()

    def compute(self, target_kph: float, current_kph: float) -> Tuple[float, float]:
        """Returns (throttle, brake) both in [0, 1]."""
        now = time.monotonic()
        dt = max(now - self._prev_time, 1e-3)
        self._prev_time = now

        error = target_kph - current_kph

        if abs(error) < self.coast_band:
            self._prev_error = error
            return 0.0, 0.0

        self._integral = max(-50.0, min(50.0, self._integral + error * dt))
        deriv = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * deriv

        if output > 0:
            return min(output, 1.0), 0.0
        else:
            return 0.0, min(abs(output), 1.0)
