#!/usr/bin/env python3
"""
main.py — Entry point for the custom autonomous driving system.

Launches BeamNG.tech, spawns a vehicle, runs the perception→planning→control
pipeline in a loop, and renders a live debug overlay.

Usage:
    cd autonomy_project
    python main.py

Press 'q' in the debug window to quit.
Press 'e' to toggle manual emergency stop.
"""

from __future__ import annotations

import os
import sys
import time

LOCAL_BEAMNGPY_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "BeamNGpy", "src")
)
if os.path.isdir(LOCAL_BEAMNGPY_SRC) and LOCAL_BEAMNGPY_SRC not in sys.path:
    sys.path.insert(0, LOCAL_BEAMNGPY_SRC)

from config import CFG
from beamng_interface.connection import SimConnection
from beamng_interface.scenario_manager import ScenarioManager
from beamng_interface.sensors import SensorSuite
from beamng_interface.vehicle_control import VehicleController
from beamng_interface.data_logger import DataLogger
from perception.lane_detection import LaneDetector
from perception.obstacle_detection import ObstacleDetector
from perception.state_estimation import StateEstimator
from planning.path_planner import PathPlanner
from planning.behavior_planner import BehaviorPlanner
from planning.target_generator import TargetGenerator
from control.control_arbiter import ControlArbiter
from utils.debug_overlay import DebugOverlay
from utils.timers import TickTimer, RateTracker


def main() -> None:
    print("=" * 60)
    print("  Custom Autonomous Driving System — v0.1")
    print("  Using BeamNG.tech + BeamNGpy")
    print("=" * 60)

    conn = SimConnection()
    logger = DataLogger()
    overlay = DebugOverlay()
    manual_estop = False

    try:
        # ── Startup ────────────────────────────────────────────────
        bng = conn.open()
        scene = ScenarioManager(bng)
        vehicle = scene.create_and_start()

        sensors = SensorSuite(vehicle, bng)
        sensors.attach_all()

        actuator = VehicleController(vehicle)
        logger.start()

        # ── Pipeline components ────────────────────────────────────
        lane_det = LaneDetector()
        obs_det = ObstacleDetector()
        state_est = StateEstimator()
        path_plan = PathPlanner()
        behavior = BehaviorPlanner()
        tgt_gen = TargetGenerator()
        arbiter = ControlArbiter()

        timer = TickTimer()
        rate = RateTracker()
        tick = 0
        dt_target = 1.0 / CFG.loop.target_hz

        print("\n[main] Entering main loop. Press 'q' in debug window to quit.\n")

        # ── Main loop ─────────────────────────────────────────────
        while True:
            t0 = time.perf_counter()
            tick += 1
            rate.tick()
            timer.reset()

            # 1) Step simulation
            timer.start("sim_step")
            bng.control.step(CFG.loop.beamng_steps)
            timer.stop("sim_step")

            # 2) Read sensors
            timer.start("sensors")
            sensor_data = sensors.poll()
            timer.stop("sensors")

            # 3) Perception
            timer.start("perception")
            ego = state_est.update(sensor_data)

            if sensor_data.colour_image is not None:
                lane_result = lane_det.detect(sensor_data.colour_image)
            else:
                from perception.lane_detection import LaneDetectionResult
                lane_result = LaneDetectionResult()

            obstacle_result = obs_det.detect(sensor_data.depth_image)
            timer.stop("perception")

            # 4) Planning
            timer.start("planning")
            mode = behavior.update(lane_result, obstacle_result, ego)
            path = path_plan.plan(lane_result, ego)
            targets = tgt_gen.generate(mode, path, obstacle_result, ego)
            timer.stop("planning")

            # 5) Control
            timer.start("control")
            if manual_estop:
                from beamng_interface.vehicle_control import ControlCommand
                cmd = ControlCommand(steering=0.0, throttle=0.0, brake=1.0)
            else:
                cmd = arbiter.compute(targets, mode, ego)
            actuator.apply(cmd)
            timer.stop("control")

            # 6) Logging
            logger.log(sensor_data, cmd, lane_offset=lane_result.offset)

            # 7) Debug overlay
            key = overlay.update(
                lane_result, obstacle_result, ego, mode, cmd,
                depth=sensor_data.depth_image,
            )
            if key == ord("q"):
                print("[main] Quit requested.")
                break
            if key == ord("e"):
                manual_estop = not manual_estop
                print(f"[main] Manual E‑STOP {'ON' if manual_estop else 'OFF'}")

            # 8) Telemetry printout
            if CFG.debug.print_telemetry and tick % CFG.debug.telemetry_interval == 0:
                print(
                    f"[t={tick:5d}] {rate.hz:4.1f}Hz  "
                    f"spd={ego.speed_kph:5.1f}kph  "
                    f"str={cmd.steering:+.3f}  thr={cmd.throttle:.3f}  brk={cmd.brake:.3f}  "
                    f"lane_off={lane_result.offset:+.3f}  conf={lane_result.confidence:.2f}  "
                    f"mode={mode.name}  "
                    f"| {timer.summary()}"
                )

            # 9) Rate limiting
            elapsed = time.perf_counter() - t0
            sleep_time = dt_target - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[main] KeyboardInterrupt — shutting down.")
    except Exception as exc:
        print(f"\n[main] Fatal error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        print("[main] Cleaning up …")
        overlay.close()
        logger.stop()
        try:
            scene.cleanup()
        except Exception:
            pass
        conn.close()
        print("[main] Done.")


if __name__ == "__main__":
    main()
