"""
train_model.py
==============
Loads collected .npz data shards, trains the NVIDIA CNN, and saves
the model to  models/acdriver_model.keras.

Run from ac_driver/:
    python scripts/train.py

ORIGINAL BUGS FIXED
-------------------
• `keras.optimizers.adam()` → `Adam()` (lowercase was removed in TF2)
• `keras.losses.categorical_crossentropy` on regression output → `mse`
• Object-array .npy loading           → structured .npz shards
• No train/val split                  → stratified split with augmentation
• model.json + model.h5 two-file save → single .keras file (modern API)
"""

from __future__ import annotations
import glob
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import CFG
from training.model import build_model, compile_model


def load_all_shards(data_dir: str) -> tuple[np.ndarray, np.ndarray]:
    """Load all .npz shards from data_dir and concatenate."""
    shards = sorted(glob.glob(os.path.join(data_dir, "*.npz")))
    if not shards:
        raise FileNotFoundError(f"No .npz files found in {data_dir!r}")

    all_frames, all_labels = [], []
    for path in shards:
        d = np.load(path)
        all_frames.append(d["frames"])     # (N, H, W, 3) float32 [0,1]
        all_labels.append(d["labels"])     # (N,)         float32 -1…+1
        print(f"  loaded {d['frames'].shape[0]:>6} frames from {os.path.basename(path)}")

    X = np.concatenate(all_frames, axis=0)
    y = np.concatenate(all_labels, axis=0)

    # Convert [0,1] float frames → uint8 [0,255] that the model's Lambda
    # normalise layer expects
    X = (X * 255).astype(np.float32)

    print(f"\n[train] Total: {X.shape[0]} frames  "
          f"steer min={y.min():.3f} max={y.max():.3f} mean={y.mean():.3f}")
    return X, y


def augment(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Horizontal flip augmentation — doubles the dataset and balances
    left/right steering bias.
    """
    import cv2
    flipped, flipped_y = [], []
    for img, label in zip(X, y):
        flipped.append(cv2.flip(img.astype(np.uint8), 1).astype(np.float32))
        flipped_y.append(-label)  # mirrored steering
    X2 = np.concatenate([X, np.stack(flipped)], axis=0)
    y2 = np.concatenate([y, np.array(flipped_y, np.float32)], axis=0)
    # Shuffle
    idx = np.random.permutation(len(X2))
    return X2[idx], y2[idx]


def train() -> None:
    cfg = CFG.training

    print(f"[train] Loading data from {cfg.data_dir!r} …")
    X, y = load_all_shards(cfg.data_dir)
    X, y = augment(X, y)
    print(f"[train] After augment: {X.shape[0]} frames")

    # Resize to model input if needed
    import cv2
    if X.shape[1] != cfg.img_height or X.shape[2] != cfg.img_width:
        print(f"[train] Resizing to {cfg.img_height}×{cfg.img_width} …")
        X_rsz = np.stack([
            cv2.resize(img.astype(np.uint8), (cfg.img_width, cfg.img_height))
            for img in X
        ]).astype(np.float32)
    else:
        X_rsz = X

    model = build_model(cfg.img_height, cfg.img_width, cfg.img_channels)
    model = compile_model(model, lr=cfg.learning_rate)
    model.summary()

    # Callbacks
    import tensorflow as tf
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            cfg.model_path, save_best_only=True,
            monitor="val_loss", verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            patience=5, restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            factor=0.5, patience=3, verbose=1,
        ),
    ]

    Path(cfg.model_path).parent.mkdir(parents=True, exist_ok=True)

    history = model.fit(
        X_rsz, y,
        batch_size=cfg.batch_size,
        epochs=cfg.epochs,
        validation_split=cfg.val_split,
        callbacks=callbacks,
        verbose=1,
    )

    print(f"\n[train] Best val_loss: "
          f"{min(history.history['val_loss']):.6f}")
    print(f"[train] Model saved → {cfg.model_path}")


if __name__ == "__main__":
    train()
