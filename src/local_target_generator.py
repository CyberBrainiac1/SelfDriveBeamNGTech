"""
local_target_generator.py — Generate a local driving target from the corridor estimate.

The target is a point on (or near) the corridor centre line at a speed-adaptive
lookahead distance, optionally biased toward a racing line.
"""

import math
from dataclasses import dataclass

import numpy as np

from corridor_detector import CorridorEstimate
from vehicle_state import VehicleState
from coordinate_transform import CoordinateTransform


@dataclass
class LocalTarget:
    """A local target point for the lateral controller."""
    target_x: float          # lateral offset in vehicle frame [m], positive = right
    target_y: float          # forward distance in vehicle frame [m]
    target_world_pos: np.ndarray  # (3,) world frame position
    heading_at_target: float  # path heading angle at target [rad]
    lookahead_m: float        # actual lookahead distance used
    valid: bool

    @classmethod
    def fallback(cls, lookahead_m: float = 18.0) -> "LocalTarget":
        """Straight-ahead fallback target."""
        return cls(
            target_x=0.0,
            target_y=lookahead_m,
            target_world_pos=np.zeros(3),
            heading_at_target=0.0,
            lookahead_m=lookahead_m,
            valid=False,
        )


class LocalTargetGenerator:
    """
    Generates a LocalTarget from a CorridorEstimate and the current VehicleState.

    Lookahead distance is speed-adaptive:
        lookahead = base + speed_mps * gain
        clamped to [min_m, max_m]

    An optional racing line bias offsets the target laterally:
        - Entry bias (outer edge on straight, apex on corner entry)
        - Exit bias (inside → outside on corner exit)
    """

    def __init__(self, config=None):
        # Lookahead parameters
        self.lookahead_base_m: float = 14.0
        self.lookahead_speed_gain: float = 0.62
        self.lookahead_min_m: float = 14.0
        self.lookahead_max_m: float = 55.0

        # Racing line bias (lateral offset as fraction of half-width)
        self.late_apex_entry_bias: float = 0.10
        self.exit_bias: float = 0.05
        self.racing_line_bias_gain: float = 0.78

        # Confidence scaling
        self.low_conf_scale: float = 0.74
        self.high_conf_scale: float = 1.14

        if config is not None:
            self._load_config(config)

    def _load_config(self, config) -> None:
        try:
            r = config.route
            self.lookahead_base_m = float(r.lookahead_base_m)
            self.lookahead_speed_gain = float(r.lookahead_speed_gain)
            self.lookahead_min_m = float(r.lookahead_min_m)
            self.lookahead_max_m = float(r.lookahead_max_m)
            self.late_apex_entry_bias = float(r.late_apex_entry_bias)
            self.exit_bias = float(r.exit_bias)
        except AttributeError:
            pass
        try:
            pc = config.probabilistic_control
            self.racing_line_bias_gain = float(pc.racing_line_bias_gain)
            self.low_conf_scale = float(pc.low_confidence_lookahead_scale)
            self.high_conf_scale = float(pc.high_confidence_lookahead_scale)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        corridor: CorridorEstimate,
        vehicle_state: VehicleState,
        confidence: float = 1.0,
        curvature: float = 0.0,
    ) -> LocalTarget:
        """
        Compute the local driving target.

        Parameters
        ----------
        corridor      : CorridorEstimate in vehicle frame
        vehicle_state : current VehicleState
        confidence    : combined confidence [0,1]
        curvature     : current curvature estimate (signed)

        Returns
        -------
        LocalTarget
        """
        if not corridor.valid or len(corridor.center_line) == 0:
            fallback_y = self._compute_lookahead(vehicle_state.speed_mps, confidence)
            tgt = LocalTarget.fallback(fallback_y)
            # Convert to world
            tgt.target_world_pos = self._to_world(0.0, fallback_y, vehicle_state)
            return tgt

        # Compute speed-adaptive lookahead
        lookahead = self._compute_lookahead(vehicle_state.speed_mps, confidence)

        # Find centre line point closest to the lookahead distance
        pts = corridor.center_line  # list of (x, y)
        tangents = corridor.tangents

        target_x, target_y, heading = self._interpolate_target(pts, tangents, lookahead)

        # Apply racing line bias
        mean_width = corridor.mean_width
        bias = self._compute_racing_bias(curvature, mean_width)
        target_x += bias * self.racing_line_bias_gain

        # World position
        world_pos = self._to_world(target_x, target_y, vehicle_state)

        return LocalTarget(
            target_x=target_x,
            target_y=target_y,
            target_world_pos=world_pos,
            heading_at_target=heading,
            lookahead_m=lookahead,
            valid=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_lookahead(self, speed_mps: float, confidence: float) -> float:
        """Speed and confidence-adaptive lookahead distance."""
        base = self.lookahead_base_m + speed_mps * self.lookahead_speed_gain
        # Scale by confidence
        if confidence < 0.4:
            base *= self.low_conf_scale
        elif confidence > 0.75:
            base *= self.high_conf_scale

        return max(self.lookahead_min_m, min(self.lookahead_max_m, base))

    def _interpolate_target(
        self,
        pts: list,
        tangents: list,
        lookahead: float,
    ) -> tuple:
        """
        Find the point on the centre line at distance *lookahead*.

        Returns (target_x, target_y, heading_rad).
        """
        # Compute cumulative arc length along the path
        # path is in vehicle frame: (x_lateral, y_forward)
        if len(pts) == 0:
            return 0.0, lookahead, 0.0

        # Arc lengths
        arc = [0.0]
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            arc.append(arc[-1] + math.sqrt(dx ** 2 + dy ** 2))

        total_len = arc[-1]

        if total_len == 0 or lookahead > total_len:
            # Return last point
            return float(pts[-1][0]), float(pts[-1][1]), float(tangents[-1])

        # Linear interpolation
        for i in range(1, len(arc)):
            if arc[i] >= lookahead:
                t = (lookahead - arc[i - 1]) / max(1e-6, arc[i] - arc[i - 1])
                x = pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0])
                y = pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1])
                h = tangents[i - 1] + t * (tangents[i] - tangents[i - 1])
                return float(x), float(y), float(h)

        return float(pts[-1][0]), float(pts[-1][1]), float(tangents[-1])

    def _compute_racing_bias(self, curvature: float, mean_width: float) -> float:
        """
        Compute a lateral racing line bias in metres.

        On straight segments: no bias.
        On corner entry: bias toward outside (late apex).
        On exit: bias toward inside.

        Positive bias = to the right (positive x in vehicle frame).
        """
        if abs(curvature) < 1e-4:
            return 0.0

        half_w = mean_width / 2.0
        # Direction: positive curvature = left turn → apex is on left → bias right (+x)
        sign = -1.0 if curvature > 0 else 1.0   # into corner → toward apex

        # Entry bias
        entry = sign * self.late_apex_entry_bias * half_w
        return entry

    @staticmethod
    def _to_world(
        target_x: float,
        target_y: float,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """Convert vehicle-frame target to world frame."""
        pt_v = np.array([[target_x, target_y, 0.0]])
        pt_w = CoordinateTransform.vehicle_to_world(pt_v, vehicle_state)
        return pt_w.reshape(3)
