"""
Math helpers — clamping, interpolation, angle wrapping, etc.
"""

from __future__ import annotations
import math


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation: a when t=0, b when t=1."""
    return a + (b - a) * clamp(t, 0.0, 1.0)


def wrap_angle(deg: float) -> float:
    """Wrap an angle to [-180, 180]."""
    return (deg + 180) % 360 - 180


def mps_to_kph(mps: float) -> float:
    return mps * 3.6


def kph_to_mps(kph: float) -> float:
    return kph / 3.6


def distance_2d(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
