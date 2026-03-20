"""
curve_speed_scheduler.py - Compute a target speed based on curvature and confidence.

Uses lateral acceleration constraint to limit speed in curves.
"""

import math

from local_curvature_estimator import CurvatureEstimate
from confidence_estimator import ConfidenceEstimate
from straight_curve_classifier import Classification


class CurveSpeedScheduler:
    """
    Compute target speed in kph.

    Algorithm:
    1. Base target from config (target_cruise_kph).
    2. Lateral accel constraint: v_max = sqrt(a_lat_max / |kappa|) m/s.
    3. Speed target = min(base, v_max * safety_factor).
    4. If low confidence: scale by cautious_speed_scale.
    5. Apply min/max bounds.
    6. EMA smooth.
    """

    def __init__(self, config=None):
        self.target_cruise_kph: float = 95.0
        self.max_lateral_accel_mps2: float = 4.9
        self.curve_speed_safety: float = 0.82
        self.min_speed_kph: float = 35.0
        self.max_speed_kph: float = 120.0
        self.cautious_speed_scale: float = 0.70
        self.tightening_speed_penalty: float = 0.18
        self.low_confidence_threshold: float = 0.35
        self.ema_alpha: float = 0.35

        if config is not None:
            self._load_config(config)

        self._smoothed_kph: float = self.target_cruise_kph

    def _load_config(self, config) -> None:
        try:
            d = config.demo
            self.target_cruise_kph = float(d.target_cruise_kph)
        except AttributeError:
            pass
        try:
            sp = config.speed_planner
            self.max_lateral_accel_mps2 = float(sp.max_lateral_accel_mps2)
            self.curve_speed_safety = float(sp.curve_speed_safety)
            self.min_speed_kph = float(sp.min_speed_kph)
            self.max_speed_kph = float(sp.max_speed_kph)
        except AttributeError:
            pass
        try:
            pc = config.probabilistic_control
            self.cautious_speed_scale = float(pc.cautious_speed_scale)
            self.tightening_speed_penalty = float(pc.tightening_speed_penalty)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        curvature_est: CurvatureEstimate,
        conf_est: ConfidenceEstimate,
        classification: Classification,
        current_speed_kph: float = 0.0,
    ) -> float:
        """
        Compute the target speed in kph.

        Parameters
        ----------
        curvature_est    : CurvatureEstimate
        conf_est         : ConfidenceEstimate
        classification   : Classification
        current_speed_kph: float

        Returns
        -------
        float - target speed in kph
        """
        base_kph = self.target_cruise_kph

        # Lateral acceleration constraint
        kappa = abs(curvature_est.curvature) if curvature_est.valid else 0.0
        if kappa > 1e-5:
            v_max_mps = math.sqrt(self.max_lateral_accel_mps2 / kappa)
            v_max_kph = v_max_mps * 3.6 * self.curve_speed_safety
            target_kph = min(base_kph, v_max_kph)
        else:
            target_kph = base_kph

        # Low confidence penalty
        if conf_est.combined_confidence < self.low_confidence_threshold:
            target_kph *= self.cautious_speed_scale

        # Curvature tightening penalty
        if curvature_est.valid and curvature_est.curvature_trend == "increasing":
            target_kph *= (1.0 - self.tightening_speed_penalty)

        # Clamp
        target_kph = max(self.min_speed_kph, min(self.max_speed_kph, target_kph))

        # EMA smooth
        self._smoothed_kph = (
            self.ema_alpha * target_kph + (1.0 - self.ema_alpha) * self._smoothed_kph
        )
        self._smoothed_kph = max(self.min_speed_kph, min(self.max_speed_kph, self._smoothed_kph))

        return float(self._smoothed_kph)

    def reset(self) -> None:
        self._smoothed_kph = self.target_cruise_kph
