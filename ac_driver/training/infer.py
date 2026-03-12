"""
infer.py
========
Loads the trained model and provides a predict() function usable
from the main inference loop.
"""

from __future__ import annotations
import os
from typing import Optional

import cv2
import numpy as np

from config import CFG


class SteeringPredictor:
    """Wraps the Keras model for single-frame inference."""

    def __init__(self) -> None:
        self._model = None
        self._img_h = CFG.training.img_height
        self._img_w = CFG.training.img_width
        self._model_path = CFG.training.model_path

    # ── lifecycle ──────────────────────────────────────────────────
    def load(self) -> bool:
        """Load model from disk.  Returns True on success."""
        if not os.path.exists(self._model_path):
            print(f"[infer] Model not found at {self._model_path}")
            print("[infer] Run  python scripts/train.py  first.")
            return False
        try:
            import tensorflow as tf
            self._model = tf.keras.models.load_model(self._model_path)
            print(f"[infer] Model loaded from {self._model_path}")
            return True
        except Exception as exc:
            print(f"[infer] Failed to load model: {exc}")
            return False

    # ── inference ─────────────────────────────────────────────────
    def predict(self, bgr_frame: np.ndarray) -> Optional[float]:
        """
        Given a BGR numpy frame, return predicted steer_norm (-1 … +1).
        Returns None if model is not loaded.
        """
        if self._model is None:
            return None

        # Resize to model input
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self._img_w, self._img_h))
        x = rgb.astype(np.float32)[np.newaxis]   # (1, H, W, 3)

        pred = self._model.predict(x, verbose=0)[0][0]
        return float(np.clip(pred, -1.0, 1.0))
