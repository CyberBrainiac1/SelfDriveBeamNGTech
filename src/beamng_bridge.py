"""
beamng_bridge.py — Low-level BeamNG.tech interface via BeamNGpy.

Manages the BeamNG connection, scenario setup, sensor polling, and
vehicle control commands.
"""

import time
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np

from logger import get_logger
from vehicle_state import VehicleState


class BeamNGBridge:
    """
    Core BeamNG interface.

    Wraps BeamNGpy API calls and handles error recovery.
    """

    def __init__(self, config=None):
        self._config = config
        self._logger = get_logger("BeamNGBridge", config)

        # BeamNGpy objects
        self._bng = None        # BeamNG instance
        self._scenario = None   # Scenario
        self._vehicle = None    # Vehicle
        self._lidar = None      # Lidar sensor
        self._electrics = None  # Electrics sensor
        self._state_sensor = None  # State sensor

        # Sensor data cache
        self._last_state_data: dict = {}
        self._last_elec_data: dict = {}

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        bng_home: str,
        host: str = "localhost",
        port: int = 64256,
        launch: bool = True,
    ) -> None:
        """
        Connect to (or launch) BeamNG.tech.

        Parameters
        ----------
        bng_home : path to BeamNG installation directory
        host     : hostname for BeamNGpy connection
        port     : port number
        launch   : if True, launch BeamNG; if False, connect to running instance
        """
        try:
            from beamngpy import BeamNG
        except ImportError as e:
            raise RuntimeError(
                "beamngpy not installed. Run: pip install beamngpy"
            ) from e

        self._logger.info("Connecting to BeamNG at %s:%d (home=%s, launch=%s)",
                          host, port, bng_home, launch)

        self._bng = BeamNG(home=bng_home, port=port)
        self._bng.open(launch=launch)
        self._logger.info("BeamNG connection established.")

    def close(self) -> None:
        """Cleanly disconnect from BeamNG."""
        if self._bng is not None:
            try:
                self._bng.close()
                self._logger.info("BeamNG connection closed.")
            except Exception as e:
                self._logger.warning("Error closing BeamNG: %s", e)
            self._bng = None

    # ------------------------------------------------------------------
    # Scenario setup
    # ------------------------------------------------------------------

    def setup_scenario(self, scenario_cfg=None) -> None:
        """
        Create and start the driving scenario.

        Uses config values from self._config if scenario_cfg is None.

        Parameters
        ----------
        scenario_cfg : config sub-object with scenario parameters (optional)
        """
        from beamngpy import Scenario, Vehicle
        from beamngpy.sensors import Lidar, Electrics, State

        cfg = scenario_cfg or (self._config.demo if self._config is not None else None)
        if cfg is None:
            raise ValueError("No scenario configuration provided.")

        map_name = cfg.map
        scenario_name = cfg.scenario_name
        vehicle_model = cfg.vehicle_model
        vehicle_id = cfg.vehicle_id
        spawn_pos = list(cfg.spawn_pos)
        spawn_rot_quat = list(cfg.spawn_rot_quat)

        self._logger.info("Setting up scenario '%s' on map '%s'", scenario_name, map_name)

        # Create scenario
        self._scenario = Scenario(map_name, scenario_name)

        # Create vehicle
        self._vehicle = Vehicle(vehicle_id, model=vehicle_model, license="SELFDRIVE")
        self._scenario.add_vehicle(self._vehicle, pos=spawn_pos, rot_quat=spawn_rot_quat)

        # Compile scenario
        self._scenario.make(self._bng)

        # Attach non-lidar sensors before loading
        self._electrics = Electrics()
        self._state_sensor = State()
        self._vehicle.attach_sensor("electrics", self._electrics)
        self._vehicle.attach_sensor("state", self._state_sensor)

        # Load + start scenario
        self._bng.scenario.load(self._scenario)
        self._bng.scenario.start()
        self._logger.info("Scenario started.")

        # Attach LiDAR after scenario start
        self._setup_lidar()

        self._logger.info("All sensors attached.")

    def _setup_lidar(self) -> None:
        """Attach and configure the LiDAR sensor."""
        from beamngpy.sensors import Lidar

        lidar_cfg = None
        if self._config is not None:
            try:
                lidar_cfg = self._config.perception.lidar
            except AttributeError:
                pass

        pos = (0.0, 0.0, 1.7)
        direction = (0.0, -1.0, 0.0)
        up = (0.0, 0.0, 1.0)
        vert_res = 24
        vert_angle = 18.0
        freq_hz = 20.0
        horiz_angle = 120.0
        max_dist = 120.0

        if lidar_cfg is not None:
            try:
                pos = tuple(lidar_cfg.pos)
                direction = tuple(lidar_cfg.dir)
                up = tuple(lidar_cfg.up)
                vert_res = int(lidar_cfg.vertical_resolution)
                vert_angle = float(lidar_cfg.vertical_angle_deg)
                freq_hz = float(lidar_cfg.frequency_hz)
                horiz_angle = float(lidar_cfg.horizontal_angle_deg)
                max_dist = float(lidar_cfg.max_distance_m)
            except AttributeError:
                pass

        try:
            self._lidar = Lidar(
                "lidar",
                self._bng,
                self._vehicle,
                pos=pos,
                dir=direction,
                up=up,
                vertical_resolution=vert_res,
                vertical_angle=vert_angle,
                frequency=freq_hz,
                horizontal_angle=horiz_angle,
                max_distance=max_dist,
                is_using_shared_memory=True,
            )
            self._logger.info("LiDAR sensor attached.")
        except Exception as e:
            self._logger.warning("LiDAR setup failed: %s. Continuing without LiDAR.", e)
            self._lidar = None

    # ------------------------------------------------------------------
    # Sensor polling
    # ------------------------------------------------------------------

    def poll_state(self) -> VehicleState:
        """
        Poll State and Electrics sensors and return a VehicleState.

        Returns
        -------
        VehicleState (valid=False on sensor error)
        """
        if self._vehicle is None:
            return VehicleState.invalid()

        try:
            self._vehicle.poll_sensors()
            state_data = self._state_sensor.data if self._state_sensor else {}
            elec_data = self._electrics.data if self._electrics else {}

            # Cache for debugging
            self._last_state_data = state_data or {}
            self._last_elec_data = elec_data or {}

            return VehicleState.from_sensor_data(state_data, elec_data)

        except Exception as e:
            self._logger.warning("poll_state error: %s", e)
            return VehicleState.invalid()

    def poll_lidar(self) -> np.ndarray:
        """
        Poll LiDAR sensor and return world-frame point cloud.

        Returns
        -------
        np.ndarray shape (N, 3) in world frame, or empty array if unavailable.
        """
        if self._lidar is None:
            return np.zeros((0, 3), dtype=np.float32)

        try:
            data = self._lidar.poll()
            if data is None:
                return np.zeros((0, 3), dtype=np.float32)

            pts = data.get("pointCloud", None)
            if pts is None:
                return np.zeros((0, 3), dtype=np.float32)

            pts = np.asarray(pts, dtype=np.float32)
            if pts.ndim == 1:
                # Flat array — reshape to (N, 3)
                n = len(pts) // 3
                pts = pts[:n * 3].reshape(n, 3)
            if pts.ndim != 2 or pts.shape[1] != 3:
                return np.zeros((0, 3), dtype=np.float32)

            return pts

        except Exception as e:
            self._logger.warning("poll_lidar error: %s", e)
            return np.zeros((0, 3), dtype=np.float32)

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def apply_control(
        self,
        steering: float,
        throttle: float,
        brake: float,
    ) -> None:
        """
        Send a control command to the vehicle.

        Parameters
        ----------
        steering : float [-1, 1]  negative = left
        throttle : float [0, 1]
        brake    : float [0, 1]
        """
        if self._vehicle is None:
            return

        # Clamp values
        steering = max(-1.0, min(1.0, float(steering)))
        throttle = max(0.0, min(1.0, float(throttle)))
        brake = max(0.0, min(1.0, float(brake)))

        try:
            self._vehicle.control(steering=steering, throttle=throttle, brake=brake)
        except Exception as e:
            self._logger.warning("apply_control error: %s", e)

    def set_deterministic(self, hz: int = 60) -> None:
        """Enable deterministic physics at the specified Hz."""
        if self._bng is None:
            return
        try:
            self._bng.settings.set_deterministic(hz)
            self._logger.info("Deterministic physics set to %d Hz.", hz)
        except Exception as e:
            self._logger.warning("set_deterministic error: %s", e)

    def hide_hud(self) -> None:
        """Hide the in-game HUD."""
        if self._bng is None:
            return
        try:
            self._bng.hide_hud()
        except Exception as e:
            self._logger.debug("hide_hud error: %s", e)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._bng is not None

    @property
    def vehicle(self):
        return self._vehicle

    @property
    def bng(self):
        return self._bng
