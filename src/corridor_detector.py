"""
corridor_detector.py — Post-process BoundaryFitter output into a clean CorridorEstimate.

Applies temporal smoothing, validates corridor width, computes tangent directions.
"""

import math
from collections import deque
from dataclasses import dataclass, field
from typing import List, Deque

import numpy as np

from boundary_fitter import CorridorBounds


@dataclass
class CorridorEstimate:
    """
    Clean corridor description in vehicle frame (X=right, Y=forward).
    center_line[i] = (x, y) — lateral, then forward.
    tangents[i]    = heading angle in radians (positive = turning left)
    """
    center_line: List[tuple]   # list of (x, y) pairs
    tangents: List[float]      # list of heading angles in radians
    valid: bool
    n_valid_stations: int
    mean_width: float
    width_std: float

    @classmethod
    def invalid(cls) -> "CorridorEstimate":
        return cls(
            center_line=[],
            tangents=[],
            valid=False,
            n_valid_stations=0,
            mean_width=7.5,
            width_std=999.0,
        )


class CorridorDetector:
    """
    Converts CorridorBounds into a temporally-smoothed CorridorEstimate.

    Temporal smoothing blends the new raw center line with a short history
    buffer.  This reduces jitter from frame-to-frame LiDAR variation.
    """

    _HISTORY_LEN = 6

    def __init__(self, config=None):
        self.min_station_count: int = 5
        self.min_corridor_width_m: float = 4.0
        self.max_corridor_width_m: float = 14.0
        self.default_corridor_width_m: float = 7.5
        self.history_blend: float = 0.38  # new = (1-blend)*raw + blend*history

        if config is not None:
            self._load_config(config)

        # History of center_x arrays aligned to the same y stations
        self._center_x_history: Deque[np.ndarray] = deque(maxlen=self._HISTORY_LEN)
        self._width_history: Deque[np.ndarray] = deque(maxlen=self._HISTORY_LEN)
        self._last_valid: CorridorEstimate = CorridorEstimate.invalid()

    def _load_config(self, config) -> None:
        try:
            g = config.geometry
            self.min_station_count = int(g.min_station_count)
            self.min_corridor_width_m = float(g.min_corridor_width_m)
            self.max_corridor_width_m = float(g.max_corridor_width_m)
            self.default_corridor_width_m = float(g.default_corridor_width_m)
            self.history_blend = float(g.fit_history_blend)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, bounds: CorridorBounds) -> CorridorEstimate:
        """
        Ingest new CorridorBounds and return smoothed CorridorEstimate.

        Parameters
        ----------
        bounds : CorridorBounds from BoundaryFitter

        Returns
        -------
        CorridorEstimate  (valid=False if insufficient data)
        """
        if not bounds.valid or bounds.n_stations < self.min_station_count:
            # Return last valid estimate with validity flag cleared if too stale
            if self._last_valid.valid:
                stale = CorridorEstimate(
                    center_line=self._last_valid.center_line,
                    tangents=self._last_valid.tangents,
                    valid=False,
                    n_valid_stations=self._last_valid.n_valid_stations,
                    mean_width=self._last_valid.mean_width,
                    width_std=self._last_valid.width_std,
                )
                return stale
            return CorridorEstimate.invalid()

        y_arr = bounds.center_pts[:, 0]   # station y positions
        cx_raw = bounds.center_pts[:, 1]  # raw center x at each station

        # Temporal blend of center_x
        cx_blended = self._blend_center(cx_raw)

        # Build center line
        center_line = [(float(cx_blended[i]), float(y_arr[i])) for i in range(len(y_arr))]

        # Compute tangents from finite differences
        tangents = self._compute_tangents(cx_blended, y_arr)

        # Width statistics
        widths = bounds.width_estimates
        mean_width = float(np.mean(widths)) if len(widths) > 0 else self.default_corridor_width_m
        width_std = float(np.std(widths)) if len(widths) > 1 else 0.0

        # Clamp mean_width to valid range
        mean_width = max(self.min_corridor_width_m, min(self.max_corridor_width_m, mean_width))

        est = CorridorEstimate(
            center_line=center_line,
            tangents=tangents,
            valid=True,
            n_valid_stations=bounds.n_stations,
            mean_width=mean_width,
            width_std=width_std,
        )
        self._last_valid = est
        return est

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _blend_center(self, cx_raw: np.ndarray) -> np.ndarray:
        """
        Blend raw center_x with historical estimates using EMA-style weighting.
        """
        if len(self._center_x_history) == 0:
            self._center_x_history.append(cx_raw.copy())
            return cx_raw

        # Only blend if lengths match (they should for a fixed station grid)
        prev = self._center_x_history[-1]
        if prev.shape == cx_raw.shape:
            blended = (1.0 - self.history_blend) * cx_raw + self.history_blend * prev
        else:
            blended = cx_raw

        self._center_x_history.append(blended.copy())
        return blended

    @staticmethod
    def _compute_tangents(cx: np.ndarray, y: np.ndarray) -> List[float]:
        """
        Compute path tangent angles from finite differences of the center line.

        The path runs along Y with lateral offset cx.
        Tangent = atan2(delta_cx, delta_y) — positive = left turn.
        """
        tangents = []
        n = len(cx)
        for i in range(n):
            if i == 0:
                dx = cx[1] - cx[0] if n > 1 else 0.0
                dy = y[1] - y[0] if n > 1 else 1.0
            elif i == n - 1:
                dx = cx[-1] - cx[-2]
                dy = y[-1] - y[-2]
            else:
                dx = cx[i + 1] - cx[i - 1]
                dy = y[i + 1] - y[i - 1]
            tangents.append(math.atan2(dx, dy))
        return tangents
