"""
Image utility functions for the perception pipeline.
"""

from __future__ import annotations
from typing import Tuple

import cv2
import numpy as np


def resize(img: np.ndarray, width: int, height: int) -> np.ndarray:
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def crop_bottom(img: np.ndarray, frac: float = 0.5) -> np.ndarray:
    """Return the bottom `frac` fraction of the image."""
    h = img.shape[0]
    return img[int(h * (1 - frac)):, :]


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def normalize_depth(depth: np.ndarray, max_range: float = 100.0) -> np.ndarray:
    """Normalise a float depth image to 0‑255 for visualisation."""
    vis = np.clip(depth / max_range, 0.0, 1.0)
    return (vis * 255).astype(np.uint8)


def stack_debug(
    *images: np.ndarray,
    target_h: int = 240,
) -> np.ndarray:
    """Horizontally stack images (auto‑converted to BGR, same height)."""
    resized = []
    for img in images:
        if img is None:
            continue
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]
        scale = target_h / h
        img = cv2.resize(img, (int(w * scale), target_h))
        resized.append(img)
    if not resized:
        return np.zeros((target_h, 320, 3), dtype=np.uint8)
    return np.hstack(resized)
