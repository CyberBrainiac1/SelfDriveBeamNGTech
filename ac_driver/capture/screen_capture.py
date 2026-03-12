"""
screen_capture.py
=================
High-speed screen grabber using mss (much faster than PIL.ImageGrab).

Original ACDriver used PIL.ImageGrab with hardcoded bboxes and no
colour processing — this replaces it with a configurable, fast pipeline.
"""

from __future__ import annotations
from typing import Optional, Tuple

import cv2
import mss
import numpy as np

from config import CFG


class ScreenCapture:
    """
    Grabs a region of the screen and returns numpy arrays.

    Keeps the mss context open for the lifetime of the object —
    re-creating it each frame is expensive.
    """

    def __init__(self) -> None:
        cfg = CFG.capture
        l, t, w, h = cfg.monitor_region
        self._monitor = {"left": l, "top": t, "width": w, "height": h}
        self._proc_size = (cfg.proc_width, cfg.proc_height)
        self._sct = mss.mss()

    # ── public ────────────────────────────────────────────────────
    def grab(self) -> Optional[np.ndarray]:
        """
        Returns a BGR numpy array (proc_height × proc_width × 3).
        Returns None on failure.
        """
        try:
            raw = self._sct.grab(self._monitor)
            # mss returns BGRA
            img = np.array(raw, dtype=np.uint8)[:, :, :3]  # drop alpha → BGR
            img = cv2.resize(img, self._proc_size, interpolation=cv2.INTER_AREA)
            return img
        except Exception as exc:
            print(f"[capture] Screen grab error: {exc}")
            return None

    def grab_full(self) -> Optional[np.ndarray]:
        """Returns the full-resolution BGR frame (no resize)."""
        try:
            raw = self._sct.grab(self._monitor)
            return np.array(raw, dtype=np.uint8)[:, :, :3]
        except Exception as exc:
            print(f"[capture] Full grab error: {exc}")
            return None

    def close(self) -> None:
        self._sct.close()

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *_) -> None:
        self.close()
