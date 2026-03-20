"""
pure_pursuit_controller.py — Classic Pure Pursuit lateral controller.
"""

import math

from controllers.controller_base import ControllerBase, ControlOutput


class PurePursuitController(ControllerBase):
    """
    Classic Pure Pursuit controller.

    Computes steering angle from the angle to the lookahead target point
    in vehicle frame.

    steering = atan2(2 * L * sin(alpha), ld) * gain / max_steer_rad
    clamped to [-1, 1].
    """

    def __init__(self, config=None):
        self.wheelbase_m: float = 2.72
        self.gain: float = 0.92
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
            self.gain = float(c.pure_pursuit.gain)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # ControllerBase
    # ------------------------------------------------------------------

    def compute(self, vehicle_state, local_target, **kwargs) -> ControlOutput:
        """
        Compute Pure Pursuit steering command.

        Parameters
        ----------
        vehicle_state : VehicleState
        local_target  : LocalTarget (target_x, target_y in vehicle frame)
        """
        tx = local_target.target_x
        ty = local_target.target_y
        ld = local_target.lookahead_m

        # Angle to target in vehicle frame
        # alpha = atan2(lateral_offset, forward_distance)
        alpha = math.atan2(tx, max(ty, 0.1))

        # Pure pursuit steering angle (radians)
        L = self.wheelbase_m
        steer_rad = math.atan2(2.0 * L * math.sin(alpha), max(ld, 0.1))

        # Normalise to [-1, 1] via max steer angle, apply gain
        steer_norm = (steer_rad / self.max_steer_rad) * self.gain
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
            notes={"alpha_rad": alpha, "steer_rad": steer_rad},
        )

    def reset(self) -> None:
        self._prev_steer = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_rate_limit(new_val: float, prev_val: float, limit: float) -> float:
        delta = new_val - prev_val
        delta = max(-limit, min(limit, delta))
        return prev_val + delta
