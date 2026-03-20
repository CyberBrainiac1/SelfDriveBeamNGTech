"""
Live debug overlay window using OpenCV.
Shows camera feed with perception annotations, telemetry bar, and HUD.
Press 'q' to quit, 'p' to pause, 'e' for emergency stop toggle.
"""

from __future__ import annotations
from typing import Optional

import cv2
import numpy as np

from config import CFG
from beamng_interface.vehicle_control import ControlCommand
from perception.lane_detection import LaneDetectionResult
from perception.obstacle_detection import ObstacleResult
from perception.state_estimation import EgoState
from planning.behavior_planner import DrivingMode
from utils.image_utils import normalize_depth, stack_debug


# Key codes
_KEY_Q = ord("q")
_KEY_P = ord("p")
_KEY_E = ord("e")


class DebugOverlay:
    """Renders a live debug window with all autonomy‑stack info."""

    WINDOW = "Autonomy Debug"

    def __init__(self) -> None:
        self._enabled = CFG.debug.show_overlay
        if self._enabled:
            cv2.namedWindow(self.WINDOW, cv2.WINDOW_NORMAL)

    # ── per‑tick ───────────────────────────────────────────────────
    def update(
        self,
        lane: LaneDetectionResult,
        obstacle: ObstacleResult,
        ego: EgoState,
        mode: DrivingMode,
        cmd: ControlCommand,
        depth: Optional[np.ndarray] = None,
    ) -> int:
        """Draw and display. Returns the key code (0 if none)."""
        if not self._enabled:
            return 0

        panels = []

        # 1) Perception overlay (camera + lane lines)
        if lane.overlay is not None:
            panels.append(lane.overlay)

        # 2) Depth visualisation
        if depth is not None:
            panels.append(cv2.applyColorMap(normalize_depth(depth, 80.0), cv2.COLORMAP_INFERNO))

        # 3) Road mask
        if lane.road_mask is not None:
            panels.append(lane.road_mask)

        canvas = stack_debug(*panels, target_h=300)

        # HUD text
        self._hud(canvas, ego, mode, cmd, obstacle)

        cv2.imshow(self.WINDOW, canvas)
        key = cv2.waitKey(1) & 0xFF
        return key

    def close(self) -> None:
        if self._enabled:
            cv2.destroyAllWindows()

    # ── internals ──────────────────────────────────────────────────
    @staticmethod
    def _hud(
        canvas: np.ndarray,
        ego: EgoState,
        mode: DrivingMode,
        cmd: ControlCommand,
        obstacle: ObstacleResult,
    ) -> None:
        y = canvas.shape[0] - 10
        lines = [
            f"MODE: {mode.name}",
            f"SPD: {ego.speed_kph:5.1f} kph  RPM: {ego.rpm:5.0f}  GEAR: {ego.gear}",
            f"STR: {cmd.steering:+.3f}  THR: {cmd.throttle:.3f}  BRK: {cmd.brake:.3f}",
            f"OBS dist: {obstacle.min_distance_m:5.1f}m  frac: {obstacle.close_pixel_fraction:.3f}",
        ]
        for line in reversed(lines):
            cv2.putText(canvas, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y -= 18
