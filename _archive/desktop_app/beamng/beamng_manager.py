"""
desktop_app/beamng/beamng_manager.py — BeamNG.tech connection manager.
Manages the BeamNGpy instance, vehicle state, and connection lifecycle.
"""
import threading
import time
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal


class BeamNGManager(QObject):
    """
    Manages the connection to BeamNG.tech via BeamNGpy.
    Provides a thread-safe interface to vehicle telemetry and control.

    Signals:
        connected()           — BeamNG connection established
        disconnected()        — BeamNG connection lost
        vehicle_state(dict)   — new vehicle state received
        error(str)            — connection or API error
    """
    connected = Signal()
    disconnected = Signal()
    vehicle_state = Signal(dict)
    error = Signal(str)

    def __init__(self, serial_manager, logger):
        super().__init__()
        self._serial = serial_manager
        self._log = logger
        self._beamng = None
        self._vehicle = None
        self._connected = False
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False
        self._latest_state: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # BeamNGpy availability check
        self._beamngpy_available = self._check_beamngpy()

    def _check_beamngpy(self) -> bool:
        try:
            import beamngpy  # noqa: F401
            return True
        except ImportError:
            self._log.warning("beamngpy not installed — BeamNG AI mode will run in simulation")
            return False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, host: str = "localhost", port: int = 64256) -> bool:
        """Connect to a running BeamNG.tech instance."""
        if not self._beamngpy_available:
            self._log.error("beamngpy not available. Install with: pip install beamngpy")
            self.error.emit("beamngpy not installed")
            return False
        try:
            from beamngpy import BeamNGpy, Scenario, Vehicle
            from beamngpy.sensors import Electrics, IMU

            self._log.info(f"Connecting to BeamNG at {host}:{port}...")
            bng = BeamNGpy(host, port)
            bng.open(launch=False)
            self._beamng = bng

            # Attach to the first available vehicle
            scenario = bng.scenario.get_current()
            vehicles = scenario.vehicles if scenario else {}
            if not vehicles:
                self._log.warning("No vehicles found in current BeamNG scenario")
            else:
                veh_id = list(vehicles.keys())[0]
                self._vehicle = vehicles[veh_id]
                self._vehicle.attach_sensor("electrics", Electrics())
                self._vehicle.connect(bng)

            self._connected = True
            self._running = True
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()
            self._log.info("BeamNG connected")
            self.connected.emit()
            return True
        except Exception as e:
            self._log.error(f"BeamNG connect failed: {e}")
            self.error.emit(str(e))
            return False

    def disconnect(self):
        """Disconnect from BeamNG.tech."""
        self._running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)
        try:
            if self._beamng:
                self._beamng.close()
        except Exception:
            pass
        self._beamng = None
        self._vehicle = None
        self._connected = False
        self._log.info("BeamNG disconnected")
        self.disconnected.emit()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def beamngpy_available(self) -> bool:
        return self._beamngpy_available

    # ------------------------------------------------------------------
    # Vehicle state
    # ------------------------------------------------------------------

    def get_latest_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_state)

    def send_steering(self, normalized: float):
        """
        Send a steering command to BeamNG vehicle.
        normalized: -1.0 (full left) to +1.0 (full right)
        """
        normalized = max(-1.0, min(1.0, normalized))
        if not self._connected or self._vehicle is None:
            return
        try:
            self._vehicle.control(steering=normalized)
        except Exception as e:
            self._log.error(f"BeamNG steer command failed: {e}")

    def send_control(self, steering: float = 0.0, throttle: float = 0.0,
                     brake: float = 0.0):
        """Send full control inputs to BeamNG vehicle."""
        if not self._connected or self._vehicle is None:
            return
        try:
            self._vehicle.control(
                steering=max(-1.0, min(1.0, steering)),
                throttle=max(0.0, min(1.0, throttle)),
                brake=max(0.0, min(1.0, brake)),
            )
        except Exception as e:
            self._log.error(f"BeamNG control failed: {e}")

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Background thread: polls vehicle sensors at ~20 Hz."""
        while self._running:
            try:
                if self._vehicle is not None:
                    self._vehicle.poll_sensors()
                    electrics = self._vehicle.sensors.get("electrics")
                    if electrics:
                        state = {
                            "steering_input": electrics.data.get("steering_input", 0.0),
                            "steering": electrics.data.get("steering", 0.0),
                            "speed": electrics.data.get("wheelspeed", 0.0),
                            "throttle_input": electrics.data.get("throttle_input", 0.0),
                            "brake_input": electrics.data.get("brake_input", 0.0),
                            "gear": electrics.data.get("gear_a", 1),
                            "rpm": electrics.data.get("rpm", 0.0),
                        }
                        with self._lock:
                            self._latest_state = state
                        self.vehicle_state.emit(state)
                time.sleep(0.05)  # 20 Hz
            except Exception as e:
                self._log.error(f"BeamNG poll error: {e}")
                self._connected = False
                self.disconnected.emit()
                break
