"""
Tests for the speed controller (offline, no BeamNG needed).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control.speed_controller import SpeedController


def test_at_target_speed_returns_coast():
    ctrl = SpeedController()
    throttle, brake = ctrl.compute(40.0, 40.0)
    assert throttle == 0.0
    assert brake == 0.0


def test_below_target_gives_throttle():
    ctrl = SpeedController()
    throttle, brake = ctrl.compute(40.0, 20.0)
    assert throttle > 0.0
    assert brake == 0.0


def test_above_target_gives_brake():
    ctrl = SpeedController()
    throttle, brake = ctrl.compute(40.0, 60.0)
    assert throttle == 0.0
    assert brake > 0.0


def test_output_bounded():
    ctrl = SpeedController()
    throttle, brake = ctrl.compute(40.0, 0.0)
    assert 0.0 <= throttle <= 1.0
    assert 0.0 <= brake <= 1.0
