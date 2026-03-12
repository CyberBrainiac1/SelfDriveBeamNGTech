"""
test_controllers.py
===================
Unit tests for PID steering and speed controllers.
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from control.steering_controller import SteeringController
from control.speed_controller import SpeedController


class TestSteeringController:
    def setup_method(self) -> None:
        self.ctrl = SteeringController()

    def test_zero_target_returns_near_zero(self) -> None:
        out = self.ctrl.compute(0.0)
        assert abs(out) < 0.1

    def test_positive_target_positive_output(self) -> None:
        for _ in range(5):
            out = self.ctrl.compute(0.5)
        assert out > 0.0

    def test_negative_target_negative_output(self) -> None:
        for _ in range(5):
            out = self.ctrl.compute(-0.5)
        assert out < 0.0

    def test_output_clamped(self) -> None:
        for _ in range(20):
            out = self.ctrl.compute(9999.0)
        assert out <= 1.0

    def test_reset_zeroes_integral(self) -> None:
        for _ in range(10):
            self.ctrl.compute(1.0)
        self.ctrl.reset()
        assert self.ctrl._integral == 0.0


class TestSpeedController:
    def setup_method(self) -> None:
        self.ctrl = SpeedController()

    def test_coast_in_band(self) -> None:
        thr, brk = self.ctrl.compute(50.0, 50.0)
        assert thr == 0.0 and brk == 0.0

    def test_too_slow_gives_throttle(self) -> None:
        thr, brk = self.ctrl.compute(80.0, 20.0)
        assert thr > 0.0
        assert brk == 0.0

    def test_too_fast_gives_brake(self) -> None:
        thr, brk = self.ctrl.compute(20.0, 80.0)
        assert brk > 0.0
        assert thr == 0.0

    def test_outputs_in_range(self) -> None:
        thr, brk = self.ctrl.compute(60.0, 0.0)
        assert 0.0 <= thr <= 1.0
        assert 0.0 <= brk <= 1.0

    def test_reset_clears_state(self) -> None:
        for _ in range(10):
            self.ctrl.compute(100.0, 0.0)
        self.ctrl.reset()
        assert self.ctrl._integral == 0.0
