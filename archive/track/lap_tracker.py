"""
lap_tracker.py
==============
Lap and progress tracker for Assetto Corsa.

Inspired by learn-to-race/l2r's ProgressTracker (l2r/env/tracker.py)
and GranTurismo reward (l2r/env/reward.py).  Adapted to work entirely
from AC telemetry (NormalizedSplinePosition, speed, lap_count) instead
of GPS coordinates, so no map geometry is required.

Key features (matching l2r patterns)
-------------------------------------
  • Progress reward:  Δspline_pos × PROGRESS_SCALE  (analogous to l2r's
    race_idx progression reward)
  • OOB penalty:  not applicable in AC (no GPS track boundary), but the
    spline-position can detect wrong-way driving
  • Stuck detection:  speed < threshold for N consecutive frames
  • Wrong-way detection:  spline_pos consistently decreasing
  • Lap completion:  spline_pos crosses 0 after exceeding 0.5 (halfway)
  • Movement smoothness:  log dimensionless jerk metric
    (Balasubramanian 2012, same formula as l2r's _log_dimensionless_jerk)
  • Per-lap metrics dict matching l2r's append_metrics() output structure
"""

from __future__ import annotations
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Constants ────────────────────────────────────────────────────
PROGRESS_SCALE   = 100.0        # reward units per full lap
OOB_PENALTY_BASE = 25.0         # flat penalty for wrong-way frame
WRONG_WAY_DELTA  = -0.03        # spline_pos drop threshold per tick
STUCK_SPEED_KPH  = 2.0          # below this = possibly stuck
STUCK_FRAMES     = 120          # consecutive slow frames = stuck
HALFWAY          = 0.50         # must pass this before lap completes
MPS_TO_KPH       = 3.6
EPSILON          = 1e-6


class LapMetrics:
    """Holds the metrics for a completed lap — mirrors l2r's metrics dict."""

    def __init__(self) -> None:
        self.lap_time:        float = 0.0
        self.avg_speed_kph:   float = 0.0
        self.num_infractions: int   = 0
        self.movement_smoothness: float = 0.0   # log-dimensionless jerk
        self.avg_steer_magnitude: float = 0.0   # mean |steer| per frame

    def as_dict(self) -> Dict:
        return {
            "lap_time_s":          round(self.lap_time, 2),
            "avg_speed_kph":       round(self.avg_speed_kph, 2),
            "num_infractions":     self.num_infractions,
            "movement_smoothness": round(self.movement_smoothness, 4),
            "avg_steer_magnitude": round(self.avg_steer_magnitude, 4),
        }


class LapTracker:
    """
    Tracks laps, progress, and driving quality for a session.

    Usage::

        tracker = LapTracker()
        ...
        reward = tracker.update(obs)
        done, reason = tracker.is_terminal()
        if done:
            metrics = tracker.last_metrics
    """

    def __init__(
        self,
        max_stuck_frames: int = STUCK_FRAMES,
        max_episode_secs: float = 600.0,
    ) -> None:
        self._max_stuck  = max_stuck_frames
        self._max_ep_s   = max_episode_secs
        self.laps_completed = 0
        self.num_infractions = 0
        self.all_lap_times: List[float] = []
        self.last_metrics: Optional[LapMetrics] = None
        self._reset_episode()

    # ── Public API ────────────────────────────────────────────────
    def reset(self) -> None:
        self.laps_completed  = 0
        self.num_infractions = 0
        self.all_lap_times   = []
        self.last_metrics    = None
        self._reset_episode()

    def update(self, spline_pos: float, speed_kph: float, steer_norm: float) -> float:
        """
        Call once per tick with current AC telemetry.

        :param spline_pos:  AC NormalizedSplinePosition  (0 … 1)
        :param speed_kph:   current speed in kph
        :param steer_norm:  normalised steering angle -1 … +1
        :return:            reward for this tick
        """
        now = time.monotonic()

        # Initialise on first call
        if self._lap_start is None:
            self._lap_start  = now
            self._last_pos   = spline_pos
            return 0.0

        reward = self._compute_reward(spline_pos, speed_kph)
        self._record(spline_pos, speed_kph, steer_norm)
        self._check_halfway(spline_pos)
        self._check_lap_complete(spline_pos, now)

        # Wrong-way infraction
        if self._is_wrong_way(spline_pos):
            reward -= OOB_PENALTY_BASE
            self.num_infractions += 1

        self._last_pos = spline_pos
        self._ep_ticks += 1
        self._ep_start = self._ep_start or now
        return reward

    def is_terminal(self) -> Tuple[bool, str]:
        """
        Returns (done, reason_string).
        Mirrors l2r's ProgressTracker.is_complete().
        """
        if self._stuck_frames >= self._max_stuck:
            return True, "stuck"
        if self._wrong_way_frames >= 30:
            return True, "wrong_way"
        if self._ep_start and (time.monotonic() - self._ep_start) > self._max_ep_s:
            return True, "timeout"
        return False, ""

    # ── Internals ─────────────────────────────────────────────────
    def _reset_episode(self) -> None:
        self._lap_start     : Optional[float] = None
        self._ep_start      : Optional[float] = None
        self._last_pos      : float = 0.0
        self._halfway_flag  : bool  = False
        self._stuck_frames  : int   = 0
        self._wrong_way_frames: int = 0
        self._ep_ticks      : int   = 0
        self._speeds        : deque = deque(maxlen=2000)
        self._steers        : deque = deque(maxlen=2000)

    def _compute_reward(self, spline_pos: float, speed_kph: float) -> float:
        """
        Progress reward (l2r GranTurismo style):
          reward = Δprogress × PROGRESS_SCALE
        Wrap-around handled for lap crossings.
        """
        delta = spline_pos - self._last_pos
        if delta < -0.5:        # crossed start/finish line forward
            delta += 1.0
        elif delta > 0.5:       # impossible jump backwards (GPS noise)
            delta = 0.0
        return delta * PROGRESS_SCALE

    def _record(self, spline_pos: float, speed_kph: float, steer_norm: float) -> None:
        self._speeds.append(speed_kph)
        self._steers.append(steer_norm)

        if speed_kph < STUCK_SPEED_KPH:
            self._stuck_frames += 1
        else:
            self._stuck_frames = 0

    def _check_halfway(self, spline_pos: float) -> None:
        if spline_pos >= HALFWAY:
            self._halfway_flag = True

    def _check_lap_complete(self, spline_pos: float, now: float) -> None:
        """Detect forward crossing of the start/finish line."""
        crossed = (
            self._halfway_flag
            and self._last_pos > 0.85
            and spline_pos < 0.15
        )
        if not crossed or self._lap_start is None:
            return

        lap_time = now - self._lap_start
        self.all_lap_times.append(lap_time)
        self.laps_completed += 1
        self.last_metrics = self._build_metrics(lap_time)

        # Reset for next lap
        self._lap_start    = now
        self._halfway_flag = False
        self._speeds.clear()
        self._steers.clear()

    def _is_wrong_way(self, spline_pos: float) -> bool:
        delta = spline_pos - self._last_pos
        if delta > -0.5:
            is_rev = delta < WRONG_WAY_DELTA
        else:
            is_rev = False     # lap crossing — not wrong way
        if is_rev:
            self._wrong_way_frames += 1
        else:
            self._wrong_way_frames = max(0, self._wrong_way_frames - 1)
        return is_rev

    def _build_metrics(self, lap_time: float) -> LapMetrics:
        m = LapMetrics()
        m.lap_time = lap_time
        speeds = list(self._speeds)
        steers = list(self._steers)
        if speeds:
            m.avg_speed_kph = float(np.mean(speeds))
        if steers:
            m.avg_steer_magnitude = float(np.mean(np.abs(steers)))
        if len(steers) > 4:
            m.movement_smoothness = _log_dimensionless_jerk(
                np.array(steers, dtype=np.float32),
                freq=30.0,
                data_type="accl",
            )
        m.num_infractions = self.num_infractions
        return m


# ── Smoothness metric (Balasubramanian 2012) ──────────────────────
# Identical algorithm to l2r's ProgressTracker._log_dimensionless_jerk
def _log_dimensionless_jerk(
    movement: np.ndarray,
    freq: float = 30.0,
    data_type: str = "accl",
) -> float:
    """
    Log dimensionless jerk — a smoothness metric where more negative =
    smoother.  Taken from l2r/env/tracker.py (Balasubramanian 2012).

    :param movement:  1-D signal (e.g. steering angle profile)
    :param freq:      sampling frequency in Hz
    :param data_type: 'speed' | 'accl' | 'jerk'
    :return:          log dimensionless jerk (smoother → more negative)
    """
    if data_type not in ("speed", "accl", "jerk"):
        raise ValueError("data_type must be 'speed', 'accl', or 'jerk'")

    movement_peak = max(abs(movement))
    if movement_peak < EPSILON:
        return 0.0

    dt            = 1.0 / freq
    movement_dur  = len(movement) * dt
    _p            = {"speed": 3, "accl": 1, "jerk": -1}
    p             = _p[data_type]
    scale         = (movement_dur ** p) / (movement_peak ** 2)

    if data_type == "speed":
        jerk = np.diff(movement, 2) / (dt ** 2)
    elif data_type == "accl":
        jerk = np.diff(movement, 1) / dt
    else:
        jerk = movement

    dim_jerk = -scale * float(np.sum(jerk ** 2)) * dt
    return float(np.log(abs(dim_jerk) + EPSILON))
