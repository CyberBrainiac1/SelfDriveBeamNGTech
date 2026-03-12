"""
data_collector.py
=================
Records (screen_frame, steering_label) pairs while YOU drive the car.
The neural model is then trained on this data via train_model.py.

Run from the repository root:
    python scripts/collect_data.py

HOW IT WORKS
------------
1. Start Assetto Corsa and enable the ACDriverApp widget in-game.
2. Drive normally — the collector automatically captures screen frames
   and reads your steering angle from the AC telemetry file.
3. Press 'q' in the preview window to stop.

Data is saved as  data/session_YYYYMMDD_HHMMSS.npz  containing:
  frames : float32 array (N, H, W, 3)  — RGB  normalised 0–1
  labels : float32 array (N,)          — steer_norm  -1 … +1
  metas  : float32 array (N, 3)        — [speed_kph, gas, brake]

ORIGINAL BUGS FIXED
-------------------
• Hardcoded path  C:\\Users\\denni\\...  → uses config.py
• Old PIL.ImageGrab                      → mss (4× faster)
• Saves object array .npy               → structured .npz (reliable)
• Normalises steering as (deg+450)/900  → clean  deg / 450  = -1…+1
• No preview or FPS display             → added
"""

from __future__ import annotations
import datetime
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import CFG
from capture.screen_capture import ScreenCapture
from capture.ac_state_reader import ACStateReader

# ── Tunables ──────────────────────────────────────────────────────
FRAMES_PER_SHARD = 5_000        # save a new .npz after this many frames
MIN_SPEED_KPH    = 5.0          # don't record when standing still
PREVIEW_RESIZE   = (400, 133)   # display size for the OpenCV window


def collect() -> None:
    cfg = CFG.training
    data_dir = Path(cfg.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    reader  = ACStateReader()
    capture = ScreenCapture()

    # Wait until AC is running
    if not reader.wait_for_game(timeout_s=120):
        print("[collector] AC not detected — aborting.")
        return

    frames_buf : list = []
    labels_buf : list = []
    metas_buf  : list = []
    shard_idx = 0
    tick = 0
    last_time = time.time()

    print("\n[collector] Recording. Drive the car!  Press 'q' to stop.\n")

    while True:
        # ── Grab ──────────────────────────────────────────────────
        bgr = capture.grab()
        if bgr is None:
            continue
        state = reader.read()

        tick += 1

        # Skip frames where the car is standing still
        if not state.valid or state.speed_kph < MIN_SPEED_KPH:
            cv2.waitKey(1)
            continue

        # ── Process frame ─────────────────────────────────────────
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        frame_f32 = rgb.astype(np.float32) / 255.0   # [0, 1]

        label = np.float32(state.steer_norm)          # -1 … +1
        meta  = np.array([state.speed_kph,
                          state.gas, state.brake], dtype=np.float32)

        frames_buf.append(frame_f32)
        labels_buf.append(label)
        metas_buf.append(meta)

        # ── Preview window ────────────────────────────────────────
        preview = cv2.resize(bgr, PREVIEW_RESIZE)
        fps = 1.0 / max(time.time() - last_time, 1e-6)
        last_time = time.time()
        cv2.putText(preview, f"{len(frames_buf)} frames  {fps:.0f} fps  "
                             f"steer={state.steer_norm:+.2f}",
                    (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.imshow("ACDriver — Data Collector", preview)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        # ── Periodic shard save ───────────────────────────────────
        if len(frames_buf) >= FRAMES_PER_SHARD:
            _save_shard(frames_buf, labels_buf, metas_buf, data_dir, shard_idx)
            shard_idx += 1
            frames_buf, labels_buf, metas_buf = [], [], []

    cv2.destroyAllWindows()
    capture.close()

    # Save remainder
    if frames_buf:
        _save_shard(frames_buf, labels_buf, metas_buf, data_dir, shard_idx)

    print(f"\n[collector] Done.  Total ticks: {tick}")


def _save_shard(
    frames: list, labels: list, metas: list,
    data_dir: Path, shard_idx: int,
) -> None:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = data_dir / f"session_{ts}_s{shard_idx:03d}.npz"
    np.savez_compressed(
        path,
        frames=np.stack(frames).astype(np.float32),
        labels=np.array(labels, dtype=np.float32),
        metas=np.stack(metas).astype(np.float32),
    )
    print(f"[collector] Saved {len(frames)} frames → {path}")


if __name__ == "__main__":
    collect()
