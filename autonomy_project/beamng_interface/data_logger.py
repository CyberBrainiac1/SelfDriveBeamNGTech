"""
Lightweight CSV + frame logger for telemetry replay and debugging.
"""

from __future__ import annotations
import csv
import os
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import CFG
from beamng_interface.sensors import SensorBundle
from beamng_interface.vehicle_control import ControlCommand


class DataLogger:
    """Logs telemetry to CSV and optionally saves camera frames."""

    def __init__(self) -> None:
        self._csv_file = None
        self._csv_writer = None
        self._tick: int = 0
        self._start_time: float = 0.0

    # ── lifecycle ──────────────────────────────────────────────────
    def start(self) -> None:
        dcfg = CFG.debug
        self._start_time = time.time()

        if dcfg.log_csv:
            path = Path(dcfg.csv_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._csv_file = open(path, "w", newline="")
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow([
                "tick", "time_s",
                "speed_kph", "steering_cmd", "throttle_cmd", "brake_cmd",
                "lane_offset", "pos_x", "pos_y", "pos_z",
            ])
            print(f"[logger] CSV logging to {path}")

        if dcfg.save_frames:
            Path(dcfg.frame_save_dir).mkdir(parents=True, exist_ok=True)
            print(f"[logger] Saving frames to {dcfg.frame_save_dir}/")

    def stop(self) -> None:
        if self._csv_file is not None:
            self._csv_file.close()
            self._csv_file = None
            print("[logger] CSV closed.")

    # ── per‑tick ───────────────────────────────────────────────────
    def log(
        self,
        sensor_data: SensorBundle,
        cmd: ControlCommand,
        lane_offset: float = 0.0,
    ) -> None:
        self._tick += 1
        elapsed = time.time() - self._start_time
        dcfg = CFG.debug

        # CSV row
        if self._csv_writer is not None:
            pos = sensor_data.position or (0, 0, 0)
            self._csv_writer.writerow([
                self._tick,
                f"{elapsed:.3f}",
                f"{sensor_data.speed_kph:.1f}",
                f"{cmd.steering:.4f}",
                f"{cmd.throttle:.4f}",
                f"{cmd.brake:.4f}",
                f"{lane_offset:.4f}",
                f"{pos[0]:.2f}",
                f"{pos[1]:.2f}",
                f"{pos[2]:.2f}",
            ])

        # Frame dump
        if dcfg.save_frames and sensor_data.colour_image is not None:
            fpath = os.path.join(dcfg.frame_save_dir, f"frame_{self._tick:06d}.png")
            cv2.imwrite(fpath, sensor_data.colour_image)
