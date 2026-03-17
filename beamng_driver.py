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
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ── Default configuration (edit here or override with CLI flags) ────────────
BEAMNG_HOME: str = r"C:\BeamNG.tech"   # ← set your BeamNG.tech install path
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

# Perception (HSV road mask + Canny + Hough)
ROAD_HSV_LOWER: Tuple[int, int, int] = (0, 0, 50)
ROAD_HSV_UPPER: Tuple[int, int, int] = (180, 80, 180)
CANNY_LOW: int = 50
CANNY_HIGH: int = 150
ROI_TOP_FRAC: float = 0.50
BLUR_KERNEL: int = 5
HOUGH_THRESHOLD: int = 30
HOUGH_MIN_LINE: int = 40
HOUGH_MAX_GAP: int = 100
NO_ROAD_LIMIT: int = 10          # frames without road before emergency stop
OBSTACLE_CLOSE_M: float = 15.0
OBSTACLE_FRAC: float = 0.05

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
            self._prev_error = error
            return 0.0, 0.0

        self._integral += error * dt
        self._integral = max(-50.0, min(50.0, self._integral))

        derivative = (error - self._prev_error) / dt
        self._prev_error = error

        raw = SPEED_KP * error + SPEED_KI * self._integral + SPEED_KD * derivative
        if raw > 0:
            return min(raw, THROTTLE_MAX), 0.0
        return 0.0, min(abs(raw), BRAKE_MAX)


# ── Lane detection ───────────────────────────────────────────────────────────

@dataclass
class LaneResult:
    offset: float = 0.0       # -1 … +1, positive = road centre is right of image centre
    confidence: float = 0.0   # 0 = no road, 1 = both lanes found
    overlay: Optional[np.ndarray] = None


def detect_lanes(bgr: np.ndarray) -> LaneResult:
    """Classical OpenCV lane/road-centre detection. Returns a LaneResult."""
    h, w = bgr.shape[:2]
    roi_top = int(h * ROI_TOP_FRAC)
    roi = bgr[roi_top:, :]

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
        lane_mid = left_avg[2] + w * 0.25
        offset = float(np.clip((lane_mid - centre_x) / half, -1.0, 1.0))
        confidence = 0.5
    elif right_avg is not None:
        lane_mid = right_avg[2] - w * 0.25
        offset = float(np.clip((lane_mid - centre_x) / half, -1.0, 1.0))
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
    if depth_image is None:
        return False
    h, w = depth_image.shape[:2]
    roi = depth_image[h // 2:, w // 4: 3 * w // 4]
    valid = roi[roi > 0]
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
    return p.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    target_speed = args.speed
    show_overlay = not args.no_overlay

    print("=" * 60)
    print("  BeamNG.tech Autonomous Driver")
    print(f"  Map: {args.map}   Vehicle: {args.vehicle}")
    print(f"  Target speed: {target_speed} kph")
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
    mode = Mode.DRIVE
    no_road_frames = 0
    manual_estop = False

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
        cam = Camera(
            "front_cam",
            vehicle.vid,
            requested_update_time=-1.0,
            pos=CAM_POS,
            dir=CAM_DIR,
            field_of_view_y=CAM_FOV,
            resolution=CAM_RESOLUTION,
            near_far_planes=CAM_NEAR_FAR,
            is_render_colours=True,
            is_render_depth=True,
            is_render_annotations=False,
        )
        cam.attach(vehicle, "front_cam")

        electrics = Electrics()
        electrics.attach(vehicle, "electrics")

        damage = Damage()
        damage.attach(vehicle, "damage")

        print("[main] Sensors attached. Starting loop (press 'q' to quit, 'e' = e-stop).\n")

        dt_target = 1.0 / LOOP_HZ
        tick = 0

        while True:
            t0 = time.perf_counter()
            tick += 1

            # ── Step simulation ────────────────────────────────────────
            bng.control.step(BEAMNG_STEPS)

            # ── Read sensors ───────────────────────────────────────────
            vehicle.sensors.poll()

            colour_img: Optional[np.ndarray] = None
            depth_img: Optional[np.ndarray] = None
            speed_kph = 0.0
            dmg_total = 0.0

            try:
                cam_data = cam.poll()
                if "colour" in cam_data:
                    img = np.array(cam_data["colour"])
                    if img.ndim == 3 and img.shape[2] == 4:
                        colour_img = img[:, :, 2::-1]   # RGBA→BGR (single slice, no copy)
                    elif img.ndim == 3 and img.shape[2] == 3:
                        colour_img = img[:, :, ::-1]    # RGB→BGR
                if "depth" in cam_data:
                    depth_img = np.array(cam_data["depth"], dtype=np.float32)
            except Exception as e:
                print(f"[cam] poll error: {e}")

            try:
                elec = electrics.poll()
                speed_kph = float((elec or {}).get("wheelspeed", 0.0) or 0.0) * 3.6
            except Exception as e:
                print(f"[elec] poll error: {e}")

            try:
                dmg = damage.poll()
                dmg_total = float((dmg or {}).get("damage", 0.0) or 0.0)
            except Exception as e:
                print(f"[dmg] poll error: {e}")

            # ── Perception ─────────────────────────────────────────────
            if colour_img is not None:
                lane = detect_lanes(colour_img)
            else:
                lane = LaneResult()

            obs = obstacle_ahead(depth_img)

            # ── Behavior ───────────────────────────────────────────────
            if lane.confidence == 0.0:
                no_road_frames += 1
            else:
                no_road_frames = 0

            # Determine emergency stop trigger (log the reason once per transition)
            estop_reason: Optional[str] = None
            if manual_estop:
                estop_reason = "manual e-stop"
            elif obs:
                estop_reason = "obstacle detected"
            elif no_road_frames >= NO_ROAD_LIMIT:
                estop_reason = f"road lost for {no_road_frames} frames"
            elif speed_kph > MAX_SPEED_KPH:
                estop_reason = f"over speed limit ({speed_kph:.1f} kph)"

            if estop_reason:
                if mode != Mode.EMERGENCY:
                    print(f"\n[behavior] EMERGENCY — {estop_reason}")
                mode = Mode.EMERGENCY
            elif mode == Mode.EMERGENCY and speed_kph < 0.5:
                mode = Mode.STOPPED
            elif mode in (Mode.STOPPED, Mode.EMERGENCY) and lane.confidence > 0.0 and not obs and speed_kph <= MAX_SPEED_KPH:
                # Conditions have cleared — resume normal driving
                print("\n[behavior] Resuming DRIVE mode.")
                steer_pid.reset()
                speed_pid.reset()
                mode = Mode.DRIVE
            else:
                mode = Mode.DRIVE

            # ── Control ────────────────────────────────────────────────
            if mode == Mode.EMERGENCY:
                steer_pid.reset()
                speed_pid.reset()
                steering, throttle, brake = 0.0, 0.0, 1.0
            elif mode == Mode.STOPPED:
                steering, throttle, brake = 0.0, 0.0, 0.3
            else:
                steering = steer_pid.compute(lane.offset)
                throttle, brake = speed_pid.compute(target_speed, speed_kph)

            # Clamp
            steering = max(-1.0, min(1.0, steering))
            throttle = max(0.0, min(1.0, throttle))
            brake = max(0.0, min(1.0, brake))

            vehicle.control(steering=steering, throttle=throttle, brake=brake)

            # ── Console telemetry ──────────────────────────────────────
            if tick % 10 == 0:
                print(
                    f"\r[t={tick:5d}] {speed_kph:5.1f}kph  "
                    f"str={steering:+.3f}  thr={throttle:.2f}  brk={brake:.2f}  "
                    f"off={lane.offset:+.3f}  conf={lane.confidence:.2f}  "
                    f"mode={mode.name}  dmg={dmg_total:.1f}",
                    end="", flush=True,
                )

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
        cv2.destroyAllWindows()
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
