"""
boundary_fitter.py - Fit left/right corridor boundaries from LiDAR point cloud.

Input:  filtered vehicle-frame points (N,3).
Output: CorridorBounds dataclass with boundary stations.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class CorridorBounds:
    """Results from fitting corridor boundaries to a LiDAR point cloud."""
    left_pts: np.ndarray      # shape (K,2): columns = [y_station, x_left]
    right_pts: np.ndarray     # shape (K,2): columns = [y_station, x_right]
    center_pts: np.ndarray    # shape (K,2): columns = [y_station, x_center]
    fit_residual: float       # quality metric (lower = better)
    width_estimates: np.ndarray  # shape (K,) width at each station
    n_stations: int
    valid: bool

    @classmethod
    def invalid(cls) -> "CorridorBounds":
        empty = np.zeros((0, 2))
        return cls(
            left_pts=empty,
            right_pts=empty,
            center_pts=empty,
            fit_residual=999.0,
            width_estimates=np.zeros(0),
            n_stations=0,
            valid=False,
        )


class BoundaryFitter:
    """
    Fit corridor boundaries from a forward-facing LiDAR point cloud.

    Algorithm:
    - Divide y range into stations.
    - At each station find left boundary (low-percentile x) and right boundary
      (high-percentile x).
    - Smooth with EMA.
    - Compute centre and width.
    """

    def __init__(self, config=None):
        # Defaults from hirochi_endurance.yaml
        self.min_forward_m: float = 5.0
        self.max_forward_m: float = 75.0
        self.station_spacing_m: float = 4.5
        self.station_half_width_m: float = 2.0   # slice -2 m around station y
        self.boundary_percentile: float = 14.0
        self.min_side_points: int = 3
        self.min_corridor_width_m: float = 4.0
        self.max_corridor_width_m: float = 14.0
        self.default_corridor_width_m: float = 7.5
        self.ema_alpha: float = 0.35             # smoothing
        self.min_point_count: int = 70

        if config is not None:
            self._load_config(config)

    def _load_config(self, config) -> None:
        try:
            g = config.geometry
            self.min_forward_m = float(g.min_forward_m)
            self.max_forward_m = float(g.max_forward_m)
            self.station_spacing_m = float(g.station_spacing_m)
            self.boundary_percentile = float(g.boundary_percentile)
            self.min_side_points = int(g.min_side_points)
            self.min_corridor_width_m = float(g.min_corridor_width_m)
            self.max_corridor_width_m = float(g.max_corridor_width_m)
            self.default_corridor_width_m = float(g.default_corridor_width_m)
            self.min_point_count = int(g.min_point_count)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, points: np.ndarray) -> CorridorBounds:
        """
        Fit corridor boundaries to vehicle-frame point cloud.

        Parameters
        ----------
        points : np.ndarray shape (N, 3), vehicle frame (X=right, Y=forward, Z=up)

        Returns
        -------
        CorridorBounds
        """
        if points is None or len(points) < self.min_point_count:
            return CorridorBounds.invalid()

        pts = np.asarray(points, dtype=np.float64)

        stations = np.arange(
            self.min_forward_m + self.station_half_width_m,
            self.max_forward_m,
            self.station_spacing_m,
        )

        if len(stations) == 0:
            return CorridorBounds.invalid()

        left_x_list = []
        right_x_list = []
        valid_stations = []

        for y_s in stations:
            y_lo = y_s - self.station_half_width_m
            y_hi = y_s + self.station_half_width_m
            mask = (pts[:, 1] >= y_lo) & (pts[:, 1] <= y_hi)
            slice_pts = pts[mask]

            if len(slice_pts) < self.min_side_points:
                continue

            x_vals = slice_pts[:, 0]
            left_x = np.percentile(x_vals, self.boundary_percentile)
            right_x = np.percentile(x_vals, 100.0 - self.boundary_percentile)

            # Sanity check
            width = right_x - left_x
            if width < self.min_corridor_width_m or width > self.max_corridor_width_m:
                # Accept but flag - could be an edge station
                if width > self.max_corridor_width_m:
                    # Clamp to reasonable range
                    half = self.default_corridor_width_m / 2.0
                    mid = (left_x + right_x) / 2.0
                    left_x = mid - half
                    right_x = mid + half

            left_x_list.append(left_x)
            right_x_list.append(right_x)
            valid_stations.append(y_s)

        if len(valid_stations) < 2:
            return CorridorBounds.invalid()

        # Convert to arrays
        y_arr = np.array(valid_stations)
        left_arr = np.array(left_x_list)
        right_arr = np.array(right_x_list)

        # EMA smoothing (forward pass)
        left_arr = self._ema_smooth(left_arr, self.ema_alpha)
        right_arr = self._ema_smooth(right_arr, self.ema_alpha)

        center_arr = (left_arr + right_arr) / 2.0
        width_arr = right_arr - left_arr

        # Build output arrays: columns [y_station, x]
        left_pts = np.column_stack([y_arr, left_arr])
        right_pts = np.column_stack([y_arr, right_arr])
        center_pts = np.column_stack([y_arr, center_arr])

        # Residual: std of width variation (lower = straighter corridor)
        fit_residual = float(np.std(width_arr)) if len(width_arr) > 1 else 0.0

        return CorridorBounds(
            left_pts=left_pts,
            right_pts=right_pts,
            center_pts=center_pts,
            fit_residual=fit_residual,
            width_estimates=width_arr,
            n_stations=len(valid_stations),
            valid=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ema_smooth(arr: np.ndarray, alpha: float) -> np.ndarray:
        """Exponential moving average smoothing (forward pass)."""
        result = np.empty_like(arr)
        result[0] = arr[0]
        for i in range(1, len(arr)):
            result[i] = alpha * arr[i] + (1.0 - alpha) * result[i - 1]
        return result
