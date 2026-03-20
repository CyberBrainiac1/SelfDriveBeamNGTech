"""
diagnostics_logger.py — Telemetry CSV writer + JSON summary + console printer.
"""

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from logger import get_logger


class DiagnosticsLogger:
    """
    Writes per-tick telemetry to a CSV file and a JSON summary on close.

    CSV columns:
        tick, timestamp, speed_kph, steering, throttle, brake,
        curvature, turn_dir, straight_prob, curve_conf,
        target_x, target_y, speed_target, heading_error,
        fit_quality, segment_type, commitment, n_lidar_pts

    Also prints a summary line to console every print_every_ticks ticks.
    """

    CSV_FIELDS = [
        "tick", "timestamp", "speed_kph", "steering", "throttle", "brake",
        "curvature", "turn_dir", "straight_prob", "curve_conf",
        "target_x", "target_y", "speed_target", "heading_error",
        "fit_quality", "segment_type", "commitment", "n_lidar_pts",
        "pos_x", "pos_y", "pos_z",
    ]

    def __init__(self, config=None):
        self.log_dir = Path("output/logs")
        self.diagnostics_dir = Path("output/diagnostics")
        self.csv_name = "selfdrive_latest.csv"
        self.summary_name = "selfdrive_summary.json"
        self.print_every_ticks: int = 10

        if config is not None:
            self._load_config(config)

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)

        self._logger = get_logger("DiagnosticsLogger", config)
        self._csv_path = self.log_dir / self.csv_name
        self._csv_file = None
        self._writer = None
        self._open_csv()

        self._tick: int = 0
        self._start_time: float = time.monotonic()
        self._row_buffer = []

        # Summary statistics
        self._speed_history = []
        self._steering_history = []
        self._errors = []

    def _load_config(self, config) -> None:
        try:
            lg = config.logging
            self.log_dir = Path(lg.log_dir)
            self.diagnostics_dir = Path(lg.diagnostics_dir)
            self.csv_name = str(lg.telemetry_csv_name)
            self.summary_name = str(lg.summary_json_name)
        except AttributeError:
            pass
        try:
            self.print_every_ticks = int(config.runtime.print_every_ticks)
        except AttributeError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        *,
        speed_kph: float = 0.0,
        steering: float = 0.0,
        throttle: float = 0.0,
        brake: float = 0.0,
        curvature: float = 0.0,
        turn_dir: str = "straight",
        straight_prob: float = 0.0,
        curve_conf: float = 0.0,
        target_x: float = 0.0,
        target_y: float = 0.0,
        speed_target: float = 0.0,
        heading_error: float = 0.0,
        fit_quality: float = 0.0,
        segment_type: str = "straight",
        commitment: float = 0.5,
        n_lidar_pts: int = 0,
        pos_x: float = 0.0,
        pos_y: float = 0.0,
        pos_z: float = 0.0,
        extra: Dict[str, Any] = None,
    ) -> None:
        """Write one telemetry row."""
        self._tick += 1
        ts = time.monotonic() - self._start_time

        row = {
            "tick": self._tick,
            "timestamp": f"{ts:.3f}",
            "speed_kph": f"{speed_kph:.2f}",
            "steering": f"{steering:.4f}",
            "throttle": f"{throttle:.3f}",
            "brake": f"{brake:.3f}",
            "curvature": f"{curvature:.5f}",
            "turn_dir": turn_dir,
            "straight_prob": f"{straight_prob:.3f}",
            "curve_conf": f"{curve_conf:.3f}",
            "target_x": f"{target_x:.3f}",
            "target_y": f"{target_y:.3f}",
            "speed_target": f"{speed_target:.2f}",
            "heading_error": f"{heading_error:.4f}",
            "fit_quality": f"{fit_quality:.4f}",
            "segment_type": segment_type,
            "commitment": f"{commitment:.3f}",
            "n_lidar_pts": n_lidar_pts,
            "pos_x": f"{pos_x:.3f}",
            "pos_y": f"{pos_y:.3f}",
            "pos_z": f"{pos_z:.3f}",
        }

        if self._writer is not None:
            try:
                self._writer.writerow(row)
            except Exception as e:
                self._logger.warning("CSV write error: %s", e)

        # Track for summary
        self._speed_history.append(speed_kph)
        self._steering_history.append(abs(steering))

        # Console print
        if self._tick % self.print_every_ticks == 0:
            self._print_console(row)

    def log_error(self, message: str) -> None:
        self._errors.append({"tick": self._tick, "message": message})
        self._logger.error(message)

    def close(self) -> None:
        """Flush, close CSV, write JSON summary."""
        self._write_summary()
        if self._csv_file is not None:
            try:
                self._csv_file.flush()
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._writer = None
        self._logger.info("DiagnosticsLogger closed. Wrote %d ticks.", self._tick)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open_csv(self) -> None:
        try:
            self._csv_file = open(self._csv_path, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._csv_file, fieldnames=self.CSV_FIELDS)
            self._writer.writeheader()
        except OSError as e:
            print(f"[DiagnosticsLogger] Could not open CSV: {e}")
            self._csv_file = None
            self._writer = None

    def _print_console(self, row: dict) -> None:
        msg = (
            f"[Tick {row['tick']:>5}] "
            f"spd={row['speed_kph']:>6} kph | "
            f"tgt={row['speed_target']:>6} kph | "
            f"steer={row['steering']:>7} | "
            f"thr={row['throttle']:>5} brk={row['brake']:>5} | "
            f"seg={row['segment_type']:>8} | "
            f"kappa={row['curvature']:>8} | "
            f"conf={row['curve_conf']:>5} | "
            f"commit={row['commitment']:>5} | "
            f"pts={row['n_lidar_pts']:>5}"
        )
        self._logger.info(msg)

    def _write_summary(self) -> None:
        import statistics
        summary_path = self.diagnostics_dir / self.summary_name
        elapsed = time.monotonic() - self._start_time

        summary = {
            "total_ticks": self._tick,
            "elapsed_seconds": round(elapsed, 2),
            "mean_speed_kph": round(statistics.mean(self._speed_history), 2) if self._speed_history else 0.0,
            "max_speed_kph": round(max(self._speed_history), 2) if self._speed_history else 0.0,
            "mean_abs_steering": round(statistics.mean(self._steering_history), 4) if self._steering_history else 0.0,
            "error_count": len(self._errors),
            "errors": self._errors[-20:],  # last 20 errors
        }

        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except OSError as e:
            self._logger.warning("Could not write summary JSON: %s", e)
