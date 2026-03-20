#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time

import numpy as np

from beamng_driver import (
    BEAMNG_HOME,
    BEAMNG_HOST,
    BEAMNG_PORT,
    BEAMNG_STEPS,
    LOCAL_BEAMNGPY_SRC,
    LOOP_HZ,
    _attach_vehicle_sensor,
    _densify_track_points,
    _normalize_xy,
    _resample_route_points,
    _road_length,
    _rotate_looped_route_to_spawn,
    _track_line_speed_profile,
    _wrap_angle,
)

if LOCAL_BEAMNGPY_SRC not in sys.path and os.path.isdir(LOCAL_BEAMNGPY_SRC):
    sys.path.insert(0, LOCAL_BEAMNGPY_SRC)

DRIFT_ROUTE_SPACING_M = 3.0
DRIFT_SMOOTH_SPACING_M = 2.5
DRIFT_LOOKAHEAD_BASE_M = 10.0
DRIFT_LOOKAHEAD_SPEED_GAIN = 0.34
DRIFT_PREVIEW_M = 30.0
DRIFT_DAMAGE_STOP = 120.0
DRIFT_ROUTE_LOST_M = 22.0
DRIFT_ROUTE_LOST_FRAMES = 45
DRIFT_STALL_S = 8.0
DRIFT_INIT_SPEED_KPH = 28.0
DRIFT_INIT_CURVATURE = 0.010
DRIFT_INIT_PULSE_S = 0.22
DRIFT_INIT_COOLDOWN_S = 1.1
DRIFT_MIN_SPEED_KPH = 24.0
DEFAULT_LOG = os.path.join("logs", "drift_run.csv")
DEFAULT_SUMMARY = os.path.join("logs", "drift_run.json")

PRESETS = {
    "west_coast_circuit": {
        "map": "west_coast_usa",
        "info": os.path.join("gameplay", "missions", "west_coast_usa", "drift", "006-circuit", "info.json"),
        "prefab": os.path.join("gameplay", "missions", "west_coast_usa", "drift", "006-circuit", "obstacles.prefab.json"),
        "road_name": "drift_aiRacePath1",
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Autonomous drift driver for BeamNG.tech.")
    p.add_argument("--beamng-home", default=BEAMNG_HOME)
    p.add_argument("--host", default=BEAMNG_HOST)
    p.add_argument("--port", type=int, default=BEAMNG_PORT)
    p.add_argument("--preset", choices=sorted(PRESETS.keys()), default="west_coast_circuit")
    p.add_argument("--vehicle", default=None)
    p.add_argument("--part-config", default=None)
    p.add_argument("--speed", type=float, default=68.0)
    p.add_argument("--speed-scale", type=float, default=0.82)
    p.add_argument("--max-slip-deg", type=float, default=20.0)
    p.add_argument("--max-runtime-seconds", type=float, default=75.0)
    p.add_argument("--target-laps", type=int, default=1)
    p.add_argument("--steering-log", default=DEFAULT_LOG)
    p.add_argument("--summary-json", default=DEFAULT_SUMMARY)
    p.add_argument("--no-route-debug", action="store_true")
    return p.parse_args()


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def abs_path(home: str, rel: str) -> str:
    return os.path.join(home, rel)


def load_route(home: str, preset_name: str) -> dict:
    preset = PRESETS[preset_name]
    info = load_json(abs_path(home, preset["info"]))
    mission = info.get("missionTypeData") or {}
    vehicles = (((info.get("setupModules") or {}).get("vehicles") or {}).get("vehicles") or [])
    vehicle_model = str((vehicles[0].get("model") if vehicles else None) or "bluebuck")
    part_config = (vehicles[0].get("configPath") if vehicles else None) or None
    spawn_pos = tuple(float(v) for v in mission.get("startPos", (0.0, 0.0, 0.0)))
    spawn_quat = tuple(float(v) for v in mission.get("startRot", (0.0, 0.0, 0.0, 1.0)))

    target = None
    with open(abs_path(home, preset["prefab"]), "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("class") == "DecalRoad" and obj.get("name") == preset["road_name"]:
                target = obj
                break
    if target is None:
        raise RuntimeError(f"Could not find route '{preset['road_name']}' for preset '{preset_name}'.")

    points = [np.asarray(node[:3], dtype=np.float64) for node in target.get("nodes") or [] if len(node) >= 3]
    if len(points) < 4:
        raise RuntimeError("Drift preset does not contain enough route points.")
    looped = float(np.linalg.norm(points[0][:2] - points[-1][:2])) < 18.0
    points = _densify_track_points(points, DRIFT_ROUTE_SPACING_M, looped)
    points = _resample_route_points(points, DRIFT_SMOOTH_SPACING_M, looped)
    if looped:
        points = _rotate_looped_route_to_spawn(points, spawn_pos, spawn_quat)
    if len(points) >= 2:
        start = points[0].copy()
        fwd = _normalize_xy(points[1][:2] - points[0][:2])
        yaw = -math.atan2(float(fwd[1]), float(fwd[0])) - (math.pi * 0.5)
        spawn_pos = (float(start[0]), float(start[1]), float(start[2] + 0.35))
        spawn_quat = (0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5))

    return {
        "name": preset_name,
        "map": preset["map"],
        "points": points,
        "looped": looped,
        "spawn_pos": spawn_pos,
        "spawn_quat": spawn_quat,
        "vehicle": vehicle_model,
        "part_config": part_config,
    }


def nearest_idx(points: list[np.ndarray], pos_xy: np.ndarray, prev_idx: int, looped: bool) -> int:
    n = len(points)
    best_idx = prev_idx
    best_dist = float("inf")
    back = 12 if looped else 0
    for step in range(-back, 81):
        idx = (prev_idx + step) % n if looped else min(max(prev_idx + step, 0), n - 1)
        dist = float(np.linalg.norm(points[idx][:2] - pos_xy))
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def advance_idx(points: list[np.ndarray], start_idx: int, distance_m: float, looped: bool) -> int:
    n = len(points)
    idx = start_idx
    travelled = 0.0
    while travelled < distance_m:
        nxt = (idx + 1) % n if looped else min(idx + 1, n - 1)
        if nxt == idx:
            break
        travelled += float(np.linalg.norm(points[nxt][:2] - points[idx][:2]))
        idx = nxt
    return idx


def signed_curvature(points: list[np.ndarray], idx: int, looped: bool) -> float:
    n = len(points)
    prev_idx = (idx - 2) % n if looped else max(0, idx - 2)
    next_idx = (idx + 2) % n if looped else min(n - 1, idx + 2)
    a = points[idx][:2] - points[prev_idx][:2]
    b = points[next_idx][:2] - points[idx][:2]
    len_a = float(np.linalg.norm(a))
    len_b = float(np.linalg.norm(b))
    if len_a < 1e-6 or len_b < 1e-6:
        return 0.0
    turn = _wrap_angle(math.atan2(float(b[1]), float(b[0])) - math.atan2(float(a[1]), float(a[0])))
    return turn / max(len_a + len_b, 1e-3)


def preview_curvature(points: list[np.ndarray], idx: int, looped: bool, distance_m: float) -> float:
    total = 0.0
    accum = 0.0
    count = 0
    current = idx
    while total < distance_m:
        nxt = advance_idx(points, current, DRIFT_ROUTE_SPACING_M, looped)
        if nxt == current:
            break
        total += float(np.linalg.norm(points[nxt][:2] - points[current][:2]))
        accum += signed_curvature(points, current, looped)
        count += 1
        current = nxt
    return accum / max(count, 1)


def filt_steer(prev: float, target: float) -> float:
    alpha = 0.5
    max_step = 0.22
    blended = prev + alpha * (target - prev)
    delta = blended - prev
    if abs(delta) > max_step:
        blended = prev + max_step * (1.0 if delta > 0.0 else -1.0)
    return float(np.clip(blended, -1.0, 1.0))


def control_step(route: dict, teacher_kph: list[float], state: dict, pos: np.ndarray, direction: np.ndarray, vel: np.ndarray, speed_kph: float, dt: float, args: argparse.Namespace) -> dict:
    points = route["points"]
    idx = nearest_idx(points, pos[:2], state["route_idx"], route["looped"])
    state["route_idx"] = idx
    lookahead_m = DRIFT_LOOKAHEAD_BASE_M + DRIFT_LOOKAHEAD_SPEED_GAIN * (speed_kph / 3.6)
    target_idx = advance_idx(points, idx, lookahead_m, route["looped"])
    prev_idx = (target_idx - 1) % len(points) if route["looped"] else max(0, target_idx - 1)
    next_idx = (target_idx + 1) % len(points) if route["looped"] else min(len(points) - 1, target_idx + 1)
    tangent = _normalize_xy(points[next_idx][:2] - points[prev_idx][:2])
    left_vec = np.array([-tangent[1], tangent[0]], dtype=np.float64)
    path_heading = math.atan2(float(tangent[1]), float(tangent[0]))
    body_heading = math.atan2(float(direction[1]), float(direction[0]))
    vel_heading = math.atan2(float(vel[1]), float(vel[0])) if np.linalg.norm(vel[:2]) > 0.8 else body_heading
    vel_heading_error = _wrap_angle(path_heading - vel_heading)
    curv = preview_curvature(points, idx, route["looped"], DRIFT_PREVIEW_M)
    corner_norm = float(np.clip(abs(curv) * 46.0, 0.0, 1.0))
    inside_offset_m = 3.2 * corner_norm
    inside_sign = 1.0 if curv > 0.0 else (-1.0 if curv < 0.0 else 0.0)
    target_xy = points[target_idx][:2] + left_vec * inside_sign * inside_offset_m
    lateral_error = float(np.dot(target_xy - pos[:2], left_vec))
    target_slip_deg = (2.0 + corner_norm * max(0.0, args.max_slip_deg - 2.0)) * (-1.0 if curv >= 0.0 else 1.0)
    target_slip = math.radians(target_slip_deg)
    slip = _wrap_angle(vel_heading - body_heading)
    body_target_heading = path_heading - target_slip
    body_heading_error = _wrap_angle(body_target_heading - body_heading)
    target_speed_kph = float(np.clip(teacher_kph[target_idx] * float(np.clip(args.speed_scale, 0.45, 1.2)), DRIFT_MIN_SPEED_KPH, args.speed))
    steer = (
        1.10 * body_heading_error
        + 0.95 * vel_heading_error
        + 0.55 * (lateral_error / max(lookahead_m, 1.0))
        + 1.30 * (slip - target_slip)
    )
    steer = filt_steer(state["prev_steer"], steer)
    state["prev_steer"] = steer

    speed_error = target_speed_kph - speed_kph
    target_slip_abs = abs(target_slip)
    slip_abs = abs(slip)
    slip_ratio = slip_abs / max(target_slip_abs, math.radians(3.0))
    throttle = 0.34 + 0.016 * speed_error + 0.16 * (1.0 - np.clip(slip_ratio, 0.0, 1.5)) + 0.08 * corner_norm
    brake = 0.0
    if speed_error < -8.0:
        brake = min(0.45, (-speed_error - 8.0) * 0.03)
        throttle = min(throttle, 0.1)
    if slip_abs > (target_slip_abs + math.radians(10.0)):
        throttle *= 0.45
    if corner_norm > 0.30:
        throttle = max(throttle, 0.22)
    if corner_norm > 0.45 and slip_abs < max(target_slip_abs * 0.60, math.radians(5.0)):
        throttle += 0.10
    throttle = float(np.clip(throttle, 0.0, 0.9))

    state["stall_s"] = state["stall_s"] + dt if speed_kph < 5.0 else 0.0
    if state["park_timer_s"] > 0.0:
        parking = 1.0
        state["park_timer_s"] = max(0.0, state["park_timer_s"] - dt)
    else:
        parking = 0.0
        state["park_cooldown_s"] = max(0.0, state["park_cooldown_s"] - dt)
        if (
            corner_norm > 0.34
            and speed_kph >= DRIFT_INIT_SPEED_KPH
            and abs(curv) >= DRIFT_INIT_CURVATURE
            and abs(lateral_error) < 5.5
            and slip_abs < max(target_slip_abs * 0.65, math.radians(5.0))
            and state["park_cooldown_s"] <= 0.0
        ):
            state["park_timer_s"] = DRIFT_INIT_PULSE_S
            state["park_cooldown_s"] = DRIFT_INIT_COOLDOWN_S
            parking = 1.0
    state["prev_corner_norm"] = corner_norm

    return {
        "steering": float(np.clip(steer, -1.0, 1.0)),
        "throttle": throttle,
        "brake": brake,
        "parkingbrake": parking,
        "slip_deg": math.degrees(slip),
        "target_slip_deg": target_slip_deg,
        "target_speed_kph": target_speed_kph,
        "teacher_speed_kph": teacher_kph[target_idx],
        "lateral_error_m": lateral_error,
        "route_idx": idx,
        "curvature": curv,
    }


def main() -> None:
    args = parse_args()
    from beamngpy import BeamNGpy, Scenario, Vehicle
    from beamngpy.sensors import Damage, Electrics

    route = load_route(args.beamng_home, args.preset)
    teacher_kph = [float(v * 3.6) for v in _track_line_speed_profile(route["points"], args.speed, 1.0, route["looped"])]
    vehicle_model = args.vehicle or route["vehicle"]
    part_config = args.part_config or route["part_config"]
    os.makedirs(os.path.dirname(args.steering_log) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.summary_json) or ".", exist_ok=True)

    print(f"[drift] preset={route['name']} map={route['map']} vehicle={vehicle_model} points={len(route['points'])}")
    bng = BeamNGpy(args.host, args.port, home=args.beamng_home or None)
    bng.open()
    log_file = None
    try:
        vehicle = Vehicle("drifter", model=vehicle_model, part_config=part_config)
        scenario = Scenario(route["map"], "auto_drift")
        scenario.add_vehicle(vehicle, pos=route["spawn_pos"], rot_quat=route["spawn_quat"], cling=False)
        scenario.make(bng)
        bng.scenario.load(scenario)
        bng.scenario.start()
        bng.control.pause()
        for fn, value in (("set_shift_mode", "arcade"), ("set_esc_mode", "off")):
            try:
                getattr(vehicle, fn)(value)
            except Exception:
                pass
        try:
            vehicle.ai.set_mode("disabled")
        except Exception:
            pass

        electrics = Electrics()
        damage = Damage()
        _attach_vehicle_sensor(vehicle, "electrics", electrics)
        _attach_vehicle_sensor(vehicle, "damage", damage)
        bng.control.step(BEAMNG_STEPS * 3)

        if not args.no_route_debug:
            try:
                bng.debug.add_polyline([tuple(float(v) for v in p[:3]) for p in route["points"]], (0.95, 0.55, 0.1, 0.8), cling=True, offset=0.15)
            except Exception:
                pass

        log_file = open(args.steering_log, "w", newline="", encoding="utf-8")
        writer = csv.writer(log_file)
        writer.writerow(["tick", "time_s", "speed_kph", "target_speed_kph", "steering", "steering_wheel_deg", "throttle", "brake", "parking", "slip_deg", "target_slip_deg", "lateral_error_m", "damage", "laps"])

        state = {"route_idx": 0, "prev_steer": 0.0, "prev_corner_norm": 0.0, "park_timer_s": 0.0, "park_cooldown_s": 0.0, "stall_s": 0.0}
        max_speed = 0.0
        max_damage = 0.0
        max_abs_slip = 0.0
        slip_integral = 0.0
        lost_frames = 0
        laps = 0
        left_start = False
        lap_start = time.perf_counter()
        last_pos = None
        dist_since_lap = 0.0
        start_t = lap_start
        last_tick_t = start_t
        last_status_t = start_t
        road_len = _road_length(route["points"])

        while True:
            loop_t0 = time.perf_counter()
            bng.control.step(BEAMNG_STEPS)
            vehicle.poll_sensors() if hasattr(vehicle, "poll_sensors") else vehicle.sensors.poll()
            now = time.perf_counter()
            dt = max(1e-3, now - last_tick_t)
            last_tick_t = now

            vehicle_state = getattr(vehicle, "state", {}) or {}
            pos = np.asarray(vehicle_state.get("pos") or (0.0, 0.0, 0.0), dtype=np.float64)
            direction = _normalize_xy(np.asarray(vehicle_state.get("dir") or (1.0, 0.0, 0.0), dtype=np.float64)[:2])
            vel = np.asarray(vehicle_state.get("vel") or (0.0, 0.0, 0.0), dtype=np.float64)
            speed_kph = float((dict(electrics).get("wheelspeed", 0.0) or 0.0) * 3.6)
            if speed_kph <= 0.25:
                speed_kph = float(np.linalg.norm(vel[:2]) * 3.6)
            damage_total = float((dict(damage).get("damage", 0.0) or 0.0))
            steering_wheel_deg = float((dict(electrics).get("steering", 0.0) or 0.0))

            ctl = control_step(route, teacher_kph, state, pos, direction, vel, speed_kph, dt, args)
            vehicle.control(steering=-ctl["steering"], throttle=ctl["throttle"], brake=ctl["brake"], parkingbrake=ctl["parkingbrake"])
            writer.writerow([int((now - start_t) * LOOP_HZ), f"{now - start_t:.3f}", f"{speed_kph:.3f}", f"{ctl['target_speed_kph']:.3f}", f"{ctl['steering']:.4f}", f"{steering_wheel_deg:.3f}", f"{ctl['throttle']:.4f}", f"{ctl['brake']:.4f}", f"{ctl['parkingbrake']:.4f}", f"{ctl['slip_deg']:.3f}", f"{ctl['target_slip_deg']:.3f}", f"{ctl['lateral_error_m']:.3f}", f"{damage_total:.3f}", laps])
            log_file.flush()

            max_speed = max(max_speed, speed_kph)
            max_damage = max(max_damage, damage_total)
            max_abs_slip = max(max_abs_slip, abs(ctl["slip_deg"]))
            slip_integral += abs(ctl["slip_deg"]) * dt
            lost_frames = lost_frames + 1 if abs(ctl["lateral_error_m"]) >= DRIFT_ROUTE_LOST_M else max(0, lost_frames - 1)

            if route["looped"]:
                if last_pos is not None:
                    step = float(np.linalg.norm(pos[:2] - last_pos[:2]))
                    if step < 35.0:
                        dist_since_lap += step
                last_pos = pos.copy()
                dist_to_start = float(np.linalg.norm(pos[:2] - np.asarray(route["spawn_pos"][:2], dtype=np.float64)))
                if dist_to_start > 32.0:
                    left_start = True
                if left_start and dist_to_start <= 14.0 and dist_since_lap >= max(180.0, road_len * 0.45) and (now - lap_start) >= 15.0:
                    laps += 1
                    print(f"[drift] lap {laps} in {now - lap_start:.1f}s")
                    lap_start = now
                    dist_since_lap = 0.0
                    left_start = False

            if now - last_status_t >= 1.0:
                print(f"[drift] t={now-start_t:5.1f}s speed={speed_kph:6.1f} slip={ctl['slip_deg']:6.1f} target={ctl['target_slip_deg']:6.1f} steer={ctl['steering']:+.2f} th={ctl['throttle']:.2f} pb={ctl['parkingbrake']:.2f} lat={ctl['lateral_error_m']:+5.2f} dmg={damage_total:6.1f} laps={laps}")
                last_status_t = now

            if damage_total >= DRIFT_DAMAGE_STOP:
                reason = "damage_stop"
                break
            if lost_frames >= DRIFT_ROUTE_LOST_FRAMES:
                reason = "route_lost"
                break
            if state["stall_s"] >= DRIFT_STALL_S:
                reason = "stalled"
                break
            if args.max_runtime_seconds > 0.0 and (now - start_t) >= args.max_runtime_seconds:
                reason = "max_runtime"
                break
            if route["looped"] and args.target_laps > 0 and laps >= args.target_laps:
                reason = "target_laps_reached"
                break

            sleep_for = max(0.0, (1.0 / LOOP_HZ) - (time.perf_counter() - loop_t0))
            if sleep_for > 0.0:
                time.sleep(sleep_for)

        summary = {
            "preset": route["name"],
            "map": route["map"],
            "vehicle": vehicle_model,
            "part_config": part_config,
            "elapsed_s": time.perf_counter() - start_t,
            "laps_completed": laps,
            "max_speed_kph": max_speed,
            "max_damage": max_damage,
            "max_abs_slip_deg": max_abs_slip,
            "avg_abs_slip_deg": slip_integral / max(time.perf_counter() - start_t, 1e-3),
            "reason": reason,
            "success": reason in ("target_laps_reached", "max_runtime"),
        }
        with open(args.summary_json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(json.dumps(summary, indent=2))
    finally:
        if log_file is not None:
            log_file.close()
        try:
            bng.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
