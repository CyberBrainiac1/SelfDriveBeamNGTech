#!/usr/bin/env python3
"""
main.py - BeamNG.tech self-driving system main entry point.

Usage:
  python src/main.py [--config CONFIG_PATH] [--beamng-home PATH] [--dry-run]
"""

import argparse
import sys
import time
import math
import traceback
from pathlib import Path

# Insert src/ into Python path so local imports work
sys.path.insert(0, str(Path(__file__).parent))

# -----------------------------------------------------------------------
# Local imports
# -----------------------------------------------------------------------
from config import Config
from logger import get_logger, configure_logging
from diagnostics import Diagnostics
from beamng_detector import BeamNGDetector
from beamng_bridge import BeamNGBridge
from beamng_manager import BeamNGManager
from vehicle_state import VehicleState
from coordinate_transform import CoordinateTransform
from lidar_preprocessor import LidarPreprocessor
from boundary_fitter import BoundaryFitter, CorridorBounds
from corridor_detector import CorridorDetector, CorridorEstimate
from local_curvature_estimator import LocalCurvatureEstimator, CurvatureEstimate
from straight_curve_classifier import StraightCurveClassifier, Classification
from confidence_estimator import ConfidenceEstimator, ConfidenceEstimate
from local_target_generator import LocalTargetGenerator, LocalTarget
from local_path_buffer import LocalPathBuffer
from steering_commitment_scheduler import SteeringCommitmentScheduler
from curve_speed_scheduler import CurveSpeedScheduler
from controller_manager import ControllerManager
from safety_manager import SafetyManager, SafetyState
from diagnostics_logger import DiagnosticsLogger

import numpy as np


# -----------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------
DEFAULT_CONFIG = str(Path(__file__).parent.parent / "config" / "hirochi_endurance.yaml")


# -----------------------------------------------------------------------
# Argument parser
# -----------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="BeamNG.tech self-driving system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--beamng-home",
        default=None,
        help="Override BeamNG installation path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run diagnostics only, do not start BeamNG",
    )
    parser.add_argument(
        "--lateral",
        default=None,
        choices=["mpcc_inspired", "pure_pursuit", "stanley"],
        help="Override lateral controller selection",
    )
    return parser.parse_args(argv)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main(argv=None):
    args = parse_args(argv)

    # ------------------------------------------------------------------
    # 1. Load config
    # ------------------------------------------------------------------
    try:
        config = Config.load(args.config)
    except FileNotFoundError as e:
        print(f"[ERROR] Config file not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Setup logging
    # ------------------------------------------------------------------
    configure_logging(config)
    logger = get_logger("main", config)
    logger.info("Config loaded from: %s", args.config)

    # ------------------------------------------------------------------
    # 3. Override lateral controller if specified
    # ------------------------------------------------------------------
    # (Not stored back to config object - passed directly to ControllerManager)

    # ------------------------------------------------------------------
    # 4. Diagnostics
    # ------------------------------------------------------------------
    diag = Diagnostics()
    bng_home_hint = args.beamng_home
    if bng_home_hint is None:
        try:
            bng_home_hint = config.beamng.home
        except AttributeError:
            pass

    all_ok = diag.run(bng_home=bng_home_hint)

    if not all_ok:
        logger.critical("Startup diagnostics failed. Exiting.")
        sys.exit(1)

    if args.dry_run:
        logger.info("Dry-run mode: diagnostics passed. Exiting without starting BeamNG.")
        return

    # ------------------------------------------------------------------
    # 5. Validate BeamNG path
    # ------------------------------------------------------------------
    detector = BeamNGDetector()
    try:
        bng_home = detector.detect(args.beamng_home)
    except RuntimeError as e:
        logger.critical("BeamNG path error: %s", e)
        sys.exit(1)

    logger.info("BeamNG home: %s", bng_home)

    # ------------------------------------------------------------------
    # 6. Build perception + control pipeline
    # ------------------------------------------------------------------
    coord_tf = CoordinateTransform()
    lidar_prep = LidarPreprocessor(config)
    boundary_fitter = BoundaryFitter(config)
    corridor_detector = CorridorDetector(config)
    curvature_estimator = LocalCurvatureEstimator(config)
    classifier = StraightCurveClassifier(config)
    conf_estimator = ConfidenceEstimator(config)
    target_gen = LocalTargetGenerator(config)
    path_buffer = LocalPathBuffer(config)
    commitment_sched = SteeringCommitmentScheduler(config)
    speed_sched = CurveSpeedScheduler(config)
    controller_mgr = ControllerManager(config)
    safety_mgr = SafetyManager(config)
    diag_logger = DiagnosticsLogger(config)

    logger.info("Pipeline built. Lateral controller: %s", controller_mgr.lateral_name)

    # ------------------------------------------------------------------
    # 7. Connect to BeamNG and start scenario
    # ------------------------------------------------------------------
    mgr = BeamNGManager()
    bridge: BeamNGBridge = None

    try:
        bridge = mgr.startup(config)
    except Exception as e:
        logger.critical("Failed to start BeamNG: %s\n%s", e, traceback.format_exc())
        sys.exit(1)

    # ------------------------------------------------------------------
    # 8. Warm-up delay (let physics settle)
    # ------------------------------------------------------------------
    try:
        startup_delay = float(config.runtime.startup_delay_seconds)
    except AttributeError:
        startup_delay = 0.5

    logger.info("Warming up for %.1f seconds...", startup_delay)
    time.sleep(startup_delay)

    # ------------------------------------------------------------------
    # 9. Main control loop
    # ------------------------------------------------------------------
    try:
        control_hz = float(config.runtime.control_hz)
    except AttributeError:
        control_hz = 25.0

    control_dt = 1.0 / control_hz

    try:
        max_runtime = float(config.runtime.max_runtime_seconds)
    except AttributeError:
        max_runtime = 900.0

    logger.info(
        "Starting control loop at %.1f Hz, max runtime %.0f s",
        control_hz, max_runtime,
    )

    # --- Fallback defaults ---
    fallback_conf = ConfidenceEstimate(
        geometry_confidence=0.0,
        temporal_confidence=0.0,
        corridor_confidence=0.0,
        combined_confidence=0.0,
        point_density_ratio=0.0,
    )
    fallback_curvature = CurvatureEstimate.straight()
    fallback_class = Classification.default()
    fallback_corridor = CorridorEstimate.invalid()

    loop_start = time.monotonic()
    tick = 0

    try:
        while True:
            tick_start = time.monotonic()

            # --- Runtime limit ---
            elapsed = tick_start - loop_start
            if elapsed > max_runtime:
                logger.info("Max runtime reached (%.0f s). Stopping.", elapsed)
                break

            tick += 1

            # --------------------------------------------------------
            # a. Poll vehicle state
            # --------------------------------------------------------
            vehicle_state = bridge.poll_state()
            if not vehicle_state.valid:
                logger.warning("Tick %d: invalid vehicle state, coasting.", tick)
                bridge.apply_control(steering=0.0, throttle=0.0, brake=0.0)
                _sleep_remainder(tick_start, control_dt)
                continue

            # --------------------------------------------------------
            # b. Poll LiDAR
            # --------------------------------------------------------
            lidar_world = bridge.poll_lidar()

            # --------------------------------------------------------
            # c. Transform LiDAR to vehicle frame
            # --------------------------------------------------------
            n_raw = len(lidar_world)
            if n_raw > 0:
                lidar_vehicle = coord_tf.lidar_to_vehicle(lidar_world.astype(np.float64), vehicle_state)
            else:
                lidar_vehicle = np.zeros((0, 3), dtype=np.float64)

            # --------------------------------------------------------
            # d. Preprocess LiDAR
            # --------------------------------------------------------
            lidar_filtered = lidar_prep.process(lidar_vehicle)
            n_pts = len(lidar_filtered)

            # --------------------------------------------------------
            # e-f. Fit boundaries & detect corridor
            # --------------------------------------------------------
            if n_pts >= lidar_prep.sufficient_points:
                bounds = boundary_fitter.fit(lidar_filtered)
            else:
                logger.debug("Tick %d: insufficient LiDAR points (%d). Using fallback.", tick, n_pts)
                bounds = CorridorBounds.invalid()

            raw_corridor = corridor_detector.update(bounds)
            corridor = path_buffer.update(raw_corridor)

            # --------------------------------------------------------
            # g. Estimate curvature
            # --------------------------------------------------------
            curvature_est = curvature_estimator.estimate(corridor)
            if not curvature_est.valid:
                curvature_est = fallback_curvature

            # --------------------------------------------------------
            # h. Classify segment
            # --------------------------------------------------------
            conf_est = conf_estimator.estimate(bounds, curvature_est, n_pts)
            classification = classifier.classify(curvature_est, corridor, conf_est.combined_confidence)

            # --------------------------------------------------------
            # i. Generate local target
            # --------------------------------------------------------
            local_target = target_gen.generate(
                corridor, vehicle_state, conf_est.combined_confidence, curvature_est.curvature
            )

            # --------------------------------------------------------
            # j. Compute commitment
            # --------------------------------------------------------
            commitment = commitment_sched.compute(
                conf_est, classification, curvature_est.curvature_trend
            )

            # --------------------------------------------------------
            # k. Compute speed target
            # --------------------------------------------------------
            target_kph = speed_sched.compute(
                curvature_est, conf_est, classification, vehicle_state.speed_kph
            )

            # --------------------------------------------------------
            # l-m. Compute lateral + speed control
            # --------------------------------------------------------
            control_out = controller_mgr.compute(
                vehicle_state=vehicle_state,
                local_target=local_target,
                curvature_est=curvature_est,
                conf_est=conf_est,
                classification=classification,
                commitment=commitment,
                target_kph=target_kph,
                dt=control_dt,
                corridor=corridor,
            )

            # --------------------------------------------------------
            # n. Safety checks
            # --------------------------------------------------------
            safety_status = safety_mgr.check(vehicle_state, local_target, control_out)

            if safety_status.should_stop:
                logger.error("Safety: EMERGENCY STOP - %s", safety_status.message)
                bridge.apply_control(steering=0.0, throttle=0.0, brake=1.0)
                break

            # Apply safety overrides
            steering = control_out.steering
            throttle = control_out.throttle
            brake = control_out.brake

            if safety_status.override_steering is not None:
                steering = safety_status.override_steering
            if safety_status.override_throttle is not None:
                throttle = safety_status.override_throttle
            if safety_status.override_brake is not None:
                brake = safety_status.override_brake

            # --------------------------------------------------------
            # o. Apply control
            # --------------------------------------------------------
            bridge.apply_control(steering=steering, throttle=throttle, brake=brake)

            # --------------------------------------------------------
            # p. Log diagnostics
            # --------------------------------------------------------
            heading_error = local_target.heading_at_target if local_target.valid else 0.0
            diag_logger.log(
                speed_kph=vehicle_state.speed_kph,
                steering=steering,
                throttle=throttle,
                brake=brake,
                curvature=curvature_est.curvature,
                turn_dir=curvature_est.turn_direction,
                straight_prob=classification.straight_probability,
                curve_conf=conf_est.combined_confidence,
                target_x=local_target.target_x,
                target_y=local_target.target_y,
                speed_target=target_kph,
                heading_error=heading_error,
                fit_quality=1.0 - min(1.0, bounds.fit_residual) if bounds.valid else 0.0,
                segment_type=classification.segment_type,
                commitment=commitment,
                n_lidar_pts=n_pts,
                pos_x=float(vehicle_state.pos[0]),
                pos_y=float(vehicle_state.pos[1]),
                pos_z=float(vehicle_state.pos[2]),
            )

            # --------------------------------------------------------
            # q. Maintain control_hz
            # --------------------------------------------------------
            _sleep_remainder(tick_start, control_dt)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down.")

    except Exception as e:
        logger.error("Control loop error: %s\n%s", e, traceback.format_exc())
        diag_logger.log_error(str(e))

    finally:
        # ------------------------------------------------------------------
        # 10. Cleanup
        # ------------------------------------------------------------------
        logger.info("Shutting down after %d ticks.", tick)

        # Stop vehicle
        if bridge is not None and bridge.is_connected:
            try:
                bridge.apply_control(steering=0.0, throttle=0.0, brake=1.0)
                time.sleep(0.2)
            except Exception:
                pass

        diag_logger.close()
        mgr.shutdown()
        logger.info("Self-drive session complete.")


# -----------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------

def _sleep_remainder(tick_start: float, target_dt: float) -> None:
    """Sleep for whatever time remains in the control period."""
    elapsed = time.monotonic() - tick_start
    remaining = target_dt - elapsed
    if remaining > 0.001:
        time.sleep(remaining)


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

if __name__ == "__main__":
    main()
