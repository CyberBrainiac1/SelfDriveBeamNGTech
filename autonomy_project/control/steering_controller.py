"""
PID steering controller with deadband, clamping, and rate limiting.

Input : steering target  (-1 … +1, where 0 = centre of road)
Output: steering command  (-1 … +1, sent to vehicle)

The *error* is simply `target - 0` because the goal is to centre
the car in the lane (target = 0 when perfectly centred).

A positive offset means the road centre is to the right of the image
centre, so we steer right (positive output).
"""

from __future__ import annotations
import time

from config import CFG


class SteeringController:
    """PID controller for lateral (steering) control."""

    def __init__(self) -> None:
        c = CFG.steering
        self.kp = c.kp
        self.ki = c.ki
        self.kd = c.kd
        self.out_min = c.output_min
        self.out_max = c.output_max
        self.deadband = c.deadband
        self.max_rate = c.max_rate

        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_output: float = 0.0
        self._prev_time: float = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_time = time.monotonic()

    def compute(self, target: float) -> float:
        """
        Compute steering output.
        `target` is the lane‑centre offset: -1 (left) … +1 (right).
        """
        now = time.monotonic()
        dt = now - self._prev_time
        if dt <= 0:
            dt = 1e-3
        self._prev_time = now

        error = target  # desired lane offset → 0 means centred

        # Deadband
        if abs(error) < self.deadband:
            error = 0.0

        # PID terms
        self._integral += error * dt
        # Anti‑windup clamp
        self._integral = max(-1.0, min(1.0, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        # Clamp
        output = max(self.out_min, min(self.out_max, output))

        # Rate limiting (smoothing)
        delta = output - self._prev_output
        if abs(delta) > self.max_rate:
            output = self._prev_output + self.max_rate * (1.0 if delta > 0 else -1.0)

        self._prev_output = output
        return output
