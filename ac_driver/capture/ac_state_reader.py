"""
ac_state_reader.py
==================
Reads the JSON telemetry file written by the ACDriverApp in-game Python app.

The original ACDriver used a plain text file with a steering value only.
This version reads full telemetry (speed, steering, gear, rpm, throttle,
brake) from a JSON file and returns a typed dataclass.

If the file doesn't exist or is stale, the reader returns a zeroed state
so the driver can handle the absence gracefully.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from config import CFG


@dataclass
class ACState:
    speed_kph:    float = 0.0
    steer_deg:    float = 0.0
    steer_norm:   float = 0.0   # -1 … +1
    gear:         int   = 0
    rpm:          float = 0.0
    gas:          float = 0.0
    brake:        float = 0.0
    clutch:       float = 0.0
    lap:          int   = 0
    lap_progress: float = 0.0
    valid:        bool  = False   # False if file missing or stale


class ACStateReader:
    """Reads the telemetry JSON file on every call to read()."""

    # How old a state file can be before we treat it as stale (seconds)
    STALE_SECS: float = 2.0

    def __init__(self, path: str = None) -> None:
        self._path = path or CFG.paths.state_file
        self._last_mtime: float = 0.0

    def read(self) -> ACState:
        """Return the latest ACState from disk."""
        try:
            if not os.path.isfile(self._path):
                return ACState()

            mtime = os.path.getmtime(self._path)
            age = time.time() - mtime
            if age > self.STALE_SECS:
                # File hasn't been updated — game may not be running
                return ACState()

            with open(self._path, "r") as f:
                d = json.load(f)

            return ACState(
                speed_kph=float(d.get("speed_kph", 0)),
                steer_deg=float(d.get("steer_deg", 0)),
                steer_norm=float(d.get("steer_norm", 0)),
                gear=int(d.get("gear", 0)),
                rpm=float(d.get("rpm", 0)),
                gas=float(d.get("gas", 0)),
                brake=float(d.get("brake", 0)),
                clutch=float(d.get("clutch", 0)),
                lap=int(d.get("lap", 0)),
                lap_progress=float(d.get("lap_progress", 0)),
                valid=True,
            )

        except (json.JSONDecodeError, OSError, ValueError):
            return ACState()

    def wait_for_game(self, timeout_s: float = 60.0) -> bool:
        """
        Block until the state file appears and is fresh.
        Returns True when AC is detected, False if timeout expires.
        """
        print(f"[state_reader] Waiting for Assetto Corsa "
              f"(file: {self._path}) …")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            s = self.read()
            if s.valid:
                print("[state_reader] AC detected.")
                return True
            time.sleep(0.5)
        print("[state_reader] Timed out waiting for AC.")
        return False
