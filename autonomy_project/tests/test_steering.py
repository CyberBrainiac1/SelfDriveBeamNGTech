"""
Tests for the PID steering controller (offline, no BeamNG needed).
"""
import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control.steering_controller import SteeringController
from config import CFG


def test_zero_error_gives_zero_output():
    ctrl = SteeringController()
    out = ctrl.compute(0.0)
    assert abs(out) < 0.01


def test_positive_error_gives_positive_output():
    ctrl = SteeringController()
    # Feed a constant positive error for several ticks
    for _ in range(5):
        out = ctrl.compute(0.5)
        time.sleep(0.01)
    assert out > 0.0


def test_output_clamped():
    ctrl = SteeringController()
    # Very large error
    for _ in range(50):
        out = ctrl.compute(10.0)
        time.sleep(0.001)
    assert -1.0 <= out <= 1.0


def test_rate_limiting():
    ctrl = SteeringController()
    _ = ctrl.compute(0.0)
    time.sleep(0.01)
    # Sudden large jump
    out = ctrl.compute(1.0)
    # Output should be limited by max_rate
    assert abs(out) <= CFG.steering.max_rate + 0.01
