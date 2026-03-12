"""
Tests for the ControlCommand and VehicleController clamping.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from beamng_interface.vehicle_control import ControlCommand


def test_clamp_in_range():
    cmd = ControlCommand(steering=0.5, throttle=0.3, brake=0.1)
    cmd.clamp()
    assert cmd.steering == 0.5
    assert cmd.throttle == 0.3
    assert cmd.brake == 0.1


def test_clamp_out_of_range():
    cmd = ControlCommand(steering=-2.0, throttle=1.5, brake=-0.5)
    cmd.clamp()
    assert cmd.steering == -1.0
    assert cmd.throttle == 1.0
    assert cmd.brake == 0.0
