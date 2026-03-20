"""
vehicle_state.py — VehicleState dataclass constructed from BeamNGpy sensor data.
"""

import math
import time
from dataclasses import dataclass, field
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
    heading_deg: float       # yaw degrees, 0=north (+Y), increases clockwise
    heading_rad: float
    rotation_matrix: np.ndarray  # shape (3,3)
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
        Construct VehicleState from BeamNGpy State and Electrics sensor dicts.

        state_data keys (BeamNGpy State sensor):
            'pos'      : [x, y, z]
            'vel'      : [vx, vy, vz]
            'rotation' : 3x3 rotation matrix (flat list of 9 floats, row-major)
                         OR nested [[r0c0,r0c1,r0c2],[r1c0,...],...]
            'dir'      : forward direction vector (optional)
            'up'       : up direction vector (optional)

        elec_data keys (BeamNGpy Electrics sensor):
            'speed'          : m/s (may be labelled 'wheelspeed' on older builds)
            'steering_input' : [-1, 1]
            'throttle_input' : [0, 1]
            'brake_input'    : [0, 1]
            'damage'         : cumulative damage value
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

        # Electrics speed takes priority (filtered wheel speed)
        elec_speed = elec_data.get("speed", None)
        if elec_speed is not None:
            speed_mps = abs(float(elec_speed))

        speed_kph = speed_mps * 3.6

        # --- Rotation matrix ---
        rot_raw = state_data.get("rotation", None)
        rotation_matrix = cls._parse_rotation(rot_raw)

        # --- Heading ---
        heading_rad, heading_deg = cls._heading_from_rotation(rotation_matrix)

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
    def _parse_rotation(rot_raw) -> np.ndarray:
        """
        Parse rotation data from BeamNGpy into a 3x3 numpy array.
        Handles: None, flat list of 9, nested list of 3x3, or 4x4.
        """
        if rot_raw is None:
            return np.eye(3)

        arr = np.array(rot_raw, dtype=np.float64)

        if arr.shape == (3, 3):
            return arr
        if arr.shape == (9,):
            return arr.reshape(3, 3)
        if arr.shape == (4, 4):
            return arr[:3, :3]
        if arr.shape == (16,):
            return arr.reshape(4, 4)[:3, :3]

        # Fallback: identity
        return np.eye(3)

    @staticmethod
    def _heading_from_rotation(R: np.ndarray) -> tuple:
        """
        Extract yaw (heading) from a rotation matrix.

        In BeamNG the vehicle's forward direction is the -Y axis of the
        rotation matrix (column 1, negated).  We compute heading as:
            heading = atan2(forward_x, forward_y)
        where (forward_x, forward_y) is the world-frame forward vector.

        Returns (heading_rad, heading_deg).
        heading = 0   → pointing toward +Y (north in BeamNG)
        heading > 0   → clockwise from +Y
        """
        # Column 1 of R is the vehicle's +Y axis in world frame.
        # The vehicle forward is -Y body axis → +Y world column negated.
        forward_world = -R[:, 1]  # forward direction in world frame

        heading_rad = math.atan2(forward_world[0], forward_world[1])
        heading_deg = math.degrees(heading_rad)
        return heading_rad, heading_deg
