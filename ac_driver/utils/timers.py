"""
timers.py
=========
Simple rate-limiter and FPS counter for the main loop.
"""

from __future__ import annotations
import time
from collections import deque


class RateLimiter:
    """Block until the target loop period has elapsed."""

    def __init__(self, target_hz: float) -> None:
        self._period = 1.0 / target_hz
        self._last = time.monotonic()

    def wait(self) -> float:
        """Wait until the next tick.  Returns actual elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last
        remaining = self._period - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last = time.monotonic()
        return self._last - (now - elapsed)


class FPSCounter:
    """Rolling-average FPS counter."""

    def __init__(self, window: int = 30) -> None:
        self._times: deque = deque(maxlen=window)
        self._last = time.monotonic()

    def tick(self) -> float:
        now = time.monotonic()
        self._times.append(now - self._last)
        self._last = now
        if len(self._times) < 2:
            return 0.0
        return 1.0 / (sum(self._times) / len(self._times))
