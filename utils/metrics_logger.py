"""
metrics_logger.py
=================
Session and per-lap metrics logger inspired by learn-to-race/l2r.

Records per-tick data to CSV and prints lap summary tables with l2r-style
fields: lap_time, avg_speed_kph, num_infractions, movement_smoothness,
avg_steer_magnitude.
"""

from __future__ import annotations
import csv
import os
import time
from typing import List, Optional

from track.lap_tracker import LapMetrics

_TICK_FIELDS = [
    "timestamp", "lap", "tick",
    "speed_kph", "steer_norm", "steering_cmd", "throttle", "brake",
    "lap_progress", "reward",
]

_LAP_FIELDS = [
    "lap", "lap_time_s", "avg_speed_kph", "num_infractions",
    "movement_smoothness", "avg_steer_magnitude",
]


class MetricsLogger:
    """
    Writes tick-level CSV and lap summary CSV.
    Prints lap summary to stdout on each completion.
    """

    def __init__(self, log_dir: str = "logs") -> None:
        os.makedirs(log_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._tick_path = os.path.join(log_dir, f"session_{ts}_ticks.csv")
        self._lap_path  = os.path.join(log_dir, f"session_{ts}_laps.csv")
        self._tick_file = open(self._tick_path, "w", newline="")
        self._lap_file  = open(self._lap_path,  "w", newline="")
        self._tick_w    = csv.DictWriter(self._tick_file, fieldnames=_TICK_FIELDS)
        self._lap_w     = csv.DictWriter(self._lap_file,  fieldnames=_LAP_FIELDS)
        self._tick_w.writeheader()
        self._lap_w.writeheader()
        self._lap_num   = 0
        self._tick_num  = 0

    def record_tick(
        self,
        *,
        speed_kph:    float,
        steer_norm:   float,
        steering_cmd: float,
        throttle:     float,
        brake:        float,
        lap_progress: float,
        reward:       float,
    ) -> None:
        self._tick_w.writerow({
            "timestamp":    round(time.time(), 3),
            "lap":          self._lap_num,
            "tick":         self._tick_num,
            "speed_kph":    round(speed_kph, 2),
            "steer_norm":   round(steer_norm, 4),
            "steering_cmd": round(steering_cmd, 4),
            "throttle":     round(throttle, 3),
            "brake":        round(brake, 3),
            "lap_progress": round(lap_progress, 4),
            "reward":       round(reward, 4),
        })
        self._tick_num += 1

    def record_lap(self, metrics: LapMetrics) -> None:
        self._lap_num += 1
        row = {"lap": self._lap_num, **metrics.as_dict()}
        self._lap_w.writerow(row)
        self._lap_file.flush()
        self._print_lap_summary(row)

    def close(self) -> None:
        self._tick_file.flush()
        self._tick_file.close()
        self._lap_file.close()
        print(f"\n[metrics] Saved ticks → {self._tick_path}")
        print(f"[metrics] Saved laps  → {self._lap_path}")

    @staticmethod
    def _print_lap_summary(row: dict) -> None:
        print(
            f"\n{'─'*48}\n"
            f"  LAP {row['lap']} COMPLETE\n"
            f"{'─'*48}\n"
            f"  Time        : {row['lap_time_s']} s\n"
            f"  Avg speed   : {row['avg_speed_kph']} kph\n"
            f"  Infractions : {row['num_infractions']}\n"
            f"  Smoothness  : {row['movement_smoothness']}  (more negative = smoother)\n"
            f"  Avg |steer| : {row['avg_steer_magnitude']}\n"
            f"{'─'*48}"
        )
