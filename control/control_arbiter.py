"""
control_arbiter.py
==================
Merges steering + speed outputs and dispatches to either vJoy (smooth
analog) or DirectInput keys (WASD fallback), depending on config.

This is the only place that actually sends input to the game.
"""

from __future__ import annotations
from dataclasses import dataclass

from config import CFG
from control.direct_keys import (
    press, release, release_all,
    W, A, S, D,
)
from control.vjoy_output import VJoyOutput
from control.steering_controller import SteeringController
from control.speed_controller import SpeedController


@dataclass
class ControlCommand:
    steering: float = 0.0   # -1 … +1
    throttle: float = 0.0   # 0  … 1
    brake:    float = 0.0   # 0  … 1
    estop:    bool  = False


class ControlArbiter:
    """Compute and dispatch control every tick."""

    def __init__(self) -> None:
        self.steer_ctrl = SteeringController()
        self.speed_ctrl = SpeedController()
        self._vjoy = VJoyOutput(CFG.control_out.vjoy_device_id)

        self._use_vjoy = False
        if CFG.control_out.mode == "vjoy":
            self._use_vjoy = self._vjoy.open()
            if not self._use_vjoy:
                print("[arbiter] Falling back to keyboard (WASD) mode.")

    # ── public API ─────────────────────────────────────────────────
    def compute(
        self,
        steer_target: float,
        speed_target_kph: float,
        current_kph: float,
        estop: bool = False,
    ) -> ControlCommand:
        if estop:
            return ControlCommand(estop=True)

        steering = self.steer_ctrl.compute(steer_target)
        throttle, brake = self.speed_ctrl.compute(speed_target_kph, current_kph)
        return ControlCommand(steering=steering, throttle=throttle, brake=brake)

    def apply(self, cmd: ControlCommand) -> None:
        """Send the command to the game."""
        if cmd.estop:
            release_all()
            if self._use_vjoy:
                self._vjoy.reset()
            return

        if self._use_vjoy:
            self._apply_vjoy(cmd)
        else:
            self._apply_keys(cmd)

    def shutdown(self) -> None:
        release_all()
        if self._use_vjoy:
            self._vjoy.close()

    # ── internals ─────────────────────────────────────────────────
    def _apply_vjoy(self, cmd: ControlCommand) -> None:
        self._vjoy.set(cmd.steering, cmd.throttle, cmd.brake)

    def _apply_keys(self, cmd: ControlCommand) -> None:
        """
        Map continuous values to key presses.
        Not as smooth as vJoy, but works with no extra drivers.
        """
        cfg = CFG.control_out
        thr = cmd.throttle
        brk = cmd.brake
        steer = cmd.steering

        # Throttle / brake
        if thr > cfg.gas_key_threshold:
            press(W)
        else:
            release(W)

        if brk > cfg.gas_key_threshold:
            press(S)
        else:
            release(S)

        # Steering
        if steer < -cfg.steer_key_threshold:
            press(A)
            release(D)
        elif steer > cfg.steer_key_threshold:
            press(D)
            release(A)
        else:
            release(A)
            release(D)
