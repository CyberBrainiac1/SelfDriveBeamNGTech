"""
coordinate_transform.py - Coordinate frame transformations.

Frame conventions:
  World frame : BeamNG world XYZ
  Vehicle frame: X=right, Y=forward, Z=up  (relative to vehicle)

LiDAR note: BeamNGpy returns point clouds in WORLD frame coordinates,
not sensor-local frame.  So lidar_to_vehicle() just calls world_to_vehicle().
"""

import numpy as np
from vehicle_state import VehicleState


class CoordinateTransform:
    """
    Static-like helpers for transforming point clouds between frames.
    """

    # ------------------------------------------------------------------
    # World - Vehicle
    # ------------------------------------------------------------------

    @staticmethod
    def world_to_vehicle(
        points_world: np.ndarray,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """
        Transform Nx3 world-frame points into the vehicle-centric frame.

        Vehicle frame:
            X = right
            Y = forward  (vehicle -Y body axis in world frame - vehicle Y here)
            Z = up

        Steps:
            1. Translate: subtract vehicle position.
            2. Rotate: multiply by R^T  (inverse of rotation matrix).

        The rotation matrix R stored in VehicleState is the body-to-world
        transform.  Its columns are the body axes expressed in world frame.
        R^T maps world vectors back to body vectors.

        In BeamNG the body axes are:
            Body +X - right  (world R[:,0])
            Body +Y - vehicle internal Y (sideways / up depending on model)
            Body -Y - forward in many BeamNG vehicles
            Body +Z - up

        We therefore apply one additional permutation to get our convention
        (X=right, Y=forward, Z=up).  The vehicle forward is body -Y, so
        vehicle_Y = -body_Y.  But after applying R^T we are in body frame.
        We flip the second axis to get vehicle frame.

        Parameters
        ----------
        points_world : np.ndarray, shape (N, 3)
        vehicle_state : VehicleState

        Returns
        -------
        np.ndarray shape (N, 3) in vehicle frame
        """
        if points_world.ndim != 2 or points_world.shape[1] != 3:
            raise ValueError(f"Expected (N,3) array, got {points_world.shape}")

        R = vehicle_state.rotation_matrix  # (3,3)
        pos = vehicle_state.pos            # (3,)

        # Translate to vehicle-centric world coords
        pts_centered = points_world - pos  # (N, 3)

        # Rotate to vehicle frame: vehicle = R^T @ centered
        # R is body-to-world with columns [right, forward, up].
        # R^T maps world vectors to body/vehicle frame directly.
        # pts_centered @ R is equivalent to (R^T @ pts_centered^T)^T
        pts_vehicle = pts_centered @ R        # (N,3): [X=right, Y=forward, Z=up]

        return pts_vehicle

    # ------------------------------------------------------------------
    # Vehicle - World
    # ------------------------------------------------------------------

    @staticmethod
    def vehicle_to_world(
        points_vehicle: np.ndarray,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """
        Transform Nx3 vehicle-frame points back to world frame.

        Inverse of world_to_vehicle.

        Parameters
        ----------
        points_vehicle : np.ndarray, shape (N, 3)  X=right, Y=forward, Z=up
        vehicle_state  : VehicleState

        Returns
        -------
        np.ndarray shape (N, 3) in world frame
        """
        if points_vehicle.ndim != 2 or points_vehicle.shape[1] != 3:
            raise ValueError(f"Expected (N,3) array, got {points_vehicle.shape}")

        R = vehicle_state.rotation_matrix  # (3,3)
        pos = vehicle_state.pos            # (3,)

        # Rotate vehicle frame - world: world = R @ vehicle
        # points_vehicle @ R.T is equivalent to (R @ points_vehicle^T)^T
        pts_world_centered = points_vehicle @ R.T   # (N, 3)

        # Translate
        pts_world = pts_world_centered + pos

        return pts_world

    # ------------------------------------------------------------------
    # LiDAR - Vehicle  (convenience wrapper)
    # ------------------------------------------------------------------

    @staticmethod
    def lidar_to_vehicle(
        points_lidar_world: np.ndarray,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """
        Transform LiDAR point cloud from world frame to vehicle frame.

        BeamNGpy LiDAR sensor returns points in WORLD frame regardless of
        sensor mounting.  This function is an alias for world_to_vehicle().

        Parameters
        ----------
        points_lidar_world : np.ndarray shape (N, 3)  world frame
        vehicle_state      : VehicleState

        Returns
        -------
        np.ndarray shape (N, 3) in vehicle frame (X=right, Y=forward, Z=up)
        """
        return CoordinateTransform.world_to_vehicle(points_lidar_world, vehicle_state)

    # ------------------------------------------------------------------
    # Single-point helpers
    # ------------------------------------------------------------------

    @staticmethod
    def point_world_to_vehicle(
        point_world: np.ndarray,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """Transform a single (3,) world point to vehicle frame."""
        pts = point_world.reshape(1, 3)
        return CoordinateTransform.world_to_vehicle(pts, vehicle_state).reshape(3)

    @staticmethod
    def point_vehicle_to_world(
        point_vehicle: np.ndarray,
        vehicle_state: VehicleState,
    ) -> np.ndarray:
        """Transform a single (3,) vehicle frame point to world frame."""
        pts = point_vehicle.reshape(1, 3)
        return CoordinateTransform.vehicle_to_world(pts, vehicle_state).reshape(3)
