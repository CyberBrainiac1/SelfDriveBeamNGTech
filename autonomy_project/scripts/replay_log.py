#!/usr/bin/env python3
"""
replay_log.py — Replay a CSV telemetry log with optional frame playback.

Usage:
    python scripts/replay_log.py                          # default log path
    python scripts/replay_log.py --csv logs/telemetry.csv --frames logs/frames/

Plays back telemetry at the recorded rate.  If frames directory is
provided and contains matching frame_NNNNNN.png files, they are shown
alongside the telemetry.

Press 'q' to quit, SPACE to pause/resume, ←/→ to step.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay telemetry log")
    p.add_argument("--csv", default="logs/telemetry.csv", help="Path to CSV file")
    p.add_argument("--frames", default="logs/frames", help="Directory with saved frames")
    p.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not os.path.isfile(args.csv):
        print(f"[replay] CSV not found: {args.csv}")
        sys.exit(1)

    rows = []
    with open(args.csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("[replay] Empty CSV.")
        sys.exit(1)

    has_frames = os.path.isdir(args.frames)
    print(f"[replay] Loaded {len(rows)} rows.  Frames dir: {args.frames} ({'found' if has_frames else 'not found'})")
    print("[replay] SPACE=pause  q=quit  ←/→=step")

    paused = False
    idx = 0

    while 0 <= idx < len(rows):
        row = rows[idx]
        tick = int(row["tick"])

        # Build info text
        info = (
            f"tick={tick}  t={row['time_s']}s  "
            f"spd={row['speed_kph']}kph  str={row['steering_cmd']}  "
            f"thr={row['throttle_cmd']}  brk={row['brake_cmd']}  "
            f"lane_off={row['lane_offset']}"
        )

        # Try loading frame
        canvas = np.zeros((320, 640, 3), dtype=np.uint8)
        if has_frames:
            frame_path = os.path.join(args.frames, f"frame_{tick:06d}.png")
            if os.path.isfile(frame_path):
                canvas = cv2.imread(frame_path)
                if canvas is None:
                    canvas = np.zeros((320, 640, 3), dtype=np.uint8)

        cv2.putText(canvas, info, (10, canvas.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(canvas, f"[{idx + 1}/{len(rows)}]  {'PAUSED' if paused else 'PLAYING'}",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow("Replay", canvas)

        wait = 1 if paused else max(1, int(50 / args.speed))
        key = cv2.waitKey(wait) & 0xFF

        if key == ord("q"):
            break
        elif key == ord(" "):
            paused = not paused
        elif key == 81 or key == 2:  # left arrow
            idx = max(0, idx - 1)
            continue
        elif key == 83 or key == 3:  # right arrow
            idx += 1
            continue

        if not paused:
            idx += 1

    cv2.destroyAllWindows()
    print("[replay] Done.")


if __name__ == "__main__":
    main()
