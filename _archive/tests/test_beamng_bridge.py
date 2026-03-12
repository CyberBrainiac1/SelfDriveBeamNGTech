"""
tests/test_beamng_bridge.py — Tests for BeamNGBridge steer↔angle conversion.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop_app"))


def make_bridge():
    serial_mock = MagicMock()
    serial_mock.is_connected = True

    safety_mock = MagicMock()
    safety_mock.clamp_target = lambda x: max(-540.0, min(540.0, x))

    config_mock = MagicMock()
    config_mock.get = lambda key, default=None: {
        "beamng.steer_scale": 1.0,
        "wheel.angle_range": 540.0,
        "beamng.safety_max_angle": 450.0,
    }.get(key, default)

    from beamng.beamng_bridge import BeamNGBridge
    bridge = BeamNGBridge(serial_mock, safety_mock, config_mock)
    bridge.configure_from_config()
    return bridge, serial_mock, safety_mock


def test_normalized_to_angle():
    bridge, _, _ = make_bridge()
    # With range=540, half=270
    assert bridge.normalized_to_angle(0.0) == pytest.approx(0.0)
    assert bridge.normalized_to_angle(1.0) == pytest.approx(270.0)
    assert bridge.normalized_to_angle(-1.0) == pytest.approx(-270.0)
    assert bridge.normalized_to_angle(0.5) == pytest.approx(135.0)


def test_angle_to_normalized():
    bridge, _, _ = make_bridge()
    assert bridge.angle_to_normalized(0.0) == pytest.approx(0.0)
    assert bridge.angle_to_normalized(270.0) == pytest.approx(1.0)
    assert bridge.angle_to_normalized(-270.0) == pytest.approx(-1.0)
    # Clamped
    assert bridge.angle_to_normalized(999.0) == pytest.approx(1.0)


def test_roundtrip():
    bridge, _, _ = make_bridge()
    for norm in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        angle = bridge.normalized_to_angle(norm)
        back = bridge.angle_to_normalized(angle)
        assert back == pytest.approx(norm, abs=1e-6)


def test_process_vehicle_state_sends_target(tmp_path):
    """process_vehicle_state should send correct target to serial."""
    bridge, serial_mock, _ = make_bridge()
    bridge.activate()
    state = {"steering_input": 0.5}
    bridge.process_vehicle_state(state)
    # 0.5 * 270 = 135°
    serial_mock.set_target.assert_called_with(pytest.approx(135.0))


def test_deactivate_sends_zero():
    bridge, serial_mock, _ = make_bridge()
    bridge.activate()
    bridge.deactivate()
    serial_mock.set_target.assert_called_with(0.0)


def test_inactive_bridge_does_not_send():
    bridge, serial_mock, _ = make_bridge()
    # bridge not activated
    bridge.process_vehicle_state({"steering_input": 0.5})
    serial_mock.set_target.assert_not_called()
