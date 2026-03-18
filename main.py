"""
main.py
=======
Entry point — defaults to BeamNG.tech autonomous driving.

This script runs beamng_driver.py, the single-file BeamNG.tech driver.

Usage
-----
  # BeamNG.tech (default)
    python main.py

  # Override speed or map
    python main.py --speed 50 --map west_coast_usa

  # Disable the live debug window
    python main.py --no-overlay

  # Point to a custom BeamNG install
    python main.py --beamng-home "C:\\BeamNG.tech"

  # Legacy Assetto Corsa driver (classical or neural mode)
    python main.py --ac --mode classical
    python main.py --ac --mode neural

Prerequisites (BeamNG mode)
----------------------------
  pip install beamngpy opencv-python numpy
  BeamNG.tech must be installed (research/educational licence).
  See autonomy_project/README.md for details.

Prerequisites (Assetto Corsa legacy mode)
-----------------------------------------
  pip install mss opencv-python numpy
  Assetto Corsa must be running with ACDriverApp enabled.
  See README.md for full setup instructions.
"""

from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Autonomous driver — defaults to BeamNG.tech"
    )
    # BeamNG flags
    p.add_argument("--beamng-home", default=None,
                   help="Path to BeamNG.tech install folder")
    p.add_argument("--host", default="localhost", help="BeamNG host (default: localhost)")
    p.add_argument("--port", type=int, default=64256, help="BeamNG port (default: 64256)")
    p.add_argument("--speed", type=float, default=40.0,
                   help="Target cruise speed in kph (default: 40)")
    p.add_argument("--stage", choices=["idle", "cruise", "ai", "lane", "custom"], default="ai",
                   help="Bring-up stage: idle, cruise, built-in AI, lane, or custom lane following")
    p.add_argument("--ai-mode", choices=["traffic", "span"], default="span",
                   help="Built-in BeamNG AI mode when using --stage ai")
    p.add_argument("--ai-controller", choices=["auto", "span", "waypoints", "line"], default="line",
                   help="AI track controller when using --stage ai")
    p.add_argument("--ai-speed-mode", choices=["limit", "set"], default="limit",
                   help="Built-in BeamNG AI speed mode when using --stage ai")
    p.add_argument("--ai-aggression", type=float, default=0.85,
                   help="Built-in BeamNG AI aggression when using --stage ai")
    p.add_argument("--road-id", type=float, default=None,
                   help="Optional BeamNG road id for custom route following")
    p.add_argument("--steering-log", default="logs/steering_output.csv",
                   help="CSV path for steering-angle output in BeamNG mode")
    p.add_argument("--max-runtime-seconds", type=float, default=None,
                   help="Optional maximum BeamNG loop runtime before exit")
    p.add_argument("--target-laps", type=int, default=None,
                   help="Optional number of completed laps before exit on looped roads")
    p.add_argument("--summary-json", default=None,
                   help="Optional path to write a BeamNG run summary JSON")
    p.add_argument("--map", default="west_coast_usa", help="BeamNG map name")
    p.add_argument("--vehicle", default="etk800", help="BeamNG vehicle model")
    p.add_argument("--no-overlay", action="store_true",
                   help="Disable the live debug window")

    # Legacy AC mode
    p.add_argument("--ac", action="store_true",
                   help="Run legacy Assetto Corsa driver instead of BeamNG.tech")
    p.add_argument("--mode", choices=["classical", "neural"], default="classical",
                   help="AC driver mode (only used with --ac)")
    p.add_argument("--target-speed", type=float, default=None,
                   help="Override target speed for AC mode")
    p.add_argument("--debug", action="store_true",
                   help="Show debug window in AC mode")
    p.add_argument("--no-log", action="store_true",
                   help="Disable CSV logging in AC mode")
    return p.parse_args()


def _run_beamng(args: argparse.Namespace) -> None:
    """Launch the BeamNG.tech single-file driver."""
    import beamng_driver

    # Patch sys.argv so beamng_driver._parse_args() sees the right flags
    new_argv = [sys.argv[0]]
    if args.beamng_home:
        new_argv += ["--beamng-home", args.beamng_home]
    new_argv += ["--host", args.host, "--port", str(args.port)]
    new_argv += ["--speed", str(args.speed)]
    new_argv += ["--stage", args.stage]
    new_argv += ["--ai-mode", args.ai_mode]
    new_argv += ["--ai-controller", args.ai_controller]
    new_argv += ["--ai-speed-mode", args.ai_speed_mode]
    new_argv += ["--ai-aggression", str(args.ai_aggression)]
    if args.road_id is not None:
        new_argv += ["--road-id", str(args.road_id)]
    new_argv += ["--steering-log", args.steering_log]
    if args.max_runtime_seconds is not None:
        new_argv += ["--max-runtime-seconds", str(args.max_runtime_seconds)]
    if args.target_laps is not None:
        new_argv += ["--target-laps", str(args.target_laps)]
    if args.summary_json:
        new_argv += ["--summary-json", args.summary_json]
    new_argv += ["--map", args.map, "--vehicle", args.vehicle]
    if args.no_overlay:
        new_argv.append("--no-overlay")
    sys.argv = new_argv
    beamng_driver.main()


def _run_ac(args: argparse.Namespace) -> None:
    """Launch the legacy Assetto Corsa driver."""
    import time
    import cv2
    from config import CFG
    from agents.base_agent import Observation
    from capture.screen_capture import ScreenCapture
    from capture.ac_state_reader import ACStateReader
    from control.control_arbiter import ControlArbiter, ControlCommand
    from control.direct_keys import release_all, focus_assetto_window
    from track.lap_tracker import LapTracker
    from utils.metrics_logger import MetricsLogger
    from utils.timers import RateLimiter, FPSCounter
    from utils.debug_overlay import draw_hud

    if args.target_speed is not None:
        CFG.speed.target_kph = args.target_speed

    if args.mode == "classical":
        from agents.classical_agent import ClassicalAgent
        print("[main] AC mode: classical (lane detection + PID)")
        agent = ClassicalAgent()
    else:
        from agents.neural_agent import NeuralAgent
        print(f"[main] AC mode: neural (CNN model: {CFG.training.model_path})")
        agent = NeuralAgent()

    capture      = ScreenCapture()
    state_reader = ACStateReader(CFG.paths.state_file)
    arbiter      = ControlArbiter()
    tracker      = LapTracker()
    log_dir      = CFG.debug.csv_path.rsplit("/", 1)[0]
    metrics      = MetricsLogger(log_dir) if not args.no_log else None
    rate         = RateLimiter(CFG.capture.loop_hz)
    fps          = FPSCounter()

    print("[main] Waiting for Assetto Corsa telemetry…")
    if not state_reader.wait_for_game(timeout_s=60):
        print("[main] Timed out — is the ACDriverApp active in-game?")
        sys.exit(1)
    print("[main] Game detected.  Starting in 3 s…")
    time.sleep(3)

    prev_laps = 0
    no_input_frames = 0
    last_input_warn_t = 0.0
    print(f"[main] Running.  Target speed: {CFG.speed.target_kph:.0f} kph  |  Press Ctrl+C to stop.")
    try:
        with capture:
            while True:
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

                if state.speed_kph > CFG.safety.max_speed_kph or not state.valid:
                    arbiter.apply(ControlCommand(brake=1.0))
                    rate.wait()
                    continue

                cmd = agent.select_action(obs)
                arbiter.apply(cmd)

                if cmd.throttle > 0.5 and state.gas < 0.05 and state.speed_kph < 1.0:
                    no_input_frames += 1
                else:
                    no_input_frames = 0

                if no_input_frames >= 90 and (time.monotonic() - last_input_warn_t) > 5.0:
                    focused = focus_assetto_window()
                    print(
                        "\n[warn] Throttle command is high but telemetry gas/speed stay near zero. "
                        "Focus AC window, verify controls mapping, and try 'autoac mode -Value keys'. "
                        f"auto-focus attempted={focused}"
                    )
                    last_input_warn_t = time.monotonic()

                reward = tracker.update(
                    spline_pos = state.lap_progress,
                    speed_kph  = state.speed_kph,
                    steer_norm = state.steer_norm,
                )

                if tracker.laps_completed > prev_laps:
                    prev_laps = tracker.laps_completed
                    agent.on_lap_complete(tracker.last_metrics.lap_time)
                    if metrics and tracker.last_metrics:
                        metrics.record_lap(tracker.last_metrics)

                done, reason = tracker.is_terminal()
                if done:
                    print(f"\n[main] Episode ended: {reason}")
                    arbiter.apply(ControlCommand(brake=1.0))
                    agent.reset()
                    tracker.reset()
                    prev_laps = 0
                    time.sleep(2)

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


def main() -> None:
    args = _parse_args()
    if args.ac:
        _run_ac(args)
    else:
        _run_beamng(args)


if __name__ == "__main__":
    main()
