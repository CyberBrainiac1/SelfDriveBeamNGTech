"""
main.py
=======
AC Driver — main inference loop.

Modes
-----
  classical   Lane detection via OpenCV → PID steering (no ML, works immediately)
  neural      NVIDIA CNN inference → PID speed control  (requires trained model)

Architecture (inspired by learn-to-race/l2r)
--------------------------------------------
  Observation   ← captures frame + AC telemetry every tick
       ↓
  AbstractAgent.select_action(obs) → ControlCommand
       ↓             (ClassicalAgent or NeuralAgent)
  ControlArbiter.apply(cmd)   → vJoy / WASD keys
       ↓
  LapTracker.update(...)      → per-tick reward, lap completion
  MetricsLogger.record_tick() → CSV logging

Usage
-----
  # Classical (no model needed — works immediately)
    python main.py --mode classical

  # Neural (train model first with scripts/train.py)
    python main.py --mode neural

  # Override config at runtime
    python main.py --mode classical --target-speed 60 --debug

Prerequisite
------------
  Assetto Corsa must be running with the ACDriverApp Python app enabled.
  See README.md for full setup instructions.
"""

from __future__ import annotations
import argparse
import sys
import time
import cv2

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CFG
from agents.base_agent import Observation
from capture.screen_capture import ScreenCapture
from capture.ac_state_reader import ACStateReader
from control.control_arbiter import ControlArbiter, ControlCommand
from control.direct_keys import release_all
from track.lap_tracker import LapTracker
from utils.metrics_logger import MetricsLogger
from utils.timers import RateLimiter, FPSCounter
from utils.debug_overlay import draw_hud


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assetto Corsa autonomous driver")
    p.add_argument("--mode", choices=["classical", "neural"],
                   default="classical", help="Control strategy (default: classical)")
    p.add_argument("--target-speed", type=float, default=None,
                   help="Override target speed in kph")
    p.add_argument("--debug", action="store_true",
                   help="Show OpenCV debug window")
    p.add_argument("--no-log", action="store_true",
                   help="Disable CSV metrics logging")
    return p.parse_args()


def _build_agent(mode: str):
    if mode == "classical":
        from agents.classical_agent import ClassicalAgent
        print("[main] Mode: classical (lane detection + PID)")
        return ClassicalAgent()
    else:
        from agents.neural_agent import NeuralAgent
        print(f"[main] Mode: neural  (CNN model: {CFG.training.model_path})")
        return NeuralAgent()


def main() -> None:
    args = _parse_args()
    if args.target_speed is not None:
        CFG.speed.target_kph = args.target_speed

    # ── Build components ──────────────────────────────────────────
    agent        = _build_agent(args.mode)
    capture      = ScreenCapture()
    state_reader = ACStateReader(CFG.paths.state_file)
    arbiter      = ControlArbiter()
    tracker      = LapTracker()
    log_dir      = CFG.debug.csv_path.rsplit("/", 1)[0]
    metrics      = MetricsLogger(log_dir) if not args.no_log else None
    rate         = RateLimiter(CFG.capture.loop_hz)
    fps          = FPSCounter()

    # ── Wait for game ─────────────────────────────────────────────
    print("[main] Waiting for Assetto Corsa telemetry…")
    if not state_reader.wait_for_game(timeout_s=60):
        print("[main] Timed out — is the ACDriverApp active in-game?")
        sys.exit(1)
    print("[main] Game detected.  Starting in 3 s…")
    time.sleep(3)

    prev_laps = 0
    print(f"[main] Running.  Target speed: {CFG.speed.target_kph:.0f} kph  |  Press Ctrl+C to stop.")
    try:
        with capture:
            while True:
                # ── Sense ─────────────────────────────────────────
                frame = capture.grab()
                state = state_reader.read()

                obs = Observation(
                    frame        = frame,
                    speed_kph    = state.speed_kph,
                    steer_norm   = state.steer_norm,
                    gas          = state.gas,
                    brake        = state.brake,
                    gear         = state.gear,
                    rpm          = state.rpm,
                    lap_progress = state.lap_progress,
                    lap_count    = state.lap,
                    valid        = state.valid,
                )

                # ── Safety e-stop ─────────────────────────────────
                if state.speed_kph > CFG.safety.max_speed_kph or not state.valid:
                    arbiter.apply(ControlCommand(brake=1.0))
                    rate.wait()
                    continue

                # ── Think (agent) ─────────────────────────────────
                cmd = agent.select_action(obs)

                # ── Act ───────────────────────────────────────────
                arbiter.apply(cmd)

                # ── Track progress (l2r-style) ────────────────────
                reward = tracker.update(
                    spline_pos = state.lap_progress,
                    speed_kph  = state.speed_kph,
                    steer_norm = state.steer_norm,
                )

                # Lap completion hook
                if tracker.laps_completed > prev_laps:
                    prev_laps = tracker.laps_completed
                    agent.on_lap_complete(tracker.last_metrics.lap_time)
                    if metrics and tracker.last_metrics:
                        metrics.record_lap(tracker.last_metrics)

                # Stuck / wrong-way / timeout check
                done, reason = tracker.is_terminal()
                if done:
                    print(f"\n[main] Episode ended: {reason}")
                    arbiter.apply(ControlCommand(brake=1.0))
                    agent.reset()
                    tracker.reset()
                    prev_laps = 0
                    time.sleep(2)

                # ── Log ───────────────────────────────────────────
                if metrics:
                    metrics.record_tick(
                        speed_kph    = state.speed_kph,
                        steer_norm   = state.steer_norm,
                        steering_cmd = cmd.steering,
                        throttle     = cmd.throttle,
                        brake        = cmd.brake,
                        lap_progress = state.lap_progress,
                        reward       = reward,
                    )

                # ── Debug overlay ─────────────────────────────────
                if args.debug:
                    vis = draw_hud(
                        frame,
                        lane_offset = cmd.steering,
                        steering    = cmd.steering,
                        speed_kph   = state.speed_kph,
                        confidence  = 1.0,
                        mode        = args.mode,
                    )
                    cv2.imshow("ACDriver Debug", vis)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("\n[main] 'q' pressed — stopping.")
                        break

                current_fps = fps.tick()
                print(
                    f"\r[main] {current_fps:.1f} fps | "
                    f"speed {state.speed_kph:.0f} kph | "
                    f"steer {cmd.steering:+.3f} | "
                    f"reward {reward:+.2f} | "
                    f"lap {tracker.laps_completed}",
                    end="", flush=True,
                )

                rate.wait()

    except KeyboardInterrupt:
        print("\n[main] KeyboardInterrupt — stopping.")
    finally:
        arbiter.shutdown()
        release_all()
        cv2.destroyAllWindows()
        if metrics:
            metrics.close()
        print("[main] Shutdown complete.")


if __name__ == "__main__":
    main()
