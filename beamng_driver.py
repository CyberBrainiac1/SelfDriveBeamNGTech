#!/usr/bin/env python3
"""
beamng_driver.py
================
Single-file autonomous driving script for BeamNG.tech.

Runs a perception → planning → control loop inside BeamNG.tech:
  1. Connects to (or launches) BeamNG.tech
  2. Spawns a vehicle on west_coast_usa
  3. Attaches a front camera, electrics, damage sensors
  4. Detects lane lines with OpenCV (classical CV, no ML required)
  5. Steers and controls speed via two PID controllers
  6. Shows a live debug window (press 'q' to quit, 'e' for emergency stop)

Usage
-----
  python beamng_driver.py
  python beamng_driver.py --speed 50 --no-overlay
  python beamng_driver.py --beamng-home "C:\\BeamNG.tech"

Prerequisites
-------------
  pip install beamngpy opencv-python numpy
  BeamNG.tech must be installed (research/educational licence).
  Set --beamng-home to your install folder, or edit BEAMNG_HOME below.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


LOCAL_BEAMNGPY_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BeamNGpy", "src")
if os.path.isdir(LOCAL_BEAMNGPY_SRC) and LOCAL_BEAMNGPY_SRC not in sys.path:
    sys.path.insert(0, LOCAL_BEAMNGPY_SRC)

# ── Default configuration (edit here or override with CLI flags) ────────────
BEAMNG_HOME: str = r"C:\Beamngtech\BeamNG.tech.v0.38.3.0"   # ← set your BeamNG.tech install path
BEAMNG_HOST: str = "localhost"
BEAMNG_PORT: int = 64256

MAP_NAME: str = "west_coast_usa"
VEHICLE_MODEL: str = "etk800"
SPAWN_POS: Tuple[float, float, float] = (-717.121, 101.0, 118.675)
SPAWN_ROT: Tuple[float, float, float, float] = (0, 0, 0.3826834, 0.9238795)

CAM_RESOLUTION: Tuple[int, int] = (640, 480)
CAM_FOV: int = 70
CAM_POS: Tuple[float, float, float] = (0.0, 0.9, 1.5)
CAM_DIR: Tuple[float, float, float] = (0, -1, 0)
CAM_NEAR_FAR: Tuple[float, float] = (0.01, 300.0)

TARGET_SPEED_KPH: float = 40.0
MAX_SPEED_KPH: float = 60.0
LOOP_HZ: float = 20.0
BEAMNG_STEPS: int = 10           # sim steps advanced per tick
CAM_UPDATE_TIME_S: float = 0.05
DEFAULT_STEERING_LOG_CSV: str = os.path.join("logs", "steering_output.csv")
DEFAULT_ROUTE_IDS: Dict[str, float] = {
    "west_coast_usa": 59564.0,
    "hirochi_raceway": 23134.0,
    "automation_test_track": 23214.0,
    "small_island": 27782.0,
}
TRACK_WAYPOINT_PRESETS: Dict[str, List[str]] = {
    "hirochi_raceway": [
        "hr_start",
        "quickrace_wp1",
        "quickrace_wp2",
        "quickrace_wp3",
        "quickrace_wp4",
        "quickrace_wp11",
        "hr_start",
    ],
}
TRACK_WAYPOINT_SPAWN_PRESETS: Dict[str, Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]] = {
    "hirochi_raceway": (
        (-408.5, 260.2, 25.22),
        (-0.006664, -0.002505, -0.2799, 0.96),
    ),
}
TRACK_MISSION_PRESETS: Dict[str, str] = {
    "automation_test_track": os.path.join(
        "gameplay", "missions", "automation_test_track", "timeTrial", "008-Race", "race.race.json"
    ),
}
TRACK_AI_LONG_LAPS: int = 100000
TRACK_LINE_SPACING_M: float = 8.0
TRACK_LINE_START_MIN_DISTANCE_M: float = 6.0
TRACK_LINE_MIN_SPEED_KPH: float = 25.0
TRACK_LINE_ACCEL_MPS2: float = 5.5
TRACK_LINE_BRAKE_MPS2: float = 9.0

# Perception (HSV road mask + Canny + Hough)
ROAD_HSV_LOWER: Tuple[int, int, int] = (0, 0, 50)
ROAD_HSV_UPPER: Tuple[int, int, int] = (180, 80, 180)
CANNY_LOW: int = 50
CANNY_HIGH: int = 150
ROI_TOP_FRAC: float = 0.50
ROI_BOTTOM_FRAC: float = 0.74
BLUR_KERNEL: int = 5
HOUGH_THRESHOLD: int = 30
HOUGH_MIN_LINE: int = 40
HOUGH_MAX_GAP: int = 100
NO_ROAD_LIMIT: int = 10          # frames without road before emergency stop
OBSTACLE_CLOSE_M: float = 15.0
OBSTACLE_FRAC: float = 0.05
SINGLE_LANE_OFFSET_LIMIT: float = 0.35
ROUTE_LOOKAHEAD_BASE_M: float = 12.0
ROUTE_LOOKAHEAD_SPEED_GAIN: float = 0.65
ROUTE_SEARCH_WINDOW: int = 80
ROUTE_SPEED_PREVIEW_MIN_M: float = 35.0
ROUTE_SPEED_PREVIEW_BASE_M: float = 16.0
ROUTE_SPEED_PREVIEW_TIME_S: float = 2.8
ROUTE_SPEED_PREVIEW_MAX_M: float = 75.0
ROUTE_CURVATURE_MIN_WINDOW_M: float = 8.0
ROUTE_CURVATURE_MAX_WINDOW_M: float = 28.0
ROUTE_MAX_LATERAL_ACCEL_MPS2: float = 3.6
ROUTE_CURVE_SPEED_SAFETY: float = 0.90
ROUTE_RESAMPLE_SPACING_M: float = 2.5
ROUTE_SMOOTH_WINDOW: int = 5
ROUTE_MIN_SPEED_KPH: float = 8.0
ROUTE_MAX_SPEED_KPH: float = 180.0
ROUTE_LATERAL_GAIN: float = 2.2
ROUTE_HEADING_GAIN: float = 1.6
ROUTE_CURVE_MIN_SPEED_KPH: float = 18.0
ROUTE_RECOVERY_LATERAL_M: float = 0.9
ROUTE_RECOVERY_HEADING_DEG: float = 7.0
ROUTE_SEVERE_LATERAL_M: float = 1.8
ROUTE_SEVERE_HEADING_DEG: float = 16.0
ROUTE_STEER_DEADBAND: float = 0.02
ROUTE_STEER_GAIN: float = 1.25
ROUTE_STEER_FILTER_ALPHA: float = 0.65
ROUTE_STEER_MAX_STEP: float = 0.24
CUSTOM_DAMAGE_STOP: float = 200.0
CUSTOM_ROUTE_LOST_FRAMES: int = 12
CUSTOM_ROUTE_LOST_OFFSET: float = 0.95
CUSTOM_ROUTE_LOST_HEADING_DEG: float = 70.0
LAP_ENTRY_RADIUS_M: float = 20.0
LAP_EXIT_RADIUS_M: float = 45.0
LAP_MIN_DISTANCE_FACTOR: float = 0.55
LAP_MIN_DISTANCE_M: float = 250.0
LAP_MIN_TIME_S: float = 15.0

# Steering PID
STEER_KP: float = 0.8
STEER_KI: float = 0.0
STEER_KD: float = 0.15
STEER_DEADBAND: float = 0.01
STEER_MAX_RATE: float = 0.15

# Speed PID
SPEED_KP: float = 0.15
SPEED_KI: float = 0.01
SPEED_KD: float = 0.05
SPEED_COAST_KPH: float = 2.0
SPEED_BRAKE_KP: float = 0.10
SPEED_BRAKE_STRONG_DELTA_KPH: float = 10.0
SPEED_BRAKE_EXTRA_GAIN: float = 0.08
THROTTLE_MAX: float = 0.6
BRAKE_MAX: float = 1.0


# ── PID controllers ──────────────────────────────────────────────────────────

class SteeringPID:
    """PID lateral controller with deadband and rate limiting."""

    def __init__(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_t = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_t = time.monotonic()

    def compute(self, offset: float) -> float:
        """
        offset: lane-centre deviation, -1 (left) … +1 (right).
        Returns steering command in [-1, +1].
        """
        now = time.monotonic()
        dt = max(now - self._prev_t, 1e-3)
        self._prev_t = now

        error = offset
        if abs(error) < STEER_DEADBAND:
            error = 0.0

        self._integral += error * dt
        self._integral = max(-1.0, min(1.0, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        output = STEER_KP * error + STEER_KI * self._integral + STEER_KD * derivative
        output = max(-1.0, min(1.0, output))

        # Rate limiting
        delta = output - self._prev_output
        if abs(delta) > STEER_MAX_RATE:
            output = self._prev_output + STEER_MAX_RATE * (1.0 if delta > 0 else -1.0)
        self._prev_output = output
        return output


class SpeedPID:
    """PID longitudinal controller → (throttle, brake)."""

    def __init__(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_t = time.monotonic()

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_t = time.monotonic()

    def compute(self, target_kph: float, current_kph: float) -> Tuple[float, float]:
        """Returns (throttle, brake) each in [0, 1]."""
        now = time.monotonic()
        dt = max(now - self._prev_t, 1e-3)
        self._prev_t = now

        error = target_kph - current_kph
        if abs(error) < SPEED_COAST_KPH:
            self._integral *= 0.5
            self._prev_error = error
            return 0.0, 0.0

        if error < 0.0:
            overspeed = abs(error)
            # Route speed targets can drop sharply before a bend. Dump positive
            # integral and brake directly so we do not keep accelerating into the turn.
            self._integral = min(self._integral, 0.0)
            brake = SPEED_BRAKE_KP * overspeed
            if overspeed > SPEED_BRAKE_STRONG_DELTA_KPH:
                brake += SPEED_BRAKE_EXTRA_GAIN * (overspeed - SPEED_BRAKE_STRONG_DELTA_KPH)
            self._prev_error = error
            return 0.0, min(brake, BRAKE_MAX)

        self._integral += error * dt
        self._integral = max(0.0, min(50.0, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        raw = SPEED_KP * error + SPEED_KI * self._integral + SPEED_KD * derivative
        if raw > 0:
            return min(raw, THROTTLE_MAX), 0.0
        return 0.0, min(abs(raw), BRAKE_MAX)


class RouteSteeringFilter:
    """Ignore tiny route noise, but react faster than the generic lane PID on real bends."""

    def __init__(self) -> None:
        self._prev_output = 0.0

    def reset(self) -> None:
        self._prev_output = 0.0

    def compute(self, target: float) -> float:
        target = max(-1.0, min(1.0, float(target) * ROUTE_STEER_GAIN))
        if abs(target) < ROUTE_STEER_DEADBAND:
            target = 0.0
        else:
            scaled = (abs(target) - ROUTE_STEER_DEADBAND) / max(1.0 - ROUTE_STEER_DEADBAND, 1e-6)
            target = math.copysign(min(1.0, scaled), target)

        blended = self._prev_output + ROUTE_STEER_FILTER_ALPHA * (target - self._prev_output)
        max_step = ROUTE_STEER_MAX_STEP * (1.25 if abs(target) > 0.45 else 1.0)
        delta = blended - self._prev_output
        if abs(delta) > max_step:
            blended = self._prev_output + max_step * (1.0 if delta > 0.0 else -1.0)

        self._prev_output = max(-1.0, min(1.0, blended))
        if target == 0.0 and abs(self._prev_output) < (ROUTE_STEER_DEADBAND * 0.5):
            self._prev_output = 0.0
        return self._prev_output


# ── Lane detection ───────────────────────────────────────────────────────────

@dataclass
class LaneResult:
    offset: float = 0.0       # -1 … +1, positive = road centre is right of image centre
    confidence: float = 0.0   # 0 = no road, 1 = both lanes found
    overlay: Optional[np.ndarray] = None


@dataclass
class RoutePlan:
    road_id: float
    points: List[np.ndarray]
    looped: bool = False
    index: int = 0


@dataclass
class RouteControl:
    steering_target: float = 0.0
    speed_target_kph: float = 0.0
    lateral_error_m: float = 0.0
    heading_error_deg: float = 0.0
    progress_index: int = 0
    lookahead_m: float = 0.0
    curve_speed_cap_kph: float = 0.0
    preview_curvature: float = 0.0
    preview_distance_m: float = 0.0


@dataclass
class LapTrackerState:
    laps_completed: int = 0
    progress_index: int = 0
    last_lap_time_s: float = 0.0
    started_t: Optional[float] = None
    lap_start_t: Optional[float] = None
    start_pos: Optional[np.ndarray] = None
    last_pos: Optional[np.ndarray] = None
    route_length_hint_m: float = 0.0
    distance_since_lap_m: float = 0.0
    left_start_zone: bool = False
    lap_times_s: List[float] = field(default_factory=list)


@dataclass
class AITrackPreset:
    controller: str
    name: str
    route_plan: Optional[RoutePlan] = None
    waypoints: Optional[List[str]] = None
    line: Optional[List[Dict[str, object]]] = None
    spawn_pos: Optional[Tuple[float, float, float]] = None
    spawn_quat: Optional[Tuple[float, float, float, float]] = None


def _to_colour_image(value: object) -> Optional[np.ndarray]:
    """Convert BeamNG camera colour output into a BGR image or None."""
    if value is None:
        return None
    try:
        img = np.asarray(value)
    except Exception:
        return None
    if img.size == 0 or img.ndim != 3:
        return None
    if img.shape[2] == 4:
        return img[:, :, 2::-1]
    if img.shape[2] == 3:
        return img[:, :, ::-1]
    return None


def _to_depth_image(value: object) -> Optional[np.ndarray]:
    """Convert BeamNG camera depth output into a 2D float image or None."""
    if value is None:
        return None
    try:
        depth = np.asarray(value, dtype=np.float32)
    except Exception:
        return None
    if depth.size == 0:
        return None
    if depth.ndim == 3 and depth.shape[2] == 1:
        depth = depth[:, :, 0]
    if depth.ndim != 2:
        return None
    return depth


def _attach_vehicle_sensor(vehicle: object, name: str, sensor: object) -> None:
    """Attach classic vehicle sensors in a BeamNGpy-version-compatible way."""
    if hasattr(vehicle, "attach_sensor"):
        vehicle.attach_sensor(name, sensor)
        return
    sensors = getattr(vehicle, "sensors", None)
    if sensors is not None and hasattr(sensors, "attach"):
        sensors.attach(name, sensor)
        return
    if hasattr(sensor, "attach"):
        sensor.attach(vehicle, name)
        return
    raise RuntimeError(f"Unable to attach sensor '{name}' with this BeamNGpy version.")


def _normalize_xy(vec: np.ndarray) -> np.ndarray:
    out = np.array([float(vec[0]), float(vec[1])], dtype=np.float64)
    norm = np.linalg.norm(out)
    if norm < 1e-9:
        return np.array([1.0, 0.0], dtype=np.float64)
    return out / norm


def _yaw_to_quat(yaw_rad: float) -> Tuple[float, float, float, float]:
    return (0.0, 0.0, math.sin(yaw_rad * 0.5), math.cos(yaw_rad * 0.5))


def _quat_forward_xy(rot_quat: Tuple[float, float, float, float]) -> np.ndarray:
    qx, qy, qz, qw = (float(value) for value in rot_quat)
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    rot = np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )
    forward = rot @ np.array([0.0, -1.0, 0.0], dtype=np.float64)
    return _normalize_xy(forward[:2])


def _road_length(points: List[np.ndarray]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += float(np.linalg.norm(b[:2] - a[:2]))
    return total


def _wrap_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def _rotate_looped_route_to_best_start(points: List[np.ndarray]) -> List[np.ndarray]:
    n = len(points)
    if n < 40:
        return points
    headings: List[float] = []
    for idx in range(n):
        nxt = (idx + 1) % n
        delta = points[nxt][:2] - points[idx][:2]
        headings.append(math.atan2(float(delta[1]), float(delta[0])))

    best_idx = 0
    best_score = float("inf")
    for idx in range(0, n, 4):
        score = 0.0
        samples = 18
        for step in range(samples):
            a = headings[(idx + step) % n]
            b = headings[(idx + step + 1) % n]
            score += abs(_wrap_angle(b - a))
        if score < best_score:
            best_score = score
            best_idx = idx
    return points[best_idx:] + points[:best_idx]


def _resample_route_points(points: List[np.ndarray], spacing_m: float, looped: bool) -> List[np.ndarray]:
    if len(points) < 4 or spacing_m <= 0.0:
        return points

    work_points = [np.asarray(point, dtype=np.float64).copy() for point in points]
    if looped:
        work_points = work_points + [work_points[0].copy()]

    cumulative = [0.0]
    for a, b in zip(work_points, work_points[1:]):
        cumulative.append(cumulative[-1] + float(np.linalg.norm(b[:3] - a[:3])))
    total_length = cumulative[-1]
    if total_length < spacing_m * 2.0:
        return points

    sample_distances = list(np.arange(0.0, total_length, spacing_m, dtype=np.float64))
    if not sample_distances or (total_length - sample_distances[-1]) > (spacing_m * 0.4):
        sample_distances.append(total_length)

    resampled: List[np.ndarray] = []
    seg_idx = 0
    for distance in sample_distances:
        while seg_idx + 1 < len(cumulative) and cumulative[seg_idx + 1] < distance:
            seg_idx += 1
        if seg_idx + 1 >= len(work_points):
            resampled.append(work_points[-1].copy())
            continue
        seg_start = cumulative[seg_idx]
        seg_len = max(cumulative[seg_idx + 1] - seg_start, 1e-6)
        ratio = float((distance - seg_start) / seg_len)
        ratio = max(0.0, min(1.0, ratio))
        point = work_points[seg_idx] * (1.0 - ratio) + work_points[seg_idx + 1] * ratio
        resampled.append(point.astype(np.float64))

    if looped and len(resampled) > 1:
        resampled = resampled[:-1]
    if len(resampled) < 4:
        return points

    smooth_radius = max(0, ROUTE_SMOOTH_WINDOW // 2)
    if smooth_radius == 0:
        return resampled

    smoothed: List[np.ndarray] = []
    n = len(resampled)
    for idx in range(n):
        neighborhood: List[np.ndarray] = []
        for step in range(-smooth_radius, smooth_radius + 1):
            sample_idx = idx + step
            if looped:
                sample_idx %= n
            elif sample_idx < 0 or sample_idx >= n:
                continue
            neighborhood.append(resampled[sample_idx])
        smoothed.append(np.mean(neighborhood, axis=0))
    return smoothed


def _get_route_plan(
    roads: Dict[Any, Dict[str, Any]],
    map_name: str,
    requested_road_id: Optional[float] = None,
) -> RoutePlan:
    chosen_key: Optional[Any] = None
    if requested_road_id is not None:
        for key in roads.keys():
            try:
                if abs(float(key) - float(requested_road_id)) < 1e-6:
                    chosen_key = key
                    break
            except Exception:
                continue
        if chosen_key is None:
            raise ValueError(f"Road id {requested_road_id} not found on map '{map_name}'.")
    else:
        default_key = DEFAULT_ROUTE_IDS.get(map_name)
        if default_key is not None:
            for key in roads.keys():
                try:
                    if abs(float(key) - default_key) < 1e-6:
                        chosen_key = key
                        break
                except Exception:
                    continue
        if chosen_key is None:
            longest_len = -1.0
            for key, data in roads.items():
                edges = data.get("edges") or []
                points = [np.asarray(edge["middle"], dtype=np.float64) for edge in edges]
                length = _road_length(points)
                if length > longest_len:
                    longest_len = length
                    chosen_key = key
    if chosen_key is None:
        raise RuntimeError(f"No drivable road candidate found for map '{map_name}'.")

    route_data = roads[chosen_key]
    points = [np.asarray(edge["middle"], dtype=np.float64) for edge in route_data.get("edges") or []]
    if str(route_data.get("flipDirection", "0")) == "1":
        points.reverse()
    if len(points) < 4:
        raise RuntimeError(f"Road {chosen_key} on '{map_name}' does not have enough centerline points.")

    looped = str(route_data.get("looped", "0")) == "1"
    if not looped:
        looped = float(np.linalg.norm(points[0][:2] - points[-1][:2])) < 20.0
    if looped:
        points = _rotate_looped_route_to_best_start(points)
    points = _resample_route_points(points, ROUTE_RESAMPLE_SPACING_M, looped)

    return RoutePlan(road_id=float(chosen_key), points=points, looped=looped)


def _route_spawn_pose(route: RoutePlan) -> Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]:
    start = route.points[0].copy()
    next_pt = route.points[1]
    forward = _normalize_xy(next_pt[:2] - start[:2])
    yaw = -math.atan2(float(forward[1]), float(forward[0])) - (math.pi * 0.5)
    start[2] += 0.35
    return (float(start[0]), float(start[1]), float(start[2])), _yaw_to_quat(yaw)


def _rotate_looped_route_to_spawn(
    points: List[np.ndarray],
    spawn_pos: Tuple[float, float, float],
    spawn_quat: Tuple[float, float, float, float],
) -> List[np.ndarray]:
    if len(points) < 4:
        return points

    spawn_xy = np.asarray(spawn_pos[:2], dtype=np.float64)
    forward = _quat_forward_xy(spawn_quat)
    best_idx = 0
    best_dist = float("inf")
    forward_idx = 0
    forward_dist = float("inf")
    fallback_idx = 0
    fallback_dist = float("inf")

    for idx, point in enumerate(points):
        delta = np.asarray(point[:2], dtype=np.float64) - spawn_xy
        dist = float(np.linalg.norm(delta))
        if dist < fallback_dist:
            fallback_dist = dist
            fallback_idx = idx
        if np.dot(delta, forward) >= 0.0 and dist >= TRACK_LINE_START_MIN_DISTANCE_M and dist < forward_dist:
            forward_dist = dist
            forward_idx = idx
        if np.dot(delta, forward) >= -2.0 and dist < best_dist:
            best_dist = dist
            best_idx = idx

    if forward_dist < float("inf"):
        best_idx = forward_idx
    elif best_dist == float("inf"):
        best_idx = fallback_idx
    return points[best_idx:] + points[:best_idx]


def _wrapped_index(n: int, idx: int) -> int:
    return idx % n


def _nearest_route_index(route: RoutePlan, pos: np.ndarray) -> int:
    n = len(route.points)
    if n == 0:
        return 0

    pos_xy = np.asarray(pos[:2], dtype=np.float64)
    search_indices: List[int] = []
    if route.looped:
        back_window = max(4, ROUTE_SEARCH_WINDOW // 4)
        for step in range(-back_window, ROUTE_SEARCH_WINDOW + 1):
            search_indices.append(_wrapped_index(n, route.index + step))
    else:
        start_idx = max(0, route.index - 4)
        end_idx = min(n, route.index + ROUTE_SEARCH_WINDOW + 1)
        search_indices.extend(range(start_idx, end_idx))

    best_idx = route.index
    best_dist = float("inf")
    for idx in search_indices:
        dist = float(np.linalg.norm(route.points[idx][:2] - pos_xy))
        if dist < best_dist:
            best_dist = dist
            best_idx = idx

    route.index = best_idx
    return best_idx


def _update_lap_tracker(
    tracker: LapTrackerState,
    route: Optional[RoutePlan],
    progress_index: int,
    pos: np.ndarray,
) -> None:
    if route is None:
        return

    now = time.perf_counter()
    pos = np.asarray(pos[:3], dtype=np.float64)
    if tracker.started_t is None:
        tracker.started_t = now
        tracker.lap_start_t = now
        tracker.progress_index = progress_index
        if tracker.start_pos is None:
            tracker.start_pos = pos.copy()
        tracker.last_pos = pos.copy()
        return

    tracker.progress_index = progress_index
    if tracker.last_pos is not None:
        step_distance = float(np.linalg.norm(pos[:2] - tracker.last_pos[:2]))
        if step_distance < 30.0:
            tracker.distance_since_lap_m += step_distance
    tracker.last_pos = pos.copy()

    if tracker.start_pos is None:
        return

    start_distance = float(np.linalg.norm(pos[:2] - tracker.start_pos[:2]))
    if start_distance >= LAP_EXIT_RADIUS_M:
        tracker.left_start_zone = True

    if not tracker.left_start_zone or start_distance > LAP_ENTRY_RADIUS_M:
        return

    lap_elapsed = now - (tracker.lap_start_t or now)
    total_elapsed = now - tracker.started_t
    min_distance = max(LAP_MIN_DISTANCE_M, tracker.route_length_hint_m * LAP_MIN_DISTANCE_FACTOR)
    if (
        lap_elapsed < LAP_MIN_TIME_S
        or total_elapsed < LAP_MIN_TIME_S
        or tracker.distance_since_lap_m < min_distance
    ):
        return

    tracker.laps_completed += 1
    tracker.last_lap_time_s = lap_elapsed
    tracker.lap_times_s.append(lap_elapsed)
    tracker.lap_start_t = now
    tracker.distance_since_lap_m = 0.0
    tracker.left_start_zone = False
    print(f"\n[lap] Completed lap {tracker.laps_completed} in {lap_elapsed:.1f}s")


def _densify_track_points(points: List[np.ndarray], spacing_m: float, closed: bool) -> List[np.ndarray]:
    if len(points) < 2 or spacing_m <= 0.0:
        return [np.asarray(point, dtype=np.float64).copy() for point in points]

    work_points = [np.asarray(point, dtype=np.float64).copy() for point in points]
    if closed:
        work_points.append(work_points[0].copy())

    dense: List[np.ndarray] = [work_points[0].copy()]
    for start, end in zip(work_points, work_points[1:]):
        delta = end - start
        seg_len = float(np.linalg.norm(delta[:2]))
        steps = max(1, int(math.ceil(seg_len / spacing_m)))
        for step in range(1, steps + 1):
            ratio = step / steps
            point = start * (1.0 - ratio) + end * ratio
            dense.append(point.astype(np.float64))

    if closed and len(dense) > 1:
        dense = dense[:-1]
    return dense


def _track_line_speed_profile(
    points: List[np.ndarray],
    target_speed_kph: float,
    aggression: float,
    closed: bool,
) -> List[float]:
    if len(points) < 3:
        return [max(TRACK_LINE_MIN_SPEED_KPH / 3.6, target_speed_kph / 3.6)] * len(points)

    n = len(points)
    max_speed_mps = max(TRACK_LINE_MIN_SPEED_KPH / 3.6, target_speed_kph / 3.6)
    aggression_norm = float(np.clip((aggression - 0.3) / 0.7, 0.0, 1.0))
    max_lat_accel = 5.2 + 3.8 * aggression_norm
    speed_caps = [max_speed_mps] * n

    for idx in range(n):
        prev_idx = (idx - 2) % n if closed else max(idx - 2, 0)
        next_idx = (idx + 2) % n if closed else min(idx + 2, n - 1)
        prev_point = points[prev_idx][:2]
        curr_point = points[idx][:2]
        next_point = points[next_idx][:2]

        seg_a = curr_point - prev_point
        seg_b = next_point - curr_point
        len_a = float(np.linalg.norm(seg_a))
        len_b = float(np.linalg.norm(seg_b))
        if len_a < 1.0 or len_b < 1.0:
            continue

        heading_a = math.atan2(float(seg_a[1]), float(seg_a[0]))
        heading_b = math.atan2(float(seg_b[1]), float(seg_b[0]))
        turn = abs(_wrap_angle(heading_b - heading_a))
        curvature = turn / max(len_a + len_b, 1e-3)
        if curvature < 1e-4:
            continue

        corner_cap = math.sqrt(max_lat_accel / curvature)
        speed_caps[idx] = max(TRACK_LINE_MIN_SPEED_KPH / 3.6, min(speed_caps[idx], corner_cap))

    for idx in range(n):
        neighborhood: List[float] = []
        for step in range(-3, 4):
            sample_idx = idx + step
            if closed:
                sample_idx %= n
            elif sample_idx < 0 or sample_idx >= n:
                continue
            neighborhood.append(speed_caps[sample_idx])
        if neighborhood:
            speed_caps[idx] = min(neighborhood)

    segment_lengths: List[float] = []
    for idx in range(n):
        if idx + 1 < n:
            next_idx = idx + 1
        elif closed:
            next_idx = 0
        else:
            next_idx = idx
        segment_lengths.append(float(np.linalg.norm(points[next_idx][:2] - points[idx][:2])))

    speeds = speed_caps[:]
    for _ in range(3):
        for idx in range(1, n):
            ds = max(segment_lengths[idx - 1], 1e-3)
            accel_cap = math.sqrt(max(speeds[idx - 1] * speeds[idx - 1] + 2.0 * TRACK_LINE_ACCEL_MPS2 * ds, 0.0))
            speeds[idx] = min(speeds[idx], accel_cap)
        for idx in range(n - 2, -1, -1):
            ds = max(segment_lengths[idx], 1e-3)
            brake_cap = math.sqrt(max(speeds[idx + 1] * speeds[idx + 1] + 2.0 * TRACK_LINE_BRAKE_MPS2 * ds, 0.0))
            speeds[idx] = min(speeds[idx], brake_cap)
        if closed and n > 2:
            wrap_ds = max(segment_lengths[-1], 1e-3)
            wrap_cap = math.sqrt(max(speeds[-1] * speeds[-1] + 2.0 * TRACK_LINE_ACCEL_MPS2 * wrap_ds, 0.0))
            speeds[0] = min(speeds[0], wrap_cap)
            wrap_cap = math.sqrt(max(speeds[0] * speeds[0] + 2.0 * TRACK_LINE_BRAKE_MPS2 * wrap_ds, 0.0))
            speeds[-1] = min(speeds[-1], wrap_cap)

    min_speed_mps = TRACK_LINE_MIN_SPEED_KPH / 3.6
    return [max(min_speed_mps, min(speed, max_speed_mps)) for speed in speeds]


def _build_ai_line(points: List[np.ndarray], target_speed_kph: float, aggression: float, closed: bool) -> List[Dict[str, object]]:
    dense_points = _densify_track_points(points, TRACK_LINE_SPACING_M, closed)
    speeds = _track_line_speed_profile(dense_points, target_speed_kph, aggression, closed)
    line: List[Dict[str, object]] = []
    for point, speed in zip(dense_points, speeds):
        line.append(
            {
                "pos": (float(point[0]), float(point[1]), float(point[2])),
                "speed": float(speed),
            }
        )
    if closed and len(line) >= 3:
        for idx in range(3):
            line.append({"pos": line[idx]["pos"], "speed": line[idx]["speed"]})
    return line


def _load_track_mission_preset(
    beamng_home: str,
    map_name: str,
    target_speed_kph: float,
    aggression: float,
) -> Optional[AITrackPreset]:
    rel_path = TRACK_MISSION_PRESETS.get(map_name)
    if rel_path is None:
        return None

    mission_path = os.path.join(beamng_home, rel_path)
    if not os.path.isfile(mission_path):
        return None

    with open(mission_path, "r", encoding="utf-8") as fh:
        mission = json.load(fh)

    nodes = {
        int(node["oldId"]): np.asarray(node["pos"], dtype=np.float64)
        for node in mission.get("pathnodes") or []
        if "oldId" in node and "pos" in node
    }
    if len(nodes) < 3:
        return None

    next_map = {
        int(segment["from"]): int(segment["to"])
        for segment in mission.get("segments") or []
        if segment.get("mode") == "waypoint" and "from" in segment and "to" in segment
    }
    start_node = int(mission.get("startNode") or 0)
    if start_node not in nodes:
        start_node = next(iter(nodes.keys()))

    ordered_points: List[np.ndarray] = []
    visited: set[int] = set()
    current = start_node
    while current in nodes and current not in visited:
        ordered_points.append(nodes[current].copy())
        visited.add(current)
        current = next_map.get(current, -1)
        if current == start_node:
            break

    closed = bool(((mission.get("classification") or {}).get("closed")) or current == start_node)
    if len(ordered_points) < 3:
        return None

    start_positions = mission.get("startPositions") or []
    default_start_id = int(mission.get("defaultStartPosition") or 0)
    selected_start = None
    for entry in start_positions:
        if int(entry.get("oldId", -1)) == default_start_id:
            selected_start = entry
            break
    if selected_start is None and start_positions:
        selected_start = start_positions[0]

    spawn_pos = None
    spawn_quat = None
    if selected_start is not None:
        spawn_pos = tuple(float(value) for value in selected_start.get("pos", ordered_points[0]))
        spawn_quat = tuple(float(value) for value in selected_start.get("rot", (0.0, 0.0, 0.0, 1.0)))

    route_points = _densify_track_points(ordered_points, TRACK_LINE_SPACING_M, closed)
    if closed and spawn_pos is not None and spawn_quat is not None:
        route_points = _rotate_looped_route_to_spawn(route_points, spawn_pos, spawn_quat)
    route_plan = RoutePlan(road_id=-float(start_node), points=route_points, looped=closed)
    line = _build_ai_line(route_points, target_speed_kph, aggression, closed)

    return AITrackPreset(
        controller="line",
        name=os.path.basename(os.path.dirname(mission_path)),
        route_plan=route_plan,
        line=line,
        spawn_pos=spawn_pos,
        spawn_quat=spawn_quat,
    )


def _build_ai_track_preset(
    beamng_home: str,
    map_name: str,
    route_plan: Optional[RoutePlan],
    target_speed_kph: float,
    aggression: float,
    controller: str,
) -> Optional[AITrackPreset]:
    if controller == "span":
        return None

    if controller in ("auto", "line"):
        mission_preset = _load_track_mission_preset(beamng_home, map_name, target_speed_kph, aggression)
        if mission_preset is not None:
            return mission_preset
        if route_plan is not None and route_plan.looped:
            return AITrackPreset(
                controller="line",
                name=f"{map_name}_road_loop",
                route_plan=route_plan,
                line=_build_ai_line(route_plan.points, target_speed_kph, aggression, True),
            )
        if controller == "line":
            return None

    if controller == "waypoints":
        waypoints = TRACK_WAYPOINT_PRESETS.get(map_name)
        if waypoints:
            spawn_pos = None
            spawn_quat = None
            if map_name in TRACK_WAYPOINT_SPAWN_PRESETS:
                spawn_pos, spawn_quat = TRACK_WAYPOINT_SPAWN_PRESETS[map_name]
            return AITrackPreset(
                controller="waypoints",
                name=f"{map_name}_waypoints",
                route_plan=route_plan,
                waypoints=list(waypoints),
                spawn_pos=spawn_pos,
                spawn_quat=spawn_quat,
            )

    return None


def _activate_ai_driver(vehicle: object, args: argparse.Namespace, preset: Optional[AITrackPreset]) -> str:
    aggression = float(np.clip(args.ai_aggression, 0.3, 1.0))
    try:
        vehicle.ai.set_aggression(aggression)
    except Exception:
        pass

    if preset is not None:
        if preset.controller == "waypoints" and preset.waypoints:
            laps = args.target_laps if args.target_laps is not None else TRACK_AI_LONG_LAPS
            vehicle.ai.drive_using_waypoints(
                preset.waypoints,
                no_of_laps=laps,
                route_speed=args.speed / 3.6,
                route_speed_mode=args.ai_speed_mode,
                drive_in_lane=False,
                aggression=aggression,
                avoid_cars=True,
            )
            return preset.controller
        if preset.controller == "line" and preset.line:
            vehicle.ai.set_line(preset.line)
            return preset.controller

    vehicle.ai.set_mode(args.ai_mode)
    if args.ai_mode == "traffic":
        vehicle.ai.drive_in_lane(True)
    vehicle.ai.set_speed(args.speed / 3.6, mode=args.ai_speed_mode)
    return "span"


def _route_preview_profile(route: RoutePlan, start_idx: int, max_distance: float) -> Tuple[List[float], List[float]]:
    distances = [0.0]
    headings: List[float] = []
    total = 0.0
    idx = start_idx
    visited = 0
    n = len(route.points)
    while total < max_distance and visited < n:
        next_idx = _wrapped_index(n, idx + 1) if route.looped else min(idx + 1, n - 1)
        if next_idx == idx:
            break
        seg = route.points[next_idx][:2] - route.points[idx][:2]
        seg_len = float(np.linalg.norm(seg))
        idx = next_idx
        visited += 1
        if seg_len < 1e-6:
            continue
        headings.append(math.atan2(float(seg[1]), float(seg[0])))
        total += seg_len
        distances.append(total)
        if not route.looped and idx >= n - 1:
            break
    return distances, headings


def _route_preview_curvature(distances: List[float], headings: List[float]) -> Tuple[float, float]:
    if len(headings) < 2 or len(distances) != len(headings) + 1:
        return 0.0, 0.0

    best_curvature = 0.0
    max_turn = 0.0
    for start in range(len(headings) - 1):
        window_turn = 0.0
        for end in range(start + 1, len(headings)):
            window_turn += abs(_wrap_angle(headings[end] - headings[end - 1]))
            window_dist = distances[end + 1] - distances[start]
            if window_dist < ROUTE_CURVATURE_MIN_WINDOW_M:
                continue
            best_curvature = max(best_curvature, window_turn / max(window_dist, 1e-3))
            if window_dist >= ROUTE_CURVATURE_MAX_WINDOW_M:
                break
        max_turn = max(max_turn, window_turn)

    if best_curvature == 0.0 and distances[-1] > 1e-3:
        fallback_turn = 0.0
        for idx in range(1, len(headings)):
            fallback_turn += abs(_wrap_angle(headings[idx] - headings[idx - 1]))
        best_curvature = fallback_turn / max(distances[-1], 1e-3)
        max_turn = max(max_turn, fallback_turn)

    return best_curvature, max_turn


def _route_control(route: RoutePlan, pos: np.ndarray, direction: np.ndarray, speed_kph: float, speed_limit_kph: float) -> RouteControl:
    n = len(route.points)
    if n < 4:
        return RouteControl(speed_target_kph=min(speed_limit_kph, ROUTE_MIN_SPEED_KPH))

    pos_xy = np.asarray(pos[:2], dtype=np.float64)
    fwd = _normalize_xy(direction[:2])
    left = np.array([-fwd[1], fwd[0]], dtype=np.float64)

    search_indices: List[int] = []
    if route.looped:
        for step in range(ROUTE_SEARCH_WINDOW):
            search_indices.append(_wrapped_index(n, route.index + step))
    else:
        hi = min(n, route.index + ROUTE_SEARCH_WINDOW)
        search_indices = list(range(route.index, hi))
        if not search_indices:
            search_indices = [min(route.index, n - 1)]

    best_idx = route.index
    best_score = float("inf")
    for idx in search_indices:
        delta = route.points[idx][:2] - pos_xy
        d = float(np.linalg.norm(delta))
        along = float(np.dot(delta, fwd))
        penalty = 0.0 if along >= -2.0 else abs(along) * 4.0
        score = d + penalty
        if score < best_score:
            best_score = score
            best_idx = idx
    route.index = best_idx

    lookahead = ROUTE_LOOKAHEAD_BASE_M + ROUTE_LOOKAHEAD_SPEED_GAIN * (speed_kph / 3.6)
    target_idx = best_idx
    distance_ahead = 0.0
    while distance_ahead < lookahead:
        next_idx = _wrapped_index(n, target_idx + 1) if route.looped else min(target_idx + 1, n - 1)
        if next_idx == target_idx:
            break
        distance_ahead += float(np.linalg.norm(route.points[next_idx][:2] - route.points[target_idx][:2]))
        target_idx = next_idx
        if not route.looped and target_idx >= n - 1:
            break

    prev_idx = _wrapped_index(n, max(target_idx - 1, 0)) if route.looped else max(target_idx - 1, 0)
    next_idx = _wrapped_index(n, target_idx + 1) if route.looped else min(target_idx + 1, n - 1)
    tangent = _normalize_xy(route.points[next_idx][:2] - route.points[prev_idx][:2])

    target_delta = route.points[target_idx][:2] - pos_xy
    lateral_error = float(np.dot(target_delta, left))
    tangent_cross = float(fwd[0] * tangent[1] - fwd[1] * tangent[0])
    tangent_dot = float(np.clip(np.dot(fwd, tangent), -1.0, 1.0))
    heading_error = math.atan2(tangent_cross, tangent_dot)

    steer = ROUTE_HEADING_GAIN * heading_error + ROUTE_LATERAL_GAIN * (lateral_error / max(lookahead, 1.0))
    steer = float(np.clip(steer, -1.0, 1.0))

    preview_distance = min(
        ROUTE_SPEED_PREVIEW_MAX_M,
        max(
            ROUTE_SPEED_PREVIEW_MIN_M,
            lookahead + ROUTE_SPEED_PREVIEW_BASE_M + (speed_kph / 3.6) * ROUTE_SPEED_PREVIEW_TIME_S,
        ),
    )
    preview_distances, preview_headings = _route_preview_profile(route, best_idx, preview_distance)
    preview_curvature, preview_turn = _route_preview_curvature(preview_distances, preview_headings)

    curve_speed_cap = ROUTE_MAX_SPEED_KPH
    if preview_curvature > 1e-4:
        curve_speed_cap = math.sqrt(ROUTE_MAX_LATERAL_ACCEL_MPS2 / preview_curvature) * 3.6
        curve_speed_cap *= ROUTE_CURVE_SPEED_SAFETY
    if preview_turn > 1e-3 and preview_distances:
        avg_curvature = preview_turn / max(preview_distances[-1], 1e-3)
        avg_speed_cap = math.sqrt((ROUTE_MAX_LATERAL_ACCEL_MPS2 * 0.85) / max(avg_curvature, 1e-4)) * 3.6
        curve_speed_cap = min(curve_speed_cap, avg_speed_cap)
    curve_speed_cap = max(ROUTE_CURVE_MIN_SPEED_KPH, min(curve_speed_cap, ROUTE_MAX_SPEED_KPH))

    heading_error_deg = abs(math.degrees(heading_error))
    error_speed_cap = ROUTE_MAX_SPEED_KPH
    error_ratio = max(
        abs(lateral_error) / max(ROUTE_RECOVERY_LATERAL_M, 1e-3),
        heading_error_deg / max(ROUTE_RECOVERY_HEADING_DEG, 1e-3),
    )
    if error_ratio > 1.0:
        error_speed_cap = max(ROUTE_MIN_SPEED_KPH, speed_limit_kph / (1.0 + 0.9 * error_ratio * error_ratio))
    if abs(lateral_error) >= ROUTE_SEVERE_LATERAL_M or heading_error_deg >= ROUTE_SEVERE_HEADING_DEG:
        error_speed_cap = min(error_speed_cap, max(ROUTE_MIN_SPEED_KPH, speed_limit_kph * 0.35))

    steer_speed_cap = ROUTE_MAX_SPEED_KPH
    if abs(steer) > 0.25:
        steer_speed_cap = max(ROUTE_MIN_SPEED_KPH, speed_limit_kph * (1.0 - 0.9 * abs(steer)))

    speed_target = min(speed_limit_kph, ROUTE_MAX_SPEED_KPH, curve_speed_cap, error_speed_cap, steer_speed_cap)
    speed_target = max(ROUTE_MIN_SPEED_KPH, speed_target)

    return RouteControl(
        steering_target=steer,
        speed_target_kph=float(speed_target),
        lateral_error_m=lateral_error,
        heading_error_deg=math.degrees(heading_error),
        progress_index=best_idx,
        lookahead_m=lookahead,
        curve_speed_cap_kph=float(curve_speed_cap),
        preview_curvature=float(preview_curvature),
        preview_distance_m=float(preview_distance),
    )


def detect_lanes(bgr: np.ndarray) -> LaneResult:
    """Classical OpenCV lane/road-centre detection. Returns a LaneResult."""
    h, w = bgr.shape[:2]
    roi_top = int(h * ROI_TOP_FRAC)
    roi_bottom = int(h * ROI_BOTTOM_FRAC)
    roi = bgr[roi_top:roi_bottom, :]

    # Road mask (grey asphalt)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower = np.array(ROAD_HSV_LOWER, dtype=np.uint8)
    upper = np.array(ROAD_HSV_UPPER, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Canny edges masked to road
    grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(grey, (BLUR_KERNEL, BLUR_KERNEL), 0)
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
    edges = cv2.bitwise_and(edges, mask)

    # Hough lines
    raw_lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=HOUGH_MIN_LINE,
        maxLineGap=HOUGH_MAX_GAP,
    )

    left_lines: List[np.ndarray] = []
    right_lines: List[np.ndarray] = []
    mid_x = roi.shape[1] // 2

    if raw_lines is not None:
        for line in raw_lines:
            x1, y1, x2, y2 = line[0]
            if x2 == x1:
                continue
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) < 0.3:
                continue
            if slope < 0 and x1 < mid_x and x2 < mid_x:
                left_lines.append(line[0])
            elif slope > 0 and x1 > mid_x and x2 > mid_x:
                right_lines.append(line[0])

    def avg_line(group: List[np.ndarray]) -> Optional[np.ndarray]:
        if not group:
            return None
        xs, ys = [], []
        for x1, y1, x2, y2 in group:
            xs += [x1, x2]
            ys += [y1, y2]
        if len(xs) < 2:
            return None
        poly = np.polyfit(ys, xs, 1)
        rh = roi.shape[0]
        y_bot, y_top = rh, int(rh * 0.4)
        return np.array([int(np.polyval(poly, y_top)), y_top,
                         int(np.polyval(poly, y_bot)), y_bot])

    left_avg = avg_line(left_lines)
    right_avg = avg_line(right_lines)

    centre_x = w / 2.0
    half = w / 2.0

    if left_avg is not None and right_avg is not None:
        lane_mid = (left_avg[2] + right_avg[2]) / 2.0
        offset = float(np.clip((lane_mid - centre_x) / half, -1.0, 1.0))
        confidence = 1.0
    elif left_avg is not None:
        lane_mid = left_avg[2] + w * 0.35
        offset = float(np.clip((lane_mid - centre_x) / half, -SINGLE_LANE_OFFSET_LIMIT, SINGLE_LANE_OFFSET_LIMIT))
        confidence = 0.5
    elif right_avg is not None:
        lane_mid = right_avg[2] - w * 0.35
        offset = float(np.clip((lane_mid - centre_x) / half, -SINGLE_LANE_OFFSET_LIMIT, SINGLE_LANE_OFFSET_LIMIT))
        confidence = 0.5
    else:
        offset, confidence = 0.0, 0.0

    # Debug overlay
    overlay = bgr.copy()

    def draw_lane(line: np.ndarray, colour: Tuple[int, int, int]) -> None:
        pt1 = (int(line[0]), int(line[1]) + roi_top)
        pt2 = (int(line[2]), int(line[3]) + roi_top)
        cv2.line(overlay, pt1, pt2, colour, 3)

    if left_avg is not None:
        draw_lane(left_avg, (255, 0, 0))
    if right_avg is not None:
        draw_lane(right_avg, (0, 0, 255))

    target_x = int(w / 2 + offset * w / 2)
    cv2.circle(overlay, (target_x, h - 30), 10, (0, 255, 0), -1)
    cv2.line(overlay, (w // 2, h - 40), (w // 2, h - 20), (255, 255, 255), 2)
    colour = (0, 255, 0) if confidence > 0.5 else (0, 165, 255) if confidence > 0 else (0, 0, 255)
    cv2.putText(overlay, f"off={offset:+.2f} conf={confidence:.2f}",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)

    return LaneResult(offset=offset, confidence=confidence, overlay=overlay)


def obstacle_ahead(depth_image: Optional[np.ndarray]) -> bool:
    """True if a large portion of the forward depth strip is very close."""
    if depth_image is None or depth_image.ndim != 2 or depth_image.size == 0:
        return False
    h, w = depth_image.shape[:2]
    roi = depth_image[int(h * 0.25): int(h * 0.55), int(w * 0.35): int(w * 0.65)]
    valid = roi[np.isfinite(roi) & (roi > 0)]
    if valid.size == 0:
        return False
    close_frac = float(np.sum(valid < OBSTACLE_CLOSE_M)) / valid.size
    return close_frac > OBSTACLE_FRAC


# ── Driving mode ─────────────────────────────────────────────────────────────

class Mode(Enum):
    DRIVE = auto()
    EMERGENCY = auto()
    STOPPED = auto()


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BeamNG.tech autonomous driver — single script")
    p.add_argument("--beamng-home", default=BEAMNG_HOME,
                   help=f"Path to BeamNG.tech install (default: {BEAMNG_HOME})")
    p.add_argument("--host", default=BEAMNG_HOST)
    p.add_argument("--port", type=int, default=BEAMNG_PORT)
    p.add_argument("--speed", type=float, default=TARGET_SPEED_KPH,
                   help="Target cruise speed in kph")
    p.add_argument("--no-overlay", action="store_true",
                   help="Disable the live debug window")
    p.add_argument("--map", default=MAP_NAME, help="BeamNG map name")
    p.add_argument("--vehicle", default=VEHICLE_MODEL, help="Vehicle model name")
    p.add_argument("--stage", choices=["idle", "cruise", "ai", "lane", "custom"], default="ai",
                   help="Incremental bring-up stage: idle, cruise, built-in AI, camera-lane, or road-route custom driving")
    p.add_argument("--ai-mode", choices=["traffic", "span"], default="span",
                   help="Built-in AI mode for --stage ai")
    p.add_argument("--ai-controller", choices=["auto", "span", "waypoints", "line"], default="line",
                   help="AI track controller for --stage ai")
    p.add_argument("--ai-speed-mode", choices=["limit", "set"], default="limit",
                   help="Built-in AI speed behavior for --stage ai")
    p.add_argument("--ai-aggression", type=float, default=0.85,
                   help="Aggression for built-in AI when supported")
    p.add_argument("--road-id", type=float, default=None,
                   help="Optional road id for custom route following; defaults to the map preset or longest road")
    p.add_argument("--steering-log", default=DEFAULT_STEERING_LOG_CSV,
                   help=f"CSV path for steering-angle output (default: {DEFAULT_STEERING_LOG_CSV})")
    p.add_argument("--max-runtime-seconds", type=float, default=None,
                   help="Optional maximum control-loop runtime before exiting cleanly")
    p.add_argument("--target-laps", type=int, default=None,
                   help="Optional number of completed laps before exiting cleanly on looped roads")
    p.add_argument("--summary-json", default=None,
                   help="Optional path to write a JSON run summary")
    return p.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    target_speed = args.speed
    show_overlay = not args.no_overlay
    route_stage = args.stage == "custom"
    camera_stage = args.stage == "lane"
    route_spawn_stage = args.stage in ("custom", "ai")
    speed_ceiling_kph = max(MAX_SPEED_KPH, target_speed + 5.0)

    print("=" * 60)
    print("  BeamNG.tech Autonomous Driver")
    print(f"  Map: {args.map}   Vehicle: {args.vehicle}")
    print(f"  Target speed: {target_speed} kph")
    print(f"  Stage: {args.stage}")
    print("=" * 60)

    # Late import so the script can be imported without beamngpy installed
    try:
        from beamngpy import BeamNGpy, Scenario, Vehicle
        from beamngpy.sensors import Camera, Electrics, Damage
    except ImportError:
        print("\n[error] beamngpy is not installed.")
        print("        Run:  pip install beamngpy")
        sys.exit(1)

    steer_pid = SteeringPID()
    speed_pid = SpeedPID()
    route_steer_filter = RouteSteeringFilter()
    mode = Mode.DRIVE
    no_road_frames = 0
    manual_estop = False
    steering_log_file = None
    steering_log = None
    route_plan: Optional[RoutePlan] = None
    run_started_t: Optional[float] = None
    max_speed_seen = 0.0
    max_damage_seen = 0.0
    damage_failure = False
    route_failure = False
    route_lost_frames = 0
    summary: Dict[str, Any] = {}
    lap_tracker = LapTrackerState()
    ai_preset: Optional[AITrackPreset] = None
    ai_controller_name: str = "none"
    last_ai_line_refresh_lap = 0

    bng = None
    try:
        # ── Connect ────────────────────────────────────────────────────────
        print(f"\n[main] Connecting to BeamNG @ {args.host}:{args.port} …")
        bng = BeamNGpy(args.host, args.port, home=args.beamng_home or None)
        bng.open()
        print("[main] Connected.")

        # ── Scenario + vehicle ────────────────────────────────────────────
        vehicle = Vehicle("ego", model=args.vehicle)
        scenario = Scenario(args.map, "selfdrivetech")
        scenario.add_vehicle(vehicle, pos=SPAWN_POS, rot_quat=SPAWN_ROT)
        scenario.make(bng)

        print("[main] Loading scenario …")
        bng.scenario.load(scenario)
        bng.scenario.start()
        bng.control.pause()
        print("[main] Scenario running (paused for stepping).")

        # ── Sensors ───────────────────────────────────────────────────────
        cam_kwargs = dict(
            requested_update_time=CAM_UPDATE_TIME_S,
            pos=CAM_POS,
            dir=CAM_DIR,
            field_of_view_y=CAM_FOV,
            resolution=CAM_RESOLUTION,
            near_far_planes=CAM_NEAR_FAR,
            is_render_colours=True,
            is_render_depth=True,
            is_render_annotations=False,
        )
        try:
            cam = Camera("front_cam", bng, vehicle=vehicle, **cam_kwargs)
        except TypeError:
            cam = Camera("front_cam", vehicle.vid, **cam_kwargs)

        if hasattr(cam, "attach"):
            _attach_vehicle_sensor(vehicle, "front_cam", cam)

        electrics = Electrics()
        _attach_vehicle_sensor(vehicle, "electrics", electrics)

        damage = Damage()
        _attach_vehicle_sensor(vehicle, "damage", damage)

        if route_spawn_stage:
            roads = bng.scenario.get_road_network(include_edges=True, drivable_only=True)
            route_plan = _get_route_plan(roads, args.map, args.road_id)
            if args.stage == "ai":
                ai_preset = _build_ai_track_preset(
                    args.beamng_home or BEAMNG_HOME,
                    args.map,
                    route_plan,
                    target_speed,
                    args.ai_aggression,
                    args.ai_controller,
                )
                if ai_preset is not None and ai_preset.route_plan is not None:
                    route_plan = ai_preset.route_plan

            if ai_preset is not None and ai_preset.spawn_pos is not None and ai_preset.spawn_quat is not None:
                spawn_pos, spawn_quat = ai_preset.spawn_pos, ai_preset.spawn_quat
            else:
                spawn_pos, spawn_quat = _route_spawn_pose(route_plan)
            lap_tracker.start_pos = np.asarray(spawn_pos, dtype=np.float64)
            lap_tracker.last_pos = lap_tracker.start_pos.copy()
            lap_tracker.route_length_hint_m = _road_length(route_plan.points)
            vehicle.teleport(spawn_pos, rot_quat=spawn_quat, reset=True)
            bng.control.step(BEAMNG_STEPS * 3)
            if route_stage:
                print(
                    f"[main] Custom route road={route_plan.road_id:.0f} "
                    f"points={len(route_plan.points)} looped={route_plan.looped}"
                )
            else:
                if ai_preset is not None:
                    print(
                        f"[main] AI track preset={ai_preset.name} controller={ai_preset.controller} "
                        f"points={len(route_plan.points)} looped={route_plan.looped}"
                    )
                else:
                    print(
                        f"[main] AI spawn road={route_plan.road_id:.0f} "
                        f"points={len(route_plan.points)} looped={route_plan.looped}"
                    )

        ai_active = False
        if args.stage == "ai":
            ai_controller_name = _activate_ai_driver(vehicle, args, ai_preset)
            ai_active = True
            if ai_preset is not None:
                print(
                    "[main] AI track driver enabled "
                    f"(controller={ai_controller_name}, preset={ai_preset.name})."
                )
            else:
                print(
                    "[main] Built-in BeamNG AI enabled "
                    f"(mode={args.ai_mode}, speed_mode={args.ai_speed_mode})."
                )

        log_dir = os.path.dirname(args.steering_log)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        steering_log_file = open(args.steering_log, "w", newline="", encoding="utf-8")
        steering_log = csv.writer(steering_log_file)
        steering_log.writerow([
            "tick",
            "stage",
            "speed_kph",
            "steering_cmd_norm",
            "steering_wheel_deg",
            "steering_input",
            "throttle_cmd",
            "brake_cmd",
            "lane_offset",
            "lane_confidence",
            "route_heading_error_deg",
            "route_lookahead_m",
            "route_speed_target_kph",
            "route_curve_speed_cap_kph",
            "route_preview_curvature",
            "route_preview_distance_m",
            "route_progress_index",
            "damage",
        ])

        print("[main] Sensors attached. Starting loop (press 'q' to quit, 'e' = e-stop).\n")

        dt_target = 1.0 / LOOP_HZ
        tick = 0

        while True:
            t0 = time.perf_counter()
            tick += 1

            # ── Step simulation ────────────────────────────────────────
            bng.control.step(BEAMNG_STEPS)

            # ── Read sensors ───────────────────────────────────────────
            if hasattr(vehicle, "poll_sensors"):
                vehicle.poll_sensors()
            else:
                vehicle.sensors.poll()

            colour_img: Optional[np.ndarray] = None
            depth_img: Optional[np.ndarray] = None
            speed_kph = 0.0
            dmg_total = 0.0
            steering_wheel_deg = 0.0
            steering_input = 0.0
            route_ctl = RouteControl()
            vehicle_state = getattr(vehicle, "state", {}) or {}
            pos = np.asarray(vehicle_state.get("pos") or (0.0, 0.0, 0.0), dtype=np.float64)
            direction = np.asarray(vehicle_state.get("dir") or (1.0, 0.0, 0.0), dtype=np.float64)

            try:
                cam_data = cam.poll()
                if "colour" in cam_data:
                    colour_img = _to_colour_image(cam_data["colour"])
                if "depth" in cam_data:
                    depth_img = _to_depth_image(cam_data["depth"])
            except Exception as e:
                print(f"[cam] poll error: {e}")

            try:
                elec = dict(electrics)
                speed_kph = float((elec or {}).get("wheelspeed", 0.0) or 0.0) * 3.6
                steering_wheel_deg = float((elec or {}).get("steering", 0.0) or 0.0)
                steering_input = float((elec or {}).get("steering_input", 0.0) or 0.0)
            except Exception as e:
                print(f"[elec] poll error: {e}")

            try:
                dmg = dict(damage)
                dmg_total = float((dmg or {}).get("damage", 0.0) or 0.0)
                max_damage_seen = max(max_damage_seen, dmg_total)
            except Exception as e:
                print(f"[dmg] poll error: {e}")
            max_speed_seen = max(max_speed_seen, speed_kph)

            lap_progress_index = 0

            # ── Perception ─────────────────────────────────────────────
            if camera_stage and colour_img is not None:
                lane = detect_lanes(colour_img)
            else:
                lane = LaneResult()
                if route_stage and route_plan is not None:
                    route_ctl = _route_control(route_plan, pos, direction, speed_kph, target_speed)
                    lap_progress_index = route_ctl.progress_index
                    lane.offset = float(np.clip(route_ctl.lateral_error_m / 8.0, -1.0, 1.0))
                    lane.confidence = 1.0
                elif not camera_stage:
                    lane.confidence = 1.0
                    if route_plan is not None:
                        lap_progress_index = _nearest_route_index(route_plan, pos)

            if route_plan is not None:
                previous_laps = lap_tracker.laps_completed
                _update_lap_tracker(lap_tracker, route_plan, lap_progress_index, pos)
                if (
                    args.stage == "ai"
                    and ai_active
                    and ai_controller_name == "line"
                    and ai_preset is not None
                    and ai_preset.line
                    and lap_tracker.laps_completed > previous_laps
                    and lap_tracker.laps_completed > last_ai_line_refresh_lap
                ):
                    vehicle.ai.set_line(ai_preset.line)
                    last_ai_line_refresh_lap = lap_tracker.laps_completed

            obs = obstacle_ahead(depth_img) if camera_stage else False

            # ── Behavior ───────────────────────────────────────────────
            if camera_stage and lane.confidence == 0.0:
                no_road_frames += 1
            else:
                no_road_frames = 0

            if route_stage and abs(lane.offset) >= CUSTOM_ROUTE_LOST_OFFSET and abs(route_ctl.heading_error_deg) >= CUSTOM_ROUTE_LOST_HEADING_DEG:
                route_lost_frames += 1
            else:
                route_lost_frames = 0

            # Determine emergency stop trigger (log the reason once per transition)
            estop_reason: Optional[str] = None
            if manual_estop:
                estop_reason = "manual e-stop"
            elif dmg_total >= CUSTOM_DAMAGE_STOP:
                estop_reason = f"damage threshold exceeded ({dmg_total:.1f})"
                damage_failure = True
            elif route_stage and route_lost_frames >= CUSTOM_ROUTE_LOST_FRAMES:
                estop_reason = (
                    f"route lost (off={lane.offset:+.2f}, "
                    f"hdg={route_ctl.heading_error_deg:+.1f})"
                )
                route_failure = True
            elif obs:
                estop_reason = "obstacle detected"
            elif camera_stage and no_road_frames >= NO_ROAD_LIMIT:
                estop_reason = f"road lost for {no_road_frames} frames"
            elif speed_kph > speed_ceiling_kph:
                estop_reason = f"over speed limit ({speed_kph:.1f} kph)"

            if estop_reason:
                if mode != Mode.EMERGENCY:
                    print(f"\n[behavior] EMERGENCY — {estop_reason}")
                mode = Mode.EMERGENCY
            elif mode == Mode.EMERGENCY and speed_kph < 0.5:
                mode = Mode.STOPPED
            elif mode in (Mode.STOPPED, Mode.EMERGENCY) and lane.confidence > 0.0 and not obs and speed_kph <= speed_ceiling_kph and dmg_total < CUSTOM_DAMAGE_STOP and not route_failure:
                # Conditions have cleared — resume normal driving
                print("\n[behavior] Resuming DRIVE mode.")
                steer_pid.reset()
                speed_pid.reset()
                route_steer_filter.reset()
                mode = Mode.DRIVE
            else:
                mode = Mode.DRIVE

            # ── Control ────────────────────────────────────────────────
            if mode == Mode.EMERGENCY:
                steer_pid.reset()
                speed_pid.reset()
                route_steer_filter.reset()
                steering, throttle, brake = 0.0, 0.0, 1.0
            elif mode == Mode.STOPPED:
                steering, throttle, brake = 0.0, 0.0, 0.3
            elif args.stage == "ai":
                if manual_estop:
                    steering, throttle, brake = 0.0, 0.0, 1.0
                else:
                    if not ai_active:
                        ai_controller_name = _activate_ai_driver(vehicle, args, ai_preset)
                        ai_active = True
                    steering, throttle, brake = 0.0, 0.0, 0.0
            elif args.stage == "idle":
                steering, throttle, brake = 0.0, 0.0, 0.0
            elif args.stage == "cruise":
                steering = 0.0
                throttle, brake = speed_pid.compute(target_speed, speed_kph)
            elif route_stage:
                steering = route_steer_filter.compute(route_ctl.steering_target)
                throttle, brake = speed_pid.compute(route_ctl.speed_target_kph, speed_kph)
            else:
                steering = steer_pid.compute(lane.offset)
                throttle, brake = speed_pid.compute(target_speed, speed_kph)

            # Clamp
            steering = max(-1.0, min(1.0, steering))
            throttle = max(0.0, min(1.0, throttle))
            brake = max(0.0, min(1.0, brake))

            ai_needs_manual_override = args.stage == "ai" and (manual_estop or mode != Mode.DRIVE)
            if ai_needs_manual_override:
                if ai_active:
                    vehicle.ai.set_mode("disabled")
                    ai_active = False
                vehicle.control(steering=steering, throttle=throttle, brake=brake)
            elif args.stage != "ai":
                vehicle.control(steering=steering, throttle=throttle, brake=brake)

            if steering_log is not None:
                steering_log.writerow([
                    tick,
                    args.stage,
                    f"{speed_kph:.3f}",
                    f"{steering:.6f}",
                    f"{steering_wheel_deg:.3f}",
                    f"{steering_input:.6f}",
                    f"{throttle:.6f}",
                    f"{brake:.6f}",
                    f"{lane.offset:.6f}",
                    f"{lane.confidence:.3f}",
                    f"{route_ctl.heading_error_deg:.3f}",
                    f"{route_ctl.lookahead_m:.3f}",
                    f"{route_ctl.speed_target_kph:.3f}",
                    f"{route_ctl.curve_speed_cap_kph:.3f}",
                    f"{route_ctl.preview_curvature:.6f}",
                    f"{route_ctl.preview_distance_m:.3f}",
                    route_ctl.progress_index,
                    f"{dmg_total:.3f}",
                ])
                if tick % 10 == 0:
                    steering_log_file.flush()

            # ── Console telemetry ──────────────────────────────────────
            if tick % 10 == 0:
                print(
                    f"\r[t={tick:5d}] {speed_kph:5.1f}kph  "
                    f"str={steering:+.3f}  stw={steering_wheel_deg:+6.2f}deg  "
                    f"thr={throttle:.2f}  brk={brake:.2f}  "
                    f"off={lane.offset:+.3f}  conf={lane.confidence:.2f}  "
                    f"mode={mode.name}  stage={args.stage}  "
                    f"lap={lap_tracker.laps_completed}  "
                    f"hdg={route_ctl.heading_error_deg:+5.1f}  "
                    f"vref={route_ctl.speed_target_kph:4.1f}  dmg={dmg_total:.1f}",
                    end="", flush=True,
                )

            if run_started_t is None:
                run_started_t = time.perf_counter()
            if args.max_runtime_seconds is not None and (time.perf_counter() - run_started_t) >= args.max_runtime_seconds:
                print("\n[main] Max runtime reached.")
                break
            if args.target_laps is not None and lap_tracker.laps_completed >= args.target_laps:
                print("\n[main] Target laps reached.")
                break
            if damage_failure:
                print("\n[main] Damage failure stop reached.")
                break
            if route_failure and speed_kph < 1.0:
                print("\n[main] Route failure stop reached.")
                break

            # ── Debug overlay ──────────────────────────────────────────
            if show_overlay and lane.overlay is not None:
                vis = lane.overlay.copy()
                cv2.putText(vis, f"mode={mode.name}  spd={speed_kph:.1f}kph",
                            (10, vis.shape[0] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                cv2.imshow("BeamNG Self-Drive", vis)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n[main] Quit requested.")
                    break
                if key == ord("e"):
                    manual_estop = not manual_estop
                    print(f"\n[main] Manual e-stop {'ON' if manual_estop else 'OFF'}")
            elif show_overlay:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

            # ── Rate limit ─────────────────────────────────────────────
            elapsed = time.perf_counter() - t0
            sleep_t = dt_target - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

    except KeyboardInterrupt:
        print("\n[main] KeyboardInterrupt — shutting down.")
    except Exception as exc:
        import traceback
        print(f"\n[main] Fatal error: {exc}", file=sys.stderr)
        traceback.print_exc()
    finally:
        target_laps_reached = (
            True
            if 'args' not in locals() or args.target_laps is None
            else lap_tracker.laps_completed >= args.target_laps
        )
        summary = {
            "map": args.map if 'args' in locals() else None,
            "vehicle": args.vehicle if 'args' in locals() else None,
            "stage": args.stage if 'args' in locals() else None,
            "ai_controller": ai_controller_name if 'ai_controller_name' in locals() else None,
            "ai_preset": ai_preset.name if 'ai_preset' in locals() and ai_preset is not None else None,
            "target_speed_kph": target_speed if 'target_speed' in locals() else None,
            "target_laps_requested": args.target_laps if 'args' in locals() else None,
            "target_laps_reached": target_laps_reached,
            "road_id": route_plan.road_id if route_plan is not None else None,
            "route_looped": route_plan.looped if route_plan is not None else False,
            "route_length_m": _road_length(route_plan.points) if route_plan is not None else None,
            "ticks": tick if 'tick' in locals() else 0,
            "max_speed_kph": max_speed_seen,
            "max_damage": max_damage_seen,
            "laps_completed": lap_tracker.laps_completed,
            "last_lap_time_s": lap_tracker.last_lap_time_s if lap_tracker.last_lap_time_s > 0.0 else None,
            "lap_times_s": [round(value, 3) for value in lap_tracker.lap_times_s],
            "damage_failure": damage_failure,
            "route_failure": route_failure,
            "success": not damage_failure and not route_failure and target_laps_reached,
        }
        if 'args' in locals() and args.summary_json:
            summary_dir = os.path.dirname(args.summary_json)
            if summary_dir:
                os.makedirs(summary_dir, exist_ok=True)
            with open(args.summary_json, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2)
        cv2.destroyAllWindows()
        if steering_log_file is not None:
            steering_log_file.close()
        if bng is not None:
            try:
                bng.scenario.stop()
            except Exception:
                pass
            try:
                bng.close()
            except Exception:
                pass
        print("[main] Done.")


if __name__ == "__main__":
    main()
