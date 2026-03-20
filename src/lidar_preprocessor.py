"""
lidar_preprocessor.py — Filter and downsample LiDAR point clouds.

Input:  raw point cloud in VEHICLE frame (X=right, Y=forward, Z=up).
Output: filtered forward-facing points, still in vehicle frame.
"""

import numpy as np


class LidarPreprocessor:
    """
    Config-driven LiDAR point cloud preprocessor.

    Applies spatial filtering and optional voxel downsampling.
    """

    def __init__(self, config=None):
        """
        Parameters
        ----------
        config : Config or None
            If provided, reads from config.geometry and config.perception.lidar.
        """
        # Defaults (matched to hirochi_endurance.yaml)
        self.min_forward_m: float = 5.0
        self.max_forward_m: float = 75.0
        self.lateral_filter_m: float = 25.0
        self.min_height_m: float = -0.5
        self.max_height_m: float = 4.0
        self.min_proximity_m: float = 2.0
        self.voxel_size: float = 0.5   # metres; set to 0 to disable
        self.min_point_count: int = 70

        if config is not None:
            self._load_config(config)

    def _load_config(self, config) -> None:
        try:
            g = config.geometry
            self.min_forward_m = float(g.min_forward_m)
            self.max_forward_m = float(g.max_forward_m)
            self.min_point_count = int(g.min_point_count)
        except AttributeError:
            pass

        try:
            ldr = config.perception.lidar
            self.lateral_filter_m = float(ldr.lateral_filter_m)
            self.min_height_m = float(ldr.min_height_m)
            self.max_height_m = float(ldr.max_height_m)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, points: np.ndarray) -> np.ndarray:
        """
        Filter and downsample a vehicle-frame point cloud.

        Parameters
        ----------
        points : np.ndarray, shape (N, 3)
            Raw LiDAR points in vehicle frame (X=right, Y=forward, Z=up).

        Returns
        -------
        np.ndarray shape (M, 3), M <= N
            Filtered points.  May be empty (shape (0,3)) if input is insufficient.
        """
        if points is None or len(points) == 0:
            return np.zeros((0, 3), dtype=np.float64)

        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 3:
            return np.zeros((0, 3), dtype=np.float64)

        # 1. Remove points too close to vehicle (sensor/body self-returns)
        dist_xy = np.sqrt(pts[:, 0] ** 2 + pts[:, 1] ** 2)
        pts = pts[dist_xy >= self.min_proximity_m]

        if len(pts) == 0:
            return pts

        # 2. Forward filter: y in [min_forward_m, max_forward_m]
        mask_y = (pts[:, 1] >= self.min_forward_m) & (pts[:, 1] <= self.max_forward_m)
        pts = pts[mask_y]

        if len(pts) == 0:
            return pts

        # 3. Lateral filter: |x| < lateral_filter_m
        mask_x = np.abs(pts[:, 0]) < self.lateral_filter_m
        pts = pts[mask_x]

        if len(pts) == 0:
            return pts

        # 4. Height filter
        mask_z = (pts[:, 2] >= self.min_height_m) & (pts[:, 2] <= self.max_height_m)
        pts = pts[mask_z]

        if len(pts) == 0:
            return pts

        # 5. Voxel downsampling (grid-based)
        if self.voxel_size > 0 and len(pts) > 500:
            pts = self._voxel_downsample(pts, self.voxel_size)

        return pts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _voxel_downsample(self, pts: np.ndarray, voxel_size: float) -> np.ndarray:
        """
        Simple voxel grid downsampling: keep one point per cell (centroid).
        """
        # Compute voxel indices
        origin = pts.min(axis=0)
        indices = np.floor((pts - origin) / voxel_size).astype(np.int32)

        # Pack to single integer key
        max_idx = indices.max(axis=0) + 1
        keys = (indices[:, 0] * max_idx[1] * max_idx[2]
                + indices[:, 1] * max_idx[2]
                + indices[:, 2])

        # Keep first point in each voxel (sorted order preserves spatial structure)
        _, first_idx = np.unique(keys, return_index=True)
        return pts[first_idx]

    @property
    def sufficient_points(self) -> int:
        return self.min_point_count
