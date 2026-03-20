"""
safety_manager.py — Monitor vehicle safety conditions and override control if needed.
"""

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from vehicle_state import VehicleState
from controllers.controller_base import ControlOutput


class SafetyState(Enum):
    NORMAL = auto()
    RECOVERY = auto()
    EMERGENCY_STOP = auto()


@dataclass
class SafetyStatus:
    state: SafetyState
    message: str
    override_steering: Optional[float] = None
    override_throttle: Optional[float] = None
    override_brake: Optional[float] = None
    should_stop: bool = False

    @property
    def is_safe(self) -> bool:
        return self.state == SafetyState.NORMAL


class SafetyManager:
    """
    Monitor vehicle health and driving safety.  Can override control outputs
    or signal an emergency stop.

    Monitored conditions:
    - Damage exceeds threshold (after grace period)
    - Speed exceeds hard limit
    - Heading error exceeds emergency threshold
    - Cross-track error exceeds emergency threshold
    - No valid target for too many consecutive ticks
    """

    def __init__(self, config=None):
        self.max_damage: float = 250.0
        self.max_speed_kph: float = 150.0
        self.emergency_heading_error_deg: float = 45.0
        self.emergency_cross_track_m: float = 5.0
        self.no_target_grace_ticks: int = 12
        self.damage_grace_seconds: float = 20.0
        self.clamp_steering: float = 1.0
        self.clamp_throttle: float = 1.0
        self.clamp_brake: float = 1.0

        if config is not None:
            self._load_config(config)

        self._state: SafetyState = SafetyState.NORMAL
        self._no_target_ticks: int = 0
        self._start_time: float = time.monotonic()
        self._damage_grace_start: Optional[float] = None
        self._consecutive_safe: int = 0

    def _load_config(self, config) -> None:
        try:
            s = config.safety
            self.max_damage = float(s.max_damage)
            self.max_speed_kph = float(s.max_speed_kph)
            self.emergency_heading_error_deg = float(s.emergency_heading_error_deg)
            self.emergency_cross_track_m = float(s.emergency_cross_track_m)
            self.no_target_grace_ticks = int(s.no_target_grace_ticks)
            self.damage_grace_seconds = float(s.damage_grace_seconds)
            self.clamp_steering = float(s.clamp_steering)
            self.clamp_throttle = float(s.clamp_throttle)
            self.clamp_brake = float(s.clamp_brake)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        vehicle_state: VehicleState,
        target=None,
        control_output: ControlOutput = None,
    ) -> SafetyStatus:
        """
        Evaluate current safety conditions.

        Parameters
        ----------
        vehicle_state  : VehicleState
        target         : LocalTarget or None
        control_output : ControlOutput (for clamping)

        Returns
        -------
        SafetyStatus
        """
        now = time.monotonic()
        elapsed = now - self._start_time

        # --- No valid target ---
        if target is None or not target.valid:
            self._no_target_ticks += 1
            if self._no_target_ticks > self.no_target_grace_ticks:
                return SafetyStatus(
                    state=SafetyState.RECOVERY,
                    message=f"No valid target for {self._no_target_ticks} ticks",
                    override_throttle=0.0,
                    override_brake=0.0,
                )
        else:
            self._no_target_ticks = 0

        # --- Speed limit ---
        if vehicle_state.speed_kph > self.max_speed_kph:
            return SafetyStatus(
                state=SafetyState.RECOVERY,
                message=f"Speed {vehicle_state.speed_kph:.1f} kph exceeds limit {self.max_speed_kph}",
                override_throttle=0.0,
                override_brake=0.8,
            )

        # --- Damage (with grace period) ---
        if vehicle_state.damage > 0:
            if self._damage_grace_start is None:
                self._damage_grace_start = now
            damage_age = now - self._damage_grace_start
            if vehicle_state.damage > self.max_damage and damage_age > self.damage_grace_seconds:
                return SafetyStatus(
                    state=SafetyState.EMERGENCY_STOP,
                    message=f"Damage {vehicle_state.damage:.0f} exceeds limit",
                    override_throttle=0.0,
                    override_brake=1.0,
                    should_stop=True,
                )
        else:
            self._damage_grace_start = None

        # --- Heading error (if target available) ---
        if target is not None and target.valid:
            import math
            heading_err_deg = math.degrees(abs(target.heading_at_target))
            if heading_err_deg > self.emergency_heading_error_deg:
                return SafetyStatus(
                    state=SafetyState.RECOVERY,
                    message=f"Heading error {heading_err_deg:.1f}° exceeds limit",
                    override_throttle=0.0,
                    override_brake=0.3,
                )

            # Cross-track error
            cross_track = abs(target.target_x)
            if cross_track > self.emergency_cross_track_m:
                return SafetyStatus(
                    state=SafetyState.RECOVERY,
                    message=f"Cross-track error {cross_track:.1f}m exceeds limit",
                    override_throttle=0.0,
                    override_brake=0.2,
                )

        # --- Clamp control if provided ---
        if control_output is not None:
            self._clamp_output(control_output)

        return SafetyStatus(state=SafetyState.NORMAL, message="OK")

    def is_safe(self) -> bool:
        return self._state == SafetyState.NORMAL

    def reset(self) -> None:
        self._state = SafetyState.NORMAL
        self._no_target_ticks = 0
        self._damage_grace_start = None
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clamp_output(self, out: ControlOutput) -> None:
        out.steering = max(-self.clamp_steering, min(self.clamp_steering, out.steering))
        out.throttle = max(0.0, min(self.clamp_throttle, out.throttle))
        out.brake = max(0.0, min(self.clamp_brake, out.brake))
