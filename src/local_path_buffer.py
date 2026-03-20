"""
local_path_buffer.py - Rolling buffer of recent corridor centre line estimates.

Provides temporal smoothing by blending the most recent estimate with a
weighted history.
"""

from collections import deque
from typing import List, Deque, Optional

import numpy as np

from corridor_detector import CorridorEstimate


class LocalPathBuffer:
    """
    Maintains a short rolling buffer of CorridorEstimate centre lines.

    On each update, the new estimate is blended with the buffered history
    to produce a smoother path for the controller.

    The buffer length is capped at MAX_BUFFER frames.
    """

    MAX_BUFFER: int = 10

    def __init__(self, config=None):
        self.blend_alpha: float = 0.55  # weight on the new estimate
        self._buffer: Deque[List[tuple]] = deque(maxlen=self.MAX_BUFFER)
        self._buffer_tangents: Deque[List[float]] = deque(maxlen=self.MAX_BUFFER)

        if config is not None:
            self._load_config(config)

    def _load_config(self, config) -> None:
        try:
            self.blend_alpha = 1.0 - float(config.geometry.fit_history_blend)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, corridor: CorridorEstimate) -> CorridorEstimate:
        """
        Add a new CorridorEstimate to the buffer and return a smoothed version.

        Parameters
        ----------
        corridor : CorridorEstimate (may be invalid)

        Returns
        -------
        CorridorEstimate - smoothed, validity set based on buffer state.
        """
        if not corridor.valid or len(corridor.center_line) == 0:
            # Return last buffered if available
            if len(self._buffer) > 0:
                return CorridorEstimate(
                    center_line=list(self._buffer[-1]),
                    tangents=list(self._buffer_tangents[-1]),
                    valid=False,
                    n_valid_stations=corridor.n_valid_stations,
                    mean_width=corridor.mean_width,
                    width_std=corridor.width_std,
                )
            return corridor

        raw_pts = corridor.center_line
        raw_tan = corridor.tangents

        if len(self._buffer) == 0:
            # Cold start - just record
            self._buffer.append(list(raw_pts))
            self._buffer_tangents.append(list(raw_tan))
            return corridor

        # Try to blend with the previous estimate
        prev_pts = self._buffer[-1]
        prev_tan = self._buffer_tangents[-1]

        smoothed_pts = self._blend_path(raw_pts, prev_pts)
        smoothed_tan = self._blend_tangents(raw_tan, prev_tan)

        self._buffer.append(smoothed_pts)
        self._buffer_tangents.append(smoothed_tan)

        return CorridorEstimate(
            center_line=smoothed_pts,
            tangents=smoothed_tan,
            valid=corridor.valid,
            n_valid_stations=corridor.n_valid_stations,
            mean_width=corridor.mean_width,
            width_std=corridor.width_std,
        )

    def clear(self) -> None:
        """Clear the buffer (e.g. after a reset)."""
        self._buffer.clear()
        self._buffer_tangents.clear()

    @property
    def is_warm(self) -> bool:
        """True once the buffer has at least 3 frames of history."""
        return len(self._buffer) >= 3

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _blend_path(self, new_pts: List[tuple], old_pts: List[tuple]) -> List[tuple]:
        """
        Blend two centre line arrays.  If lengths differ, return new_pts unchanged.
        """
        if len(new_pts) != len(old_pts):
            return list(new_pts)

        alpha = self.blend_alpha
        result = []
        for (nx, ny), (ox, oy) in zip(new_pts, old_pts):
            bx = alpha * nx + (1.0 - alpha) * ox
            by = alpha * ny + (1.0 - alpha) * oy
            result.append((bx, by))
        return result

    def _blend_tangents(
        self, new_tan: List[float], old_tan: List[float]
    ) -> List[float]:
        if len(new_tan) != len(old_tan):
            return list(new_tan)
        alpha = self.blend_alpha
        return [alpha * n + (1.0 - alpha) * o for n, o in zip(new_tan, old_tan)]
