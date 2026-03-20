"""
Simple obstacle / collision‑risk detection (v1).

Strategy:
  • Use the depth image from the front camera.
  • Divide the depth image into a forward‑looking region.
  • If many pixels are closer than a threshold → something is in the way.

This is deliberately simple.  A future version can use bounding‑box
detection, point clouds, or BeamNG's built‑in LIDAR.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np

from config import CFG


@dataclass
class ObstacleResult:
    obstacle_ahead: bool = False
    min_distance_m: float = float("inf")
    close_pixel_fraction: float = 0.0


class ObstacleDetector:
    """Detect obstacles from the depth buffer."""

    # Tunables (could move to config if needed)
    CLOSE_THRESHOLD_M: float = 15.0    # anything closer than this is "obstacle"
    DANGER_FRACTION: float = 0.05      # if >5% of forward ROI is close → obstacle

    def detect(self, depth_image: Optional[np.ndarray]) -> ObstacleResult:
        if depth_image is None:
            return ObstacleResult()

        h, w = depth_image.shape[:2]
        # Look ahead through the upper-middle image band to avoid the hood and near ground.
        roi = depth_image[int(h * 0.25): int(h * 0.55), int(w * 0.35): int(w * 0.65)]

        valid = roi[np.isfinite(roi) & (roi > 0)]  # ignore zero/invalid depth
        if valid.size == 0:
            return ObstacleResult()

        close_mask = valid < self.CLOSE_THRESHOLD_M
        frac = float(np.sum(close_mask)) / valid.size
        min_dist = float(np.min(valid)) if valid.size > 0 else float("inf")

        return ObstacleResult(
            obstacle_ahead=frac > self.DANGER_FRACTION,
            min_distance_m=min_dist,
            close_pixel_fraction=frac,
        )
