"""
steering_controller.py
======================
PID steering controller with deadband, rate limiting, and output clamping.
Identical in logic to the BeamNG version — reused here.
"""

from __future__ import annotations
import time

from config import CFG


class SteeringController:
    def __init__(self) -> None:
        c = CFG.steering
        self.kp = c.kp
        self.ki = c.ki
        self.kd = c.kd
        self.out_min = c.output_min
        self.out_max = c.output_max
        self.deadband = c.deadband
        self.max_rate = c.max_rate
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_time = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_time = time.monotonic()

    def compute(self, target: float) -> float:
        """target = lane offset (-1…+1).  Returns steering command (-1…+1)."""
        now = time.monotonic()
        dt = max(now - self._prev_time, 1e-3)
        self._prev_time = now

        error = target
        if abs(error) < self.deadband:
            error = 0.0

        self._integral = max(-1.0, min(1.0, self._integral + error * dt))
        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        output = max(self.out_min, min(self.out_max, output))

        # Rate limit
        delta = output - self._prev_output
        if abs(delta) > self.max_rate:
            output = self._prev_output + self.max_rate * (1 if delta > 0 else -1)
        self._prev_output = output
        return output
