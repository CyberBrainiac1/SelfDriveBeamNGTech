"""
debug_overlay.py
================
Draws a HUD over the cropped frame: lane offset, steering command, speed,
model confidence, control mode.
"""

from __future__ import annotations
import cv2
import numpy as np
from typing import Optional


def draw_hud(
    bgr: np.ndarray,
    *,
    lane_offset: Optional[float] = None,
    steering: float = 0.0,
    speed_kph: float = 0.0,
    confidence: float = 0.0,
    mode: str = "classical",
    scale: int = 4,
) -> np.ndarray:
    """
    Returns an upscaled BGR image with a debug HUD overlay.
    scale: multiply frame dimensions by this for visibility.
    """
    h, w = bgr.shape[:2]
    vis = cv2.resize(bgr, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)

    mid_x = w * scale // 2
    mid_y = h * scale // 2

    # Horizon line
    cv2.line(vis, (0, mid_y), (w * scale, mid_y), (80, 80, 80), 1)

    # Lane centre offset indicator
    if lane_offset is not None:
        off_x = mid_x + int(lane_offset * mid_x)
        cv2.circle(vis, (off_x, mid_y - 10), 6, (0, 255, 0), -1)
        cv2.line(vis, (mid_x, mid_y - 10), (off_x, mid_y - 10), (0, 200, 0), 1)

    # Steering bar
    bar_y = h * scale - 14
    bar_w = int(abs(steering) * mid_x)
    bar_x = mid_x if steering >= 0 else mid_x - bar_w
    col = (0, 0, 255) if steering < 0 else (255, 0, 0)
    cv2.rectangle(vis, (bar_x, bar_y - 8), (bar_x + bar_w, bar_y + 8), col, -1)
    cv2.line(vis, (mid_x, bar_y - 12), (mid_x, bar_y + 12), (255, 255, 255), 1)

    # Text info
    lines = [
        f"Speed: {speed_kph:.0f} kph",
        f"Offset: {(lane_offset or 0):+.3f}",
        f"Steer:  {steering:+.3f}",
        f"Conf:   {confidence:.2f}",
        f"Mode:   {mode}",
    ]
    for i, txt in enumerate(lines):
        cv2.putText(vis, txt, (6, 16 + i * 14), cv2.FONT_HERSHEY_PLAIN,
                    0.85, (0, 255, 255), 1, cv2.LINE_AA)

    return vis
