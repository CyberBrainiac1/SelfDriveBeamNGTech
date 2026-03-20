"""
image_utils.py
==============
Small image helpers shared across modules.
"""

from __future__ import annotations
import cv2
import numpy as np


def bgr_to_rgb_float(bgr: np.ndarray) -> np.ndarray:
    """Convert HxWx3 uint8 BGR → HxWx3 float32 RGB in [0, 1]."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.float32) / 255.0


def resize_to(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def add_batch_dim(arr: np.ndarray) -> np.ndarray:
    """Prepend a batch dimension: HxWxC → 1xHxWxC."""
    return np.expand_dims(arr, axis=0)
