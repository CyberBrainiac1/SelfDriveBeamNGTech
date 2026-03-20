"""
Tests for math_utils.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.math_utils import clamp, lerp, wrap_angle, mps_to_kph, distance_2d


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(15, 0, 10) == 10


def test_lerp():
    assert lerp(0, 10, 0.5) == 5.0
    assert lerp(0, 10, 0.0) == 0.0
    assert lerp(0, 10, 1.0) == 10.0
    # clamp outside range
    assert lerp(0, 10, 2.0) == 10.0


def test_wrap_angle():
    assert wrap_angle(0) == 0
    assert wrap_angle(360) == 0
    assert wrap_angle(-180) == -180
    assert abs(wrap_angle(270) - (-90)) < 1e-9


def test_mps_to_kph():
    assert abs(mps_to_kph(1.0) - 3.6) < 1e-9


def test_distance_2d():
    assert abs(distance_2d((0, 0), (3, 4)) - 5.0) < 1e-9
