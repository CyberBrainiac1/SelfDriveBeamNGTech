"""
local_curvature_estimator.py - Estimate road curvature from corridor centre line.

Uses 3-point arc fitting and polynomial fitting for robustness.
Maintains a rolling history for trend analysis.
"""

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

import numpy as np

from corridor_detector import CorridorEstimate


@dataclass
class CurvatureEstimate:
    """Result of local curvature estimation."""
    curvature: float          # 1/radius, positive = left turn
    radius_m: float           # Inf if straight
    turn_direction: str       # 'straight', 'left', 'right'
    curvature_trend: str      # 'increasing', 'decreasing', 'stable'
    raw_curvature: float      # before EMA smoothing
    valid: bool

    @classmethod
    def straight(cls) -> "CurvatureEstimate":
        return cls(
            curvature=0.0,
            radius_m=float("inf"),
            turn_direction="straight",
            curvature_trend="stable",
            raw_curvature=0.0,
            valid=True,
        )

    @classmethod
    def invalid(cls) -> "CurvatureEstimate":
        return cls(
            curvature=0.0,
            radius_m=float("inf"),
            turn_direction="straight",
            curvature_trend="stable",
            raw_curvature=0.0,
            valid=False,
        )


class LocalCurvatureEstimator:
    """
    Estimate curvature from the center line of a CorridorEstimate.

    Two methods are tried and averaged for robustness:
    1. 3-point arc fit (start, middle, end of centre line).
    2. Quadratic polynomial fit to the centre line lateral deviation.
    """

    _HISTORY_LEN = 12

    def __init__(self, config=None):
        self.straight_threshold: float = 0.0016
        self.ema_alpha: float = 0.40
        self.trend_threshold: float = 0.0025

        if config is not None:
            self._load_config(config)

        self._history: Deque[float] = deque(maxlen=self._HISTORY_LEN)
        self._smoothed_curvature: float = 0.0

    def _load_config(self, config) -> None:
        try:
            g = config.geometry
            self.straight_threshold = float(g.straight_curvature_threshold)
            self.trend_threshold = float(g.curvature_trend_threshold)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self, corridor: CorridorEstimate) -> CurvatureEstimate:
        """
        Estimate curvature from corridor centre line.

        Parameters
        ----------
        corridor : CorridorEstimate

        Returns
        -------
        CurvatureEstimate
        """
        if not corridor.valid or len(corridor.center_line) < 3:
            return CurvatureEstimate.invalid()

        pts = np.array(corridor.center_line, dtype=np.float64)  # (K, 2): (x, y)

        # Method 1: 3-point arc fit
        kappa_arc = self._arc_curvature(pts)

        # Method 2: polynomial fit
        kappa_poly = self._poly_curvature(pts)

        # Combine - average, weighted by validity
        kappa_raw = 0.0
        count = 0
        if kappa_arc is not None:
            kappa_raw += kappa_arc
            count += 1
        if kappa_poly is not None:
            kappa_raw += kappa_poly
            count += 1

        if count == 0:
            return CurvatureEstimate.invalid()

        kappa_raw /= count

        # EMA smoothing
        if len(self._history) == 0:
            self._smoothed_curvature = kappa_raw
        else:
            self._smoothed_curvature = (
                self.ema_alpha * kappa_raw
                + (1.0 - self.ema_alpha) * self._smoothed_curvature
            )

        self._history.append(kappa_raw)

        kappa = self._smoothed_curvature
        radius_m = abs(1.0 / kappa) if abs(kappa) > 1e-6 else float("inf")

        turn_dir = self._turn_direction(kappa)
        trend = self._curvature_trend()

        return CurvatureEstimate(
            curvature=kappa,
            radius_m=radius_m,
            turn_direction=turn_dir,
            curvature_trend=trend,
            raw_curvature=kappa_raw,
            valid=True,
        )

    # ------------------------------------------------------------------
    # Curvature computation methods
    # ------------------------------------------------------------------

    @staticmethod
    def _arc_curvature(pts: np.ndarray) -> Optional[float]:
        """
        Fit a circle through three representative points (start, mid, end).
        Returns signed curvature (positive = left).
        """
        n = len(pts)
        i0, i1, i2 = 0, n // 2, n - 1
        p0 = pts[i0]  # (x, y) in vehicle frame
        p1 = pts[i1]
        p2 = pts[i2]

        # Use forward (y) and lateral (x) coords
        # Fit circle through (y0,x0), (y1,x1), (y2,x2)
        ax, ay = float(p0[1]), float(p0[0])  # (y, x)
        bx, by = float(p1[1]), float(p1[0])
        cx_, cy = float(p2[1]), float(p2[0])

        # Determinant method
        D = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx_ * (ay - by))
        if abs(D) < 1e-8:
            return 0.0  # collinear - straight

        ux = ((ax ** 2 + ay ** 2) * (by - cy)
              + (bx ** 2 + by ** 2) * (cy - ay)
              + (cx_ ** 2 + cy ** 2) * (ay - by)) / D
        uy = ((ax ** 2 + ay ** 2) * (cx_ - bx)
              + (bx ** 2 + by ** 2) * (ax - cx_)
              + (cx_ ** 2 + cy ** 2) * (bx - ax)) / D

        R = math.sqrt((ax - ux) ** 2 + (ay - uy) ** 2)
        if R < 0.1:
            return None

        # Sign: positive curvature = centre is to the left (positive x)
        # Centre x relative to first point
        centre_x_vehicle = uy  # uy corresponds to x in our (y,x) coordinate
        kappa = 1.0 / R
        if centre_x_vehicle < ay:  # centre is to right - right turn - negative
            kappa = -kappa

        return kappa

    @staticmethod
    def _poly_curvature(pts: np.ndarray) -> Optional[float]:
        """
        Fit y = f(x) quadratic to the centre line (x lateral, y forward).
        Actually fit x = a*y^2 + b*y + c in vehicle frame.
        Curvature - 2*a at the vehicle position (y=0 extrapolated).
        """
        x_vals = pts[:, 0]  # lateral
        y_vals = pts[:, 1]  # forward

        if len(y_vals) < 3:
            return None

        try:
            coeffs = np.polyfit(y_vals, x_vals, deg=2)
        except (np.linalg.LinAlgError, ValueError):
            return None

        a = coeffs[0]  # coefficient of y^2
        # Curvature of x(y) at the start: kappa - 2*a / (1 + (b)^2)^(3/2)
        b = coeffs[1]
        denom = (1.0 + b ** 2) ** 1.5
        if denom < 1e-6:
            return None

        kappa = 2.0 * a / denom
        return float(kappa)

    # ------------------------------------------------------------------
    # Direction and trend
    # ------------------------------------------------------------------

    def _turn_direction(self, kappa: float) -> str:
        if abs(kappa) < self.straight_threshold:
            return "straight"
        return "left" if kappa > 0 else "right"

    def _curvature_trend(self) -> str:
        """Determine if curvature is increasing, decreasing or stable."""
        if len(self._history) < 4:
            return "stable"
        recent = list(self._history)[-4:]
        # Compare magnitudes of last half vs first half
        half = len(recent) // 2
        mag_early = np.mean(np.abs(recent[:half]))
        mag_late = np.mean(np.abs(recent[half:]))
        delta = mag_late - mag_early
        if delta > self.trend_threshold:
            return "increasing"
        if delta < -self.trend_threshold:
            return "decreasing"
        return "stable"
