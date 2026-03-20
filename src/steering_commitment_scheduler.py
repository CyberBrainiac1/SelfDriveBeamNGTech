"""
steering_commitment_scheduler.py - Compute a steering commitment factor.

The commitment factor scales how aggressively the controller follows the
computed steering command vs. smoothing it out.  High confidence + tight
curve - high commitment.  Confirmed straight - reduced commitment.
"""

from dataclasses import dataclass

from confidence_estimator import ConfidenceEstimate
from straight_curve_classifier import Classification


class SteeringCommitmentScheduler:
    """
    Compute a steering commitment factor - [min_commitment, max_commitment].

    Algorithm:
    1. Base commitment = lerp(min, max, combined_confidence).
    2. If confirmed straight: reduce by straight_steering_relaxation.
    3. If curvature is tightening: add tightening_commitment_bonus.
    4. EMA smooth.
    5. Clamp.
    """

    def __init__(self, config=None):
        self.min_commitment: float = 0.18
        self.max_commitment: float = 0.98
        self.ema_alpha: float = 0.32
        self.straight_relaxation: float = 0.42
        self.tightening_bonus: float = 0.14

        if config is not None:
            self._load_config(config)

        self._smoothed: float = 0.60  # initial value

    def _load_config(self, config) -> None:
        try:
            pc = config.probabilistic_control
            self.min_commitment = float(pc.min_steering_commitment)
            self.max_commitment = float(pc.max_steering_commitment)
            self.ema_alpha = float(pc.commitment_smoothing)
            self.straight_relaxation = float(pc.straight_steering_relaxation)
            self.tightening_bonus = float(pc.tightening_commitment_bonus)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        conf_est: ConfidenceEstimate,
        classification: Classification,
        curvature_trend: str = "stable",
    ) -> float:
        """
        Compute the steering commitment factor for this tick.

        Parameters
        ----------
        conf_est       : ConfidenceEstimate
        classification : Classification from StraightCurveClassifier
        curvature_trend: 'increasing', 'decreasing', or 'stable'

        Returns
        -------
        float in [min_commitment, max_commitment]
        """
        cc = conf_est.combined_confidence

        # 1. Base: linear interpolation between min and max
        base = self.min_commitment + cc * (self.max_commitment - self.min_commitment)

        # 2. Straight relaxation
        if classification.confirmed_straight:
            base = base * (1.0 - self.straight_relaxation) + self.min_commitment * self.straight_relaxation

        # 3. Tightening bonus
        if curvature_trend == "increasing":
            base = min(self.max_commitment, base + self.tightening_bonus)

        # 4. EMA smooth
        self._smoothed = self.ema_alpha * base + (1.0 - self.ema_alpha) * self._smoothed

        # 5. Clamp
        self._smoothed = max(self.min_commitment, min(self.max_commitment, self._smoothed))

        return self._smoothed

    def reset(self) -> None:
        self._smoothed = (self.min_commitment + self.max_commitment) / 2.0
