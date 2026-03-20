"""
stanley_controller.py - Classic Stanley lateral controller.
"""

import math

from controllers.controller_base import ControllerBase, ControlOutput


class StanleyController(ControllerBase):
    """
    Stanley lateral controller.

    steering = e_heading + atan2(k * e_ct, v + k0)
    clamped and filtered.

    e_heading : heading error (path tangent vs vehicle heading) [rad]
    e_ct      : cross-track error (signed lateral distance from path) [m]
    v         : speed [m/s]
    k         : Stanley gain
    k0        : softening speed [m/s]
    """

    def __init__(self, config=None):
        self.wheelbase_m: float = 2.72
        self.gain: float = 1.10
        self.softening_kph: float = 45.0
        self.max_steer_rad: float = 0.60
        self.filter_alpha: float = 0.28
        self.rate_limit: float = 0.08

        if config is not None:
            self._load_config(config)

        self._prev_steer: float = 0.0

    def _load_config(self, config) -> None:
        try:
            c = config.controllers
            self.wheelbase_m = float(c.wheelbase_m)
            self.max_steer_rad = float(c.max_steer_rad)
            self.filter_alpha = float(c.steering_filter_alpha)
            self.rate_limit = float(c.steering_rate_limit)
            self.gain = float(c.stanley.gain)
            self.softening_kph = float(c.stanley.softening_kph)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # ControllerBase
    # ------------------------------------------------------------------

    def compute(self, vehicle_state, local_target, **kwargs) -> ControlOutput:
        """
        Compute Stanley steering command.

        Parameters
        ----------
        vehicle_state : VehicleState
        local_target  : LocalTarget
            target_x         : cross-track error [m] (positive = right of path)
            heading_at_target: path heading [rad]
        """
        speed_mps = max(0.1, vehicle_state.speed_mps)
        k0_mps = self.softening_kph / 3.6

        # Cross-track error: positive = vehicle is to right of path
        # target_x is lateral offset of path centre from vehicle - negate for CTE
        e_ct = -local_target.target_x

        # Heading error: path heading minus vehicle heading
        # Both in vehicle frame; heading_at_target is the path tangent angle
        e_heading = local_target.heading_at_target   # already in vehicle frame angle

        # Stanley formula
        steer_rad = e_heading + math.atan2(self.gain * e_ct, speed_mps + k0_mps)

        # Clamp to steering range
        steer_rad = max(-self.max_steer_rad, min(self.max_steer_rad, steer_rad))

        # Normalise to [-1, 1]
        steer_norm = steer_rad / self.max_steer_rad
        steer_norm = max(-1.0, min(1.0, steer_norm))

        # Rate limit
        steer_norm = self._apply_rate_limit(steer_norm, self._prev_steer, self.rate_limit)

        # EMA filter
        steer_norm = self.filter_alpha * steer_norm + (1.0 - self.filter_alpha) * self._prev_steer
        steer_norm = max(-1.0, min(1.0, steer_norm))

        self._prev_steer = steer_norm

        return ControlOutput(
            steering=steer_norm,
            throttle=0.0,
            brake=0.0,
            notes={
                "e_ct": e_ct,
                "e_heading": e_heading,
                "steer_rad": steer_rad,
            },
        )

    def reset(self) -> None:
        self._prev_steer = 0.0

    @staticmethod
    def _apply_rate_limit(new_val: float, prev_val: float, limit: float) -> float:
        delta = new_val - prev_val
        delta = max(-limit, min(limit, delta))
        return prev_val + delta
