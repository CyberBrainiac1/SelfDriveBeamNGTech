"""
beamng_bridge.py - Low-level BeamNG.tech interface via BeamNGpy 1.35.

Manages the BeamNG connection, scenario setup, sensor polling, and
vehicle control commands.

BeamNGpy 1.35 API notes:
  - Main class is BeamNGpy(host, port, home=...), NOT BeamNG
  - Vehicle already auto-attaches a State sensor named 'state'
  - Sensors are dict subclasses; sensor.data is self (backwards compat)
  - Lidar is a standalone sensor (not via vehicle.attach_sensor)
  - LiDAR poll() returns {'pointCloud': np.ndarray (N,3), 'colours': ...}
    where pointCloud is in WORLD frame
"""

import time
from pathlib import Path
from typing import Optional

import numpy as np

from logger import get_logger
from vehicle_state import VehicleState


class BeamNGBridge:
    """
    Core BeamNG interface.

    Wraps BeamNGpy 1.35 API calls and handles error recovery.
    """

    def __init__(self, config=None):
        self._config = config
        self._logger = get_logger("BeamNGBridge", config)

        # BeamNGpy objects
        self._bng = None        # BeamNGpy instance
        self._scenario = None   # Scenario
        self._vehicle = None    # Vehicle
        self._lidar = None      # Lidar sensor
        self._electrics = None  # Electrics sensor
        self._state_sensor = None  # State sensor (auto-attached by Vehicle)

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
            from beamngpy import BeamNGpy
        except ImportError as e:
            raise RuntimeError(
                "beamngpy not installed. Run: pip install beamngpy"
            ) from e

        self._logger.info(
            "Connecting to BeamNG at %s:%d (home=%s, launch=%s)",
            host, port, bng_home, launch,
        )

        # BeamNGpy 1.35: BeamNGpy(host, port, home=...)
        self._bng = BeamNGpy(host, port, home=bng_home)
        self._bng.open(launch=launch)
        self._logger.info("BeamNG connection established.")

    def close(self) -> None:
        """Cleanly disconnect from BeamNG."""
        if self._lidar is not None:
            try:
                self._lidar.remove()
            except Exception:
                pass
            self._lidar = None

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

        Parameters
        ----------
        scenario_cfg : config sub-object with scenario parameters (optional)
        """
        from beamngpy import Scenario, Vehicle
        from beamngpy.sensors import Electrics

        cfg = scenario_cfg or (self._config.demo if self._config is not None else None)
        if cfg is None:
            raise ValueError("No scenario configuration provided.")

        map_name = cfg.map
        scenario_name = cfg.scenario_name
        vehicle_model = cfg.vehicle_model
        vehicle_id = cfg.vehicle_id
        spawn_pos = tuple(cfg.spawn_pos)
        spawn_rot_quat = tuple(cfg.spawn_rot_quat)

        self._logger.info(
            "Setting up scenario '%s' on map '%s' with vehicle '%s'",
            scenario_name, map_name, vehicle_model,
        )

        # Create scenario
        self._scenario = Scenario(map_name, scenario_name)

        # Create vehicle - Vehicle.__init__ auto-attaches State sensor as 'state'
        self._vehicle = Vehicle(vehicle_id, model=vehicle_model, license="SELFDRIVE")

        # Attach Electrics sensor before scenario.make()
        self._electrics = Electrics()
        self._vehicle.attach_sensor("electrics", self._electrics)

        # Add vehicle to scenario
        self._scenario.add_vehicle(self._vehicle, pos=spawn_pos, rot_quat=spawn_rot_quat)

        # Compile scenario files
        self._scenario.make(self._bng)

        # Load scenario - this also connects the vehicle and calls sensor.connect()
        self._bng.scenario.load(self._scenario, precompile_shaders=False)
        self._logger.info("Scenario loaded.")

        # Start scenario
        self._bng.scenario.start()
        self._logger.info("Scenario started.")

        # Grab reference to auto-attached State sensor (now connected)
        self._state_sensor = self._vehicle.sensors._sensors.get("state")
        if self._state_sensor is None:
            self._logger.warning("State sensor not found after scenario start.")

        # Attach LiDAR (must be after vehicle is connected and scenario started)
        self._setup_lidar()

        self._logger.info("All sensors ready.")

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

        # is_360_mode=False for a forward-facing cone rather than full 360
        is_360 = (horiz_angle >= 340.0)

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
                is_360_mode=is_360,
                is_using_shared_memory=True,
                is_visualised=False,
            )
            self._logger.info(
                "LiDAR attached (horiz=%.0f-, vert_res=%d, max_dist=%.0fm, 360=%s).",
                horiz_angle, vert_res, max_dist, is_360,
            )
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

            # State sensor is a dict (sensor.data = self for backwards compat)
            state_data = dict(self._state_sensor) if self._state_sensor else {}
            elec_data = dict(self._electrics) if self._electrics else {}

            # Cache for debugging
            self._last_state_data = state_data
            self._last_elec_data = elec_data

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

            # Lidar._convert_binary_to_array already reshapes to (N,3)
            if pts.ndim == 1:
                n = len(pts) // 3
                if n == 0:
                    return np.zeros((0, 3), dtype=np.float32)
                pts = pts[: n * 3].reshape(n, 3)

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
            # BeamNGpy 1.35: bng.settings.set_deterministic(steps_per_second)
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
