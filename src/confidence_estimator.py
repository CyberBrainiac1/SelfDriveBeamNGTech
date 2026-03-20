"""
confidence_estimator.py — Estimate perception confidence from multiple signals.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, List

import numpy as np

from boundary_fitter import CorridorBounds
from local_curvature_estimator import CurvatureEstimate


@dataclass
class ConfidenceEstimate:
    """Multi-factor confidence estimate for the current perception state."""
    geometry_confidence: float    # [0,1] from point count + fit quality
    temporal_confidence: float    # [0,1] consistency over time
    corridor_confidence: float    # [0,1] from width stability
    combined_confidence: float    # [0,1] weighted combination
    point_density_ratio: float    # actual / target point count


class ConfidenceEstimator:
    """
    Estimate perception confidence from corridor bounds and curvature history.

    geometry_confidence  = f(point_count, fit_residual)
    temporal_confidence  = f(curvature consistency over last N frames)
    corridor_confidence  = f(width stability)
    combined             = weighted average
    """

    _HISTORY_LEN = 12

    def __init__(self, config=None):
        # Calibration targets
        self.point_count_target: int = 200
        self.residual_scale: float = 1.0
        self.width_confidence_scale: float = 0.9
        self.temporal_confidence_scale: float = 0.7

        # Weights for combined score
        self.w_geometry: float = 0.45
        self.w_temporal: float = 0.30
        self.w_corridor: float = 0.25

        if config is not None:
            self._load_config(config)

        self._curvature_history: Deque[float] = deque(maxlen=self._HISTORY_LEN)
        self._width_history: Deque[float] = deque(maxlen=self._HISTORY_LEN)

    def _load_config(self, config) -> None:
        try:
            cal = config.calibration
            self.point_count_target = int(cal.point_count_target)
        except AttributeError:
            pass
        try:
            g = config.geometry
            self.residual_scale = float(g.residual_confidence_scale_m)
            self.width_confidence_scale = float(g.width_confidence_scale_m)
            self.temporal_confidence_scale = float(g.temporal_confidence_scale)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(
        self,
        bounds: CorridorBounds,
        curvature_est: CurvatureEstimate,
        point_count: int = 0,
    ) -> ConfidenceEstimate:
        """
        Compute confidence estimate.

        Parameters
        ----------
        bounds        : CorridorBounds from BoundaryFitter
        curvature_est : CurvatureEstimate
        point_count   : number of filtered LiDAR points used

        Returns
        -------
        ConfidenceEstimate
        """
        # --- Geometry confidence ---
        density_ratio = min(2.0, point_count / max(1, self.point_count_target))
        density_score = self._sigmoid(density_ratio, steepness=4.0, midpoint=0.5)

        residual = bounds.fit_residual if bounds.valid else 999.0
        residual_score = max(0.0, 1.0 - min(1.0, residual / self.residual_scale))

        # Station count score
        n_stations = bounds.n_stations if bounds.valid else 0
        station_score = min(1.0, n_stations / 8.0)

        geometry_conf = (density_score * 0.35 + residual_score * 0.35 + station_score * 0.30)

        # --- Corridor (width stability) confidence ---
        if bounds.valid and len(bounds.width_estimates) > 0:
            mean_w = float(np.mean(bounds.width_estimates))
            self._width_history.append(mean_w)

        if len(self._width_history) >= 2:
            width_std = float(np.std(list(self._width_history)))
            corridor_conf = max(0.0, 1.0 - min(1.0, width_std / self.width_confidence_scale))
        else:
            corridor_conf = 0.5  # prior

        # --- Temporal confidence (curvature consistency) ---
        if curvature_est.valid:
            self._curvature_history.append(curvature_est.curvature)

        if len(self._curvature_history) >= 3:
            kappa_vals = list(self._curvature_history)
            kappa_std = float(np.std(kappa_vals))
            temporal_conf = max(0.0, 1.0 - min(1.0, kappa_std / self.temporal_confidence_scale))
        else:
            temporal_conf = 0.4  # prior

        # --- Combined ---
        combined = (
            self.w_geometry * geometry_conf
            + self.w_temporal * temporal_conf
            + self.w_corridor * corridor_conf
        )
        combined = max(0.0, min(1.0, combined))

        # If bounds invalid, penalize
        if not bounds.valid:
            combined *= 0.35

        return ConfidenceEstimate(
            geometry_confidence=float(geometry_conf),
            temporal_confidence=float(temporal_conf),
            corridor_confidence=float(corridor_conf),
            combined_confidence=float(combined),
            point_density_ratio=float(density_ratio),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sigmoid(x: float, steepness: float = 6.0, midpoint: float = 0.5) -> float:
        """Sigmoid function scaled to [0, 1]."""
        try:
            return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
        except OverflowError:
            return 0.0 if x < midpoint else 1.0
