"""
mpcc_inspired_controller.py — MPCC-inspired lateral controller.

A practical implementation inspired by Model Predictive Contouring Control.
Rather than solving a full optimal control problem at each step, we:
1. Project the vehicle onto the reference path (corridor centre line).
2. Compute contour error (cross-track) and lag error (along-track deviation).
3. Compute heading error.
4. Add curvature feedforward.
5. Weight and combine into a steering command.
6. Apply commitment factor scaling.

This gives the key benefits of MPCC (smooth contouring + progress tracking)
without the computational cost of a full OCP solver.
"""

import math
from typing import List, Tuple

import numpy as np

from controllers.controller_base import ControllerBase, ControlOutput


class MPCCInspiredController(ControllerBase):
    """
    MPCC-inspired lateral controller.

    Key parameters (from config.controllers.mpcc_inspired):
        contour_gain    : weight on cross-track error
        lag_gain        : weight on along-path deviation
        heading_gain    : weight on heading error
        feedforward_gain: weight on curvature feedforward
        softening_kph   : speed for softening (avoid divide-by-zero)
        candidate_count : number of lateral offset candidates to evaluate
        max_offset_m    : max lateral offset to evaluate [m]
    """

    def __init__(self, config=None):
        # Control gains
        self.contour_gain: float = 2.6
        self.lag_gain: float = 0.18
        self.heading_gain: float = 0.95
        self.feedforward_gain: float = 1.05

        # Vehicle params
        self.wheelbase_m: float = 2.72
        self.max_steer_rad: float = 0.60
        self.softening_kph: float = 32.0

        # Path/candidate params
        self.path_point_spacing_m: float = 6.0
        self.candidate_count: int = 9
        self.max_offset_m: float = 1.8

        # Weights for candidate scoring
        self.contour_weight: float = 0.90
        self.lag_weight: float = 0.18
        self.smoothness_weight: float = 5.0
        self.curvature_weight: float = 3.2
        self.clearance_weight: float = 0.55
        self.clearance_radius_m: float = 2.4

        # Filters
        self.filter_alpha: float = 0.28
        self.rate_limit: float = 0.08

        # Stiffness factor Kv for speed-dependent steering
        self.Kv: float = 0.0002  # empirical

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

            m = c.mpcc_inspired
            self.contour_gain = float(m.contour_gain)
            self.lag_gain = float(m.lag_gain)
            self.heading_gain = float(m.heading_gain)
            self.feedforward_gain = float(m.feedforward_gain)
            self.softening_kph = float(m.softening_kph)
            self.path_point_spacing_m = float(m.path_point_spacing_m)
            self.candidate_count = int(m.candidate_count)
            self.max_offset_m = float(m.max_offset_m)
            self.contour_weight = float(m.contour_weight)
            self.lag_weight = float(m.lag_weight)
            self.smoothness_weight = float(m.smoothness_weight)
            self.curvature_weight = float(m.curvature_weight)
            self.clearance_weight = float(m.clearance_weight)
            self.clearance_radius_m = float(m.clearance_radius_m)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # ControllerBase
    # ------------------------------------------------------------------

    def compute(self, vehicle_state, local_target, **kwargs) -> ControlOutput:
        """
        Compute MPCC-inspired steering command.

        Parameters
        ----------
        vehicle_state : VehicleState
        local_target  : LocalTarget (target_x, target_y, heading_at_target)

        Keyword args
        ------------
        corridor       : CorridorEstimate (optional, for full path)
        curvature_est  : CurvatureEstimate
        commitment     : float commitment factor [0,1]
        """
        corridor = kwargs.get("corridor", None)
        curvature_est = kwargs.get("curvature_est", None)
        commitment = float(kwargs.get("commitment", 0.80))

        speed_mps = max(0.1, vehicle_state.speed_mps)
        speed_kph = speed_mps * 3.6

        # Build reference path from corridor if available, else use target point
        path = self._build_path(corridor, local_target)

        # Project vehicle onto path (vehicle is at origin of vehicle frame)
        proj_x, proj_y, proj_idx = self._project_on_path(path)

        # Errors
        e_contour, e_lag, e_heading = self._compute_errors(
            path, proj_idx, proj_x, proj_y, local_target
        )

        # Curvature feedforward
        kappa = 0.0
        if curvature_est is not None and curvature_est.valid:
            kappa = curvature_est.curvature

        # Ackermann-style feedforward: steer = kappa * L / (1 + v^2 * Kv)
        steer_ff = kappa * self.wheelbase_m / (1.0 + speed_mps ** 2 * self.Kv)

        # Primary steering command
        softening_mps = self.softening_kph / 3.6
        speed_factor = 1.0 / max(speed_mps / softening_mps, 1.0)

        steer_lat = (
            self.contour_gain * e_contour * speed_factor
            + self.lag_gain * e_lag
            + self.heading_gain * e_heading
            + self.feedforward_gain * steer_ff
        )

        # Apply commitment factor to the reactive lateral correction
        # (feedforward is always fully applied)
        reactive_steer = (
            self.contour_gain * e_contour * speed_factor
            + self.lag_gain * e_lag
            + self.heading_gain * e_heading
        )
        full_steer = reactive_steer * commitment + self.feedforward_gain * steer_ff

        # Convert to normalised [-1, 1]
        steer_norm = full_steer / self.max_steer_rad
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
                "e_contour": e_contour,
                "e_lag": e_lag,
                "e_heading": e_heading,
                "steer_ff": steer_ff,
                "kappa": kappa,
                "commitment": commitment,
            },
        )

    def reset(self) -> None:
        self._prev_steer = 0.0

    # ------------------------------------------------------------------
    # Path projection helpers
    # ------------------------------------------------------------------

    def _build_path(self, corridor, local_target) -> List[Tuple[float, float, float]]:
        """
        Build a list of (x, y, heading) path points in vehicle frame.

        Uses corridor centre line if available, otherwise creates a simple
        straight path to the target.
        """
        path = []

        if corridor is not None and corridor.valid and len(corridor.center_line) >= 2:
            pts = corridor.center_line
            tans = corridor.tangents
            for i, (pt, tan) in enumerate(zip(pts, tans)):
                path.append((float(pt[0]), float(pt[1]), float(tan)))
        else:
            # Synthesise a short path from vehicle to target
            tx = float(local_target.target_x)
            ty = float(local_target.target_y)
            heading = float(local_target.heading_at_target)
            n = max(3, int(ty / self.path_point_spacing_m))
            for i in range(n + 1):
                t = i / max(n, 1)
                path.append((tx * t, ty * t, heading * t))

        return path

    def _project_on_path(
        self, path: List[Tuple[float, float, float]]
    ) -> Tuple[float, float, int]:
        """
        Find the nearest point on the path to the vehicle origin (0, 0).

        Returns (proj_x, proj_y, idx) — the projected point and segment index.
        """
        if len(path) == 0:
            return 0.0, 0.0, 0

        best_dist = float("inf")
        best_idx = 0
        best_proj = (0.0, 0.0)

        for i in range(len(path) - 1):
            x0, y0, _ = path[i]
            x1, y1, _ = path[i + 1]

            dx = x1 - x0
            dy = y1 - y0
            seg_len_sq = dx * dx + dy * dy

            if seg_len_sq < 1e-8:
                t = 0.0
            else:
                t = max(0.0, min(1.0, (-x0 * dx + -y0 * dy) / seg_len_sq))

            px = x0 + t * dx
            py = y0 + t * dy
            dist = math.sqrt(px ** 2 + py ** 2)

            if dist < best_dist:
                best_dist = dist
                best_idx = i
                best_proj = (px, py)

        return best_proj[0], best_proj[1], best_idx

    def _compute_errors(
        self,
        path: List[Tuple[float, float, float]],
        proj_idx: int,
        proj_x: float,
        proj_y: float,
        local_target,
    ) -> Tuple[float, float, float]:
        """
        Compute (e_contour, e_lag, e_heading) errors.

        e_contour : signed cross-track error (negative = vehicle left of path)
        e_lag     : along-path lag error (positive = vehicle behind path)
        e_heading : heading error relative to path tangent [rad]
        """
        if len(path) == 0:
            return (
                -float(local_target.target_x),
                0.0,
                float(local_target.heading_at_target),
            )

        # Get path tangent at projection point
        idx = min(proj_idx, len(path) - 1)
        _, _, path_heading = path[idx]

        # Contour error: perpendicular distance from vehicle (0,0) to path
        # Positive = vehicle to the right of path (path needs to steer left)
        # Vehicle is at (0,0); projected point is (proj_x, proj_y)
        # Contour error = signed perpendicular distance
        # Normal to tangent: (-sin(heading), cos(heading))
        nx = -math.sin(path_heading)
        ny = math.cos(path_heading)
        # Vector from proj to vehicle (0,0)
        vx = 0.0 - proj_x
        vy = 0.0 - proj_y
        # Positive = vehicle is left of path (path tangent in +y, left = -x)
        e_contour = -(vx * nx + vy * ny)

        # Lag error: forward distance to target
        # Positive = target is ahead (normal operation)
        tx = math.cos(path_heading)
        ty = math.sin(path_heading)
        e_lag = -(vx * tx + vy * ty)

        # Heading error: path tangent vs vehicle heading (vehicle heading = 0 in vehicle frame)
        e_heading = path_heading  # path heading relative to vehicle (vehicle heading = 0)

        return float(e_contour), float(e_lag), float(e_heading)

    @staticmethod
    def _apply_rate_limit(new_val: float, prev_val: float, limit: float) -> float:
        delta = new_val - prev_val
        delta = max(-limit, min(limit, delta))
        return prev_val + delta
