"""
test_pipeline.py — Unit tests for the self-driving pipeline modules.
Tests are offline-only: no BeamNG connection required.
"""

import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import numpy as np

from config import Config
from vehicle_state import VehicleState
from coordinate_transform import CoordinateTransform
from lidar_preprocessor import LidarPreprocessor
from boundary_fitter import BoundaryFitter, CorridorBounds
from corridor_detector import CorridorDetector, CorridorEstimate
from local_curvature_estimator import LocalCurvatureEstimator, CurvatureEstimate
from straight_curve_classifier import StraightCurveClassifier, Classification
from confidence_estimator import ConfidenceEstimator
from local_target_generator import LocalTargetGenerator, LocalTarget
from local_path_buffer import LocalPathBuffer
from steering_commitment_scheduler import SteeringCommitmentScheduler
from curve_speed_scheduler import CurveSpeedScheduler
from controllers.pure_pursuit_controller import PurePursuitController
from controllers.pid_speed_controller import PIDSpeedController
from controllers.mpcc_inspired_controller import MPCCInspiredController
from controllers.controller_base import ControlOutput
from safety_manager import SafetyManager, SafetyState


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "hirochi_endurance.yaml")


@pytest.fixture
def cfg():
    return Config.load(CONFIG_PATH)


# ── VehicleState ─────────────────────────────────────────────────────────────

class TestVehicleState:
    def test_invalid(self):
        vs = VehicleState.invalid()
        assert not vs.valid
        assert vs.speed_mps == 0.0

    def test_from_sensor_data_basic(self):
        state = {"pos": [10.0, 20.0, 5.0], "vel": [5.0, 0.0, 0.0],
                 "dir": [1.0, 0.0, 0.0], "up": [0.0, 0.0, 1.0]}
        elec = {"wheelspeed": 5.0, "steering_input": 0.1,
                "throttle_input": 0.5, "brake_input": 0.0}
        vs = VehicleState.from_sensor_data(state, elec)
        assert vs.valid
        assert vs.speed_mps == pytest.approx(5.0)
        assert vs.speed_kph == pytest.approx(18.0)
        assert vs.pos[0] == pytest.approx(10.0)

    def test_heading_north(self):
        state = {"pos": [0,0,0], "vel": [0,0,0],
                 "dir": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]}
        vs = VehicleState.from_sensor_data(state, {})
        assert vs.heading_deg == pytest.approx(0.0, abs=1.0)

    def test_heading_east(self):
        state = {"pos": [0,0,0], "vel": [0,0,0],
                 "dir": [1.0, 0.0, 0.0], "up": [0.0, 0.0, 1.0]}
        vs = VehicleState.from_sensor_data(state, {})
        assert vs.heading_deg == pytest.approx(90.0, abs=1.0)

    def test_rotation_matrix_orthogonal(self):
        state = {"pos": [0,0,0], "vel": [0,0,0],
                 "dir": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]}
        vs = VehicleState.from_sensor_data(state, {})
        R = vs.rotation_matrix
        assert R.shape == (3, 3)
        # R should be orthogonal: R @ R.T ≈ I
        err = np.abs(R @ R.T - np.eye(3)).max()
        assert err < 1e-9


# ── CoordinateTransform ───────────────────────────────────────────────────────

class TestCoordinateTransform:
    def test_world_to_vehicle_round_trip(self):
        ct = CoordinateTransform()
        vs = VehicleState.from_sensor_data(
            {"pos": [100.0, 200.0, 0.0], "vel": [0,0,0],
             "dir": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]}, {}
        )
        pts_world = np.array([[100.0, 210.0, 0.0],  # 10m forward
                               [105.0, 200.0, 0.0]]) # 5m right
        pts_veh = ct.world_to_vehicle(pts_world, vs)
        pts_back = ct.vehicle_to_world(pts_veh, vs)
        np.testing.assert_allclose(pts_back, pts_world, atol=1e-6)

    def test_forward_point_is_positive_y(self):
        ct = CoordinateTransform()
        # Vehicle facing north (+Y), at origin
        vs = VehicleState.from_sensor_data(
            {"pos": [0,0,0], "vel": [0,0,0],
             "dir": [0.0, 1.0, 0.0], "up": [0.0, 0.0, 1.0]}, {}
        )
        # A point 20m directly ahead (north = +Y world)
        pts_world = np.array([[0.0, 20.0, 0.0]])
        pts_veh = ct.world_to_vehicle(pts_world, vs)
        # Should be ~20m in vehicle Y (forward) direction
        assert pts_veh[0, 1] == pytest.approx(20.0, abs=0.5)


# ── LidarPreprocessor ────────────────────────────────────────────────────────

class TestLidarPreprocessor:
    def test_filters_behind_points(self, cfg):
        prep = LidarPreprocessor(cfg)
        pts = np.array([
            [0.0, -5.0, 1.0],   # behind — should be removed
            [0.0,  15.0, 1.0],  # ahead — keep
            [0.0,  80.0, 1.0],  # too far — remove
        ])
        result = prep.process(pts)
        # Only the 15m-ahead point should remain
        assert len(result) >= 1
        assert all(result[:, 1] > 0)

    def test_empty_input(self, cfg):
        prep = LidarPreprocessor(cfg)
        result = prep.process(np.zeros((0, 3)))
        assert len(result) == 0

    def test_sufficient_points_threshold(self, cfg):
        prep = LidarPreprocessor(cfg)
        assert prep.sufficient_points > 0


# ── BoundaryFitter ───────────────────────────────────────────────────────────

class TestBoundaryFitter:
    def _synthetic_corridor_points(self, n=300):
        """Generate synthetic corridor: straight ahead, 8m wide."""
        y = np.linspace(8, 70, n)
        # Left wall at x=-4, right wall at x=+4, noise included
        left = np.column_stack([-4.0 + np.random.randn(n)*0.1, y, np.ones(n)])
        right = np.column_stack([4.0 + np.random.randn(n)*0.1, y, np.ones(n)])
        mid = np.column_stack([np.random.uniform(-3.5, 3.5, 20),
                                np.random.uniform(8, 70, 20),
                                np.ones(20)])
        return np.vstack([left, right, mid])

    def test_straight_corridor(self, cfg):
        np.random.seed(42)
        fitter = BoundaryFitter(cfg)
        pts = self._synthetic_corridor_points()
        bounds = fitter.fit(pts)
        assert bounds.valid
        # width_estimates should be ~8m
        assert np.mean(bounds.width_estimates) == pytest.approx(8.0, abs=2.5)

    def test_invalid_on_empty(self, cfg):
        fitter = BoundaryFitter(cfg)
        bounds = fitter.fit(np.zeros((0, 3)))
        assert not bounds.valid


# ── Curvature Estimator ───────────────────────────────────────────────────────

class TestLocalCurvatureEstimator:
    def _straight_corridor(self):
        pts = [(0.0, y) for y in range(5, 60, 5)]  # (x, y) pairs
        est = CorridorEstimate.__new__(CorridorEstimate)
        est.center_line = pts
        est.valid = True
        est.n_valid_stations = len(pts)
        est.mean_width = 7.5
        est.tangents = [0.0] * len(pts)
        return est

    def test_straight_gives_low_curvature(self, cfg):
        estimator = LocalCurvatureEstimator(cfg)
        corridor = self._straight_corridor()
        result = estimator.estimate(corridor)
        assert result.valid
        assert abs(result.curvature) < 0.01

    def test_invalid_corridor_returns_straight(self, cfg):
        estimator = LocalCurvatureEstimator(cfg)
        corridor = CorridorEstimate.invalid()
        result = estimator.estimate(corridor)
        assert not result.valid or result.curvature == pytest.approx(0.0, abs=0.01)


# ── Classifier ───────────────────────────────────────────────────────────────

class TestStraightCurveClassifier:
    def test_zero_curvature_classifies_straight(self, cfg):
        clf = StraightCurveClassifier(cfg)
        # Build a fake CurvatureEstimate for zero curvature
        ce = CurvatureEstimate(
            curvature=0.0, radius_m=9999.0, turn_direction="straight",
            curvature_trend="stable", raw_curvature=0.0, valid=True,
        )
        corridor = CorridorEstimate.__new__(CorridorEstimate)
        corridor.valid = True
        corridor.center_line = [(0, y) for y in range(0, 60, 5)]
        corridor.n_valid_stations = 12
        corridor.mean_width = 7.5
        corridor.tangents = [0.0] * 12
        result = clf.classify(ce, corridor, confidence=0.9)
        assert result.straight_probability > 0.5

    def test_high_curvature_classifies_curve(self, cfg):
        clf = StraightCurveClassifier(cfg)
        ce = CurvatureEstimate(
            curvature=0.05, radius_m=20.0, turn_direction="left",
            curvature_trend="stable", raw_curvature=0.05, valid=True,
        )
        corridor = CorridorEstimate.__new__(CorridorEstimate)
        corridor.valid = True
        corridor.center_line = [(0, y) for y in range(0, 60, 5)]
        corridor.n_valid_stations = 12
        corridor.mean_width = 7.5
        corridor.tangents = [0.0] * 12
        result = clf.classify(ce, corridor, confidence=0.85)
        assert result.straight_probability < 0.3


# ── PID Speed Controller ──────────────────────────────────────────────────────

class TestPIDSpeedController:
    def test_coast_in_band(self, cfg):
        ctrl = PIDSpeedController(cfg)
        thr, brk = ctrl.compute(50.0, 50.0)
        assert thr == 0.0 and brk == 0.0

    def test_accelerate_when_slow(self, cfg):
        ctrl = PIDSpeedController(cfg)
        for _ in range(5):
            thr, brk = ctrl.compute(80.0, 20.0)
        assert thr > 0.0 and brk == 0.0

    def test_brake_when_fast(self, cfg):
        ctrl = PIDSpeedController(cfg)
        for _ in range(5):
            thr, brk = ctrl.compute(20.0, 80.0)
        assert brk > 0.0 and thr == 0.0

    def test_outputs_clamped(self, cfg):
        ctrl = PIDSpeedController(cfg)
        thr, brk = ctrl.compute(0.0, 200.0)
        assert 0.0 <= thr <= 1.0
        assert 0.0 <= brk <= 1.0


# ── Pure Pursuit ──────────────────────────────────────────────────────────────

class TestPurePursuitController:
    def _make_vs(self, speed_kph=50.0, heading_deg=0.0):
        state = {"pos": [0,0,0], "vel": [0,0,0],
                 "dir": [math.sin(math.radians(heading_deg)),
                         math.cos(math.radians(heading_deg)), 0.0],
                 "up": [0.0, 0.0, 1.0]}
        elec = {"wheelspeed": speed_kph / 3.6}
        return VehicleState.from_sensor_data(state, elec)

    def _make_target(self, x=0.0, y=20.0):
        t = LocalTarget.__new__(LocalTarget)
        t.target_x = x
        t.target_y = y
        t.target_world_pos = np.array([x, y, 0.0])
        t.heading_at_target = math.atan2(x, y)
        t.lookahead_m = math.sqrt(x*x + y*y)
        t.valid = True
        return t

    def test_straight_target_zero_steering(self, cfg):
        ctrl = PurePursuitController(cfg)
        vs = self._make_vs()
        target = self._make_target(x=0.0, y=20.0)
        out = ctrl.compute(vs, target)
        assert abs(out.steering) < 0.05

    def test_right_target_positive_steering(self, cfg):
        ctrl = PurePursuitController(cfg)
        vs = self._make_vs()
        target = self._make_target(x=5.0, y=20.0)
        out = ctrl.compute(vs, target)
        assert out.steering > 0.0

    def test_left_target_negative_steering(self, cfg):
        ctrl = PurePursuitController(cfg)
        vs = self._make_vs()
        target = self._make_target(x=-5.0, y=20.0)
        out = ctrl.compute(vs, target)
        assert out.steering < 0.0

    def test_steering_clamped(self, cfg):
        ctrl = PurePursuitController(cfg)
        vs = self._make_vs()
        target = self._make_target(x=100.0, y=1.0)  # extreme right
        out = ctrl.compute(vs, target)
        assert -1.0 <= out.steering <= 1.0


# ── Commitment Scheduler ──────────────────────────────────────────────────────

class TestSteeringCommitmentScheduler:
    def test_high_confidence_high_commitment(self, cfg):
        sched = SteeringCommitmentScheduler(cfg)
        from confidence_estimator import ConfidenceEstimate
        from straight_curve_classifier import Classification
        conf = ConfidenceEstimate(
            geometry_confidence=0.9, temporal_confidence=0.9,
            corridor_confidence=0.9, combined_confidence=0.9,
            point_density_ratio=1.0,
        )
        clf = Classification.default()
        commitment = sched.compute(conf, clf, "stable")
        assert commitment > 0.65

    def test_zero_confidence_low_commitment(self, cfg):
        sched = SteeringCommitmentScheduler(cfg)
        from confidence_estimator import ConfidenceEstimate
        from straight_curve_classifier import Classification
        conf = ConfidenceEstimate(
            geometry_confidence=0.0, temporal_confidence=0.0,
            corridor_confidence=0.0, combined_confidence=0.0,
            point_density_ratio=0.0,
        )
        clf = Classification.default()
        commitment = sched.compute(conf, clf, "stable")
        assert commitment < 0.5


# ── Safety Manager ────────────────────────────────────────────────────────────

class TestSafetyManager:
    def test_normal_state_no_override(self, cfg):
        mgr = SafetyManager(cfg)
        vs = VehicleState.from_sensor_data(
            {"pos": [0,0,0], "vel": [0,10,0],
             "dir": [0.0,1.0,0.0], "up": [0.0,0.0,1.0]},
            {"wheelspeed": 10.0}
        )
        ctrl = ControlOutput(steering=0.1, throttle=0.5, brake=0.0)
        status = mgr.check(vs, None, ctrl)
        assert not status.should_stop

    def test_over_speed_triggers_safety(self, cfg):
        mgr = SafetyManager(cfg)
        vs = VehicleState.from_sensor_data(
            {"pos": [0,0,0], "vel": [0, 60, 0],  # ~216 kph
             "dir": [0.0,1.0,0.0], "up": [0.0,0.0,1.0]},
            {"wheelspeed": 60.0}
        )
        ctrl = ControlOutput(steering=0.0, throttle=1.0, brake=0.0)
        status = mgr.check(vs, None, ctrl)
        # Should at least cap throttle
        assert status.override_throttle is not None or status.override_brake is not None or status.should_stop
