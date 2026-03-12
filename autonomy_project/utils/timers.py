"""
Simple timing helpers for measuring loop and stage durations.
"""

from __future__ import annotations
import time
from collections import defaultdict
from typing import Dict


class TickTimer:
    """Measures durations of named stages within a tick."""

    def __init__(self) -> None:
        self._starts: Dict[str, float] = {}
        self._durations: Dict[str, float] = defaultdict(float)

    def start(self, name: str) -> None:
        self._starts[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        elapsed = time.perf_counter() - self._starts.get(name, time.perf_counter())
        self._durations[name] = elapsed
        return elapsed

    def get_ms(self, name: str) -> float:
        return self._durations.get(name, 0.0) * 1000.0

    def summary(self) -> str:
        parts = [f"{k}={v * 1000:.1f}ms" for k, v in self._durations.items()]
        return "  ".join(parts)

    def reset(self) -> None:
        self._starts.clear()
        self._durations.clear()


class RateTracker:
    """Tracks and reports loop frequency."""

    def __init__(self, window: int = 30) -> None:
        self._window = window
        self._times: list[float] = []

    def tick(self) -> None:
        self._times.append(time.perf_counter())
        if len(self._times) > self._window + 1:
            self._times = self._times[-self._window - 1:]

    @property
    def hz(self) -> float:
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        if span == 0:
            return 0.0
        return (len(self._times) - 1) / span
