"""
Road surface analysis — placeholder for v2 features like road‑type
classification, surface‑grip estimation, or pothole detection.

Currently provides a simple "road visible" check based on the
road mask from lane_detection.
"""

from __future__ import annotations
from typing import Optional

import numpy as np


class RoadAnalyser:
    """Analyses the road mask to assess driving conditions."""

    @staticmethod
    def road_visible(road_mask: Optional[np.ndarray], min_fraction: float = 0.05) -> bool:
        """Return True if enough pixels in the mask look like road."""
        if road_mask is None:
            return False
        frac = float(np.count_nonzero(road_mask)) / road_mask.size
        return frac >= min_fraction

    @staticmethod
    def road_width_fraction(road_mask: Optional[np.ndarray]) -> float:
        """Estimate the fraction of the bottom row that is road."""
        if road_mask is None:
            return 0.0
        bottom_row = road_mask[-1, :]
        return float(np.count_nonzero(bottom_row)) / bottom_row.size
