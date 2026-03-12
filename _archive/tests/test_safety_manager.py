"""
tests/test_safety_manager.py — Unit tests for SafetyManager.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop_app"))

from core.safety_manager import SafetyManager


@pytest.fixture
def safety():
    serial_mock = MagicMock()
    serial_mock.is_connected = True
    logger_mock = MagicMock()
    sm = SafetyManager(serial_mock, logger_mock)
    return sm


def test_initial_state(safety):
    assert not safety.estop_active
    assert not safety.ai_mode_active


def test_trigger_estop(safety):
    safety.trigger_estop("test")
    assert safety.estop_active
    assert not safety.ai_mode_active
    safety._serial.estop.assert_called_once()


def test_clear_estop(safety):
    safety.trigger_estop("test")
    safety.clear_estop()
    assert not safety.estop_active


def test_clamp_target(safety):
    safety.configure(max_angle=540.0)
    assert safety.clamp_target(600.0) == pytest.approx(540.0)
    assert safety.clamp_target(-700.0) == pytest.approx(-540.0)
    assert safety.clamp_target(100.0) == pytest.approx(100.0)


def test_validate_target(safety):
    safety.configure(max_angle=540.0)
    assert safety.validate_target(400.0)
    assert not safety.validate_target(600.0)
    assert not safety.validate_target(-600.0)


def test_validate_ai_rate(safety):
    safety.configure(max_ai_rate=180.0)
    # 90° change in 1s = 90 °/s → OK
    assert safety.validate_ai_rate(0.0, 90.0, dt=1.0)
    # 270° change in 1s = 270 °/s → too fast
    assert not safety.validate_ai_rate(0.0, 270.0, dt=1.0)


def test_enter_ai_mode_blocked_when_estop(safety):
    safety.trigger_estop("test")
    assert not safety.enter_ai_mode()


def test_enter_ai_mode_blocked_when_disconnected():
    serial_mock = MagicMock()
    serial_mock.is_connected = False
    logger_mock = MagicMock()
    sm = SafetyManager(serial_mock, logger_mock)
    assert not sm.enter_ai_mode()


def test_enter_and_exit_ai_mode(safety):
    assert safety.enter_ai_mode()
    assert safety.ai_mode_active
    safety.exit_ai_mode()
    assert not safety.ai_mode_active
