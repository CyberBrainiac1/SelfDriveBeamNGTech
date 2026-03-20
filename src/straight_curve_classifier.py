"""
straight_curve_classifier.py - Classify road segment type from curvature estimate.

Segment types: 'straight', 'slight', 'medium', 'tight'.
Uses temporal persistence to confirm straight segments.
"""

from dataclasses import dataclass

from local_curvature_estimator import CurvatureEstimate
from corridor_detector import CorridorEstimate


@dataclass
class Classification:
    """Probabilistic classification of the current road segment."""
    segment_type: str           # 'straight', 'slight', 'medium', 'tight'
    is_straight: bool
    straight_probability: float
    left_probability: float
    right_probability: float
    slight_probability: float
    medium_probability: float
    tight_probability: float
    temporal_straight_count: int   # consecutive frames classified as straight
    confirmed_straight: bool       # temporal persistence threshold met

    @classmethod
    def default(cls) -> "Classification":
        return cls(
            segment_type="straight",
            is_straight=True,
            straight_probability=1.0,
            left_probability=0.0,
            right_probability=0.0,
            slight_probability=0.0,
            medium_probability=0.0,
            tight_probability=0.0,
            temporal_straight_count=0,
            confirmed_straight=False,
        )


class StraightCurveClassifier:
    """
    Classify road segment type and compute soft probabilities.

    Thresholds from config (hirochi_endurance.yaml):
        straight: |kappa| < 0.0016
        slight  : |kappa| < 0.0048
        medium  : |kappa| < 0.0105
        tight   : |kappa| >= 0.0105

    Straight confirmation requires `straight_persistence_frames` consecutive
    straight classifications.
    """

    def __init__(self, config=None):
        # Curvature thresholds
        self.straight_threshold: float = 0.0016
        self.slight_threshold: float = 0.0048
        self.medium_threshold: float = 0.0105
        self.tight_threshold: float = 0.0220

        # Temporal persistence
        self.straight_persistence_frames: int = 5
        self._straight_count: int = 0

        if config is not None:
            self._load_config(config)

    def _load_config(self, config) -> None:
        try:
            g = config.geometry
            self.straight_threshold = float(g.straight_curvature_threshold)
            self.slight_threshold = float(g.slight_curvature_threshold)
            self.medium_threshold = float(g.medium_curvature_threshold)
            self.tight_threshold = float(g.tight_curvature_threshold)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        curvature_est: CurvatureEstimate,
        corridor_est: CorridorEstimate = None,
        confidence: float = 1.0,
    ) -> Classification:
        """
        Classify the current segment.

        Parameters
        ----------
        curvature_est : CurvatureEstimate
        corridor_est  : CorridorEstimate (optional, unused currently)
        confidence    : float [0,1] overall confidence (modulates probabilities)

        Returns
        -------
        Classification
        """
        if not curvature_est.valid:
            self._straight_count = 0
            return Classification.default()

        kappa_abs = abs(curvature_est.curvature)
        kappa_sign = curvature_est.curvature

        # Determine hard segment type
        if kappa_abs < self.straight_threshold:
            segment_type = "straight"
        elif kappa_abs < self.slight_threshold:
            segment_type = "slight"
        elif kappa_abs < self.medium_threshold:
            segment_type = "medium"
        else:
            segment_type = "tight"

        # Straight temporal counter
        if segment_type == "straight":
            self._straight_count += 1
        else:
            self._straight_count = 0

        confirmed_straight = self._straight_count >= self.straight_persistence_frames

        # Soft probabilities via a simple Gaussian-like soft assignment
        straight_p = self._prob_straight(kappa_abs)
        curve_p = 1.0 - straight_p

        # Left/right split
        if kappa_abs < 1e-6:
            left_p = 0.5 * curve_p
            right_p = 0.5 * curve_p
        else:
            left_p = curve_p * max(0.0, kappa_sign / kappa_abs) if kappa_sign > 0 else 0.0
            right_p = curve_p * max(0.0, -kappa_sign / kappa_abs) if kappa_sign < 0 else 0.0

        # Segment type probabilities
        slight_p = self._prob_in_range(kappa_abs, self.straight_threshold, self.slight_threshold)
        medium_p = self._prob_in_range(kappa_abs, self.slight_threshold, self.medium_threshold)
        tight_p = self._prob_above(kappa_abs, self.medium_threshold)

        # Scale by confidence
        straight_p *= confidence
        left_p *= confidence
        right_p *= confidence

        return Classification(
            segment_type=segment_type,
            is_straight=(segment_type == "straight"),
            straight_probability=float(straight_p),
            left_probability=float(left_p),
            right_probability=float(right_p),
            slight_probability=float(slight_p),
            medium_probability=float(medium_p),
            tight_probability=float(tight_p),
            temporal_straight_count=self._straight_count,
            confirmed_straight=confirmed_straight,
        )

    # ------------------------------------------------------------------
    # Soft probability helpers
    # ------------------------------------------------------------------

    def _prob_straight(self, kappa_abs: float) -> float:
        """Soft probability of being straight based on curvature magnitude."""
        # Sigmoid-like: 1 at kappa=0, decays to ~0 at threshold
        import math
        scale = self.straight_threshold * 2.0
        return 1.0 / (1.0 + math.exp(8.0 * (kappa_abs - self.straight_threshold) / scale))

    @staticmethod
    def _prob_in_range(kappa_abs: float, lo: float, hi: float) -> float:
        """Probability of being in [lo, hi] range using triangle function."""
        mid = (lo + hi) / 2.0
        half = (hi - lo) / 2.0
        if half == 0:
            return 0.0
        dist = abs(kappa_abs - mid) / half
        return float(max(0.0, 1.0 - dist))

    @staticmethod
    def _prob_above(kappa_abs: float, threshold: float) -> float:
        """Probability of being above threshold (tight curve)."""
        import math
        if kappa_abs >= threshold:
            return min(1.0, (kappa_abs - threshold) / threshold + 0.5)
        return 0.0
