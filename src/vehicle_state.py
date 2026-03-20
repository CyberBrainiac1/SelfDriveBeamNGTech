"""
vehicle_state.py - VehicleState dataclass constructed from BeamNGpy 1.35 sensor data.

State sensor fields (BeamNGpy 1.35):
  - 'pos'      : (x, y, z) world position
  - 'dir'      : (x, y, z) forward direction unit vector in world frame
  - 'up'       : (x, y, z) up direction unit vector in world frame
  - 'vel'      : (vx, vy, vz) velocity in m/s
  - 'rotation' : (x, y, z, w) quaternion (NOT a matrix - we use dir/up instead)

Electrics sensor fields:
  - 'wheelspeed'     : m/s (wheel speed)
  - 'steering_input' : [-1, 1]
  - 'throttle_input' : [0, 1]
  - 'brake_input'    : [0, 1]
  - 'damage'         : cumulative damage
"""

import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class VehicleState:
    """
    Snapshot of vehicle state at a single timestep.
    All positions/velocities are in world frame unless noted.
    """
    pos: np.ndarray          # shape (3,) world XYZ
    vel: np.ndarray          # shape (3,) velocity vector m/s
    speed_mps: float         # scalar speed
    speed_kph: float
    heading_deg: float       # yaw degrees, 0 = +Y (north), positive = clockwise
    heading_rad: float
    rotation_matrix: np.ndarray  # shape (3,3) body-to-world; columns = [right, forward, up]
    steering: float          # [-1, 1]
    throttle: float          # [0, 1]
    brake: float             # [0, 1]
    damage: float
    timestamp: float
    valid: bool = True

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_sensor_data(
        cls,
        state_data: dict,
        elec_data: dict,
        timestamp: float = None,
    ) -> "VehicleState":
        """
        Construct VehicleState from BeamNGpy 1.35 State and Electrics sensor dicts.
        """
        if timestamp is None:
            timestamp = time.monotonic()

        # --- Position ---
        pos_raw = state_data.get("pos", [0.0, 0.0, 0.0])
        pos = np.array(pos_raw, dtype=np.float64)

        # --- Velocity ---
        vel_raw = state_data.get("vel", [0.0, 0.0, 0.0])
        vel = np.array(vel_raw, dtype=np.float64)
        speed_mps = float(np.linalg.norm(vel))

        # Electrics wheelspeed takes priority (smoothed wheel speed)
        elec_speed = elec_data.get("wheelspeed", None)
        if elec_speed is not None:
            speed_mps = abs(float(elec_speed))

        speed_kph = speed_mps * 3.6

        # --- Rotation matrix from dir + up vectors ---
        dir_raw = state_data.get("dir", [0.0, -1.0, 0.0])   # forward in world frame
        up_raw = state_data.get("up", [0.0, 0.0, 1.0])      # up in world frame

        rotation_matrix = cls._rotation_from_dir_up(dir_raw, up_raw)

        # --- Heading from dir vector ---
        # In BeamNG world: X=East, Y=North, Z=Up
        # dir = forward direction of vehicle in world frame
        # heading = angle from +Y (north), positive = clockwise (east)
        heading_rad, heading_deg = cls._heading_from_dir(dir_raw)

        # --- Electrics ---
        steering = float(elec_data.get("steering_input", 0.0))
        throttle = float(elec_data.get("throttle_input", 0.0))
        brake = float(elec_data.get("brake_input", 0.0))
        damage = float(elec_data.get("damage", 0.0))

        return cls(
            pos=pos,
            vel=vel,
            speed_mps=speed_mps,
            speed_kph=speed_kph,
            heading_deg=heading_deg,
            heading_rad=heading_rad,
            rotation_matrix=rotation_matrix,
            steering=steering,
            throttle=throttle,
            brake=brake,
            damage=damage,
            timestamp=timestamp,
            valid=True,
        )

    @classmethod
    def invalid(cls) -> "VehicleState":
        """Return a zero-value VehicleState marked as invalid."""
        return cls(
            pos=np.zeros(3),
            vel=np.zeros(3),
            speed_mps=0.0,
            speed_kph=0.0,
            heading_deg=0.0,
            heading_rad=0.0,
            rotation_matrix=np.eye(3),
            steering=0.0,
            throttle=0.0,
            brake=0.0,
            damage=0.0,
            timestamp=time.monotonic(),
            valid=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rotation_from_dir_up(dir_raw, up_raw) -> np.ndarray:
        """
        Build a 3x3 body-to-world rotation matrix from the vehicle's
        forward direction vector and up direction vector.

        The vehicle body frame is defined as:
          - Body X = right  (= cross(forward, up))
          - Body Y = forward (= dir)
          - Body Z = up     (= up, orthogonalised)

        So R = [right | forward | up_corrected]  (columns in world frame).

        world_to_vehicle = R.T
        """
        forward = np.array(dir_raw, dtype=np.float64)
        up = np.array(up_raw, dtype=np.float64)

        fwd_norm = np.linalg.norm(forward)
        if fwd_norm < 1e-6:
            return np.eye(3)
        forward = forward / fwd_norm

        up_norm = np.linalg.norm(up)
        if up_norm < 1e-6:
            up = np.array([0.0, 0.0, 1.0])
        else:
            up = up / up_norm

        right = np.cross(forward, up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6:
            # forward and up are parallel - degenerate, use fallback
            return np.eye(3)
        right = right / right_norm

        # Re-orthogonalise up
        up_corrected = np.cross(right, forward)
        up_corrected = up_corrected / np.linalg.norm(up_corrected)

        # Columns: right, forward, up
        R = np.column_stack([right, forward, up_corrected])
        return R

    @staticmethod
    def _heading_from_dir(dir_raw) -> tuple:
        """
        Compute heading (yaw) from the vehicle's forward direction vector.

        In BeamNG world frame: X=East, Y=North, Z=Up.
        heading = atan2(forward_x, forward_y)
          = 0 when pointing north (+Y)
          > 0 when pointing east (+X, clockwise from north)

        Returns (heading_rad, heading_deg).
        """
        fwd = np.array(dir_raw, dtype=np.float64)
        n = np.linalg.norm(fwd[:2])
        if n < 1e-6:
            return 0.0, 0.0
        heading_rad = math.atan2(float(fwd[0]), float(fwd[1]))
        heading_deg = math.degrees(heading_rad)
        return heading_rad, heading_deg
