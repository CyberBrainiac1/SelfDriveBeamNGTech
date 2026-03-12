"""
desktop_app/beamng/ai_controller.py — AI steering controller.

Supports multiple steering target sources:
  MANUAL_TEST   — manual angle slider from UI
  REPLAY        — replay a recorded steering CSV
  PATH_FOLLOW   — simple path-following PD controller
  LANE_CENTER   — lane-centering logic (stub, needs vision data)
  BEAMNG        — live BeamNG vehicle steering input
"""
import time
import threading
from enum import Enum
from typing import Optional
from PySide6.QtCore import QObject, Signal


class TargetSource(str, Enum):
    MANUAL_TEST = "MANUAL_TEST"
    REPLAY      = "REPLAY"
    PATH_FOLLOW = "PATH_FOLLOW"
    LANE_CENTER = "LANE_CENTER"
    BEAMNG      = "BEAMNG"


class AIController(QObject):
    """
    Central AI steering controller.
    Computes a target angle each control cycle and sends it to the bridge.
    """
    target_computed = Signal(float)   # degrees
    mode_changed    = Signal(str)

    def __init__(self, bridge, safety_manager, logger):
        super().__init__()
        self._bridge = bridge
        self._safety = safety_manager
        self._log = logger
        self._source = TargetSource.MANUAL_TEST
        self._manual_target: float = 0.0
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Replay support
        self._replay_data: list = []
        self._replay_index: int = 0
        self._replay_loop: bool = False

        # Path follow
        self._path_kp: float = 1.5
        self._path_target: float = 0.0

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self):
        if self._active:
            return
        if not self._safety.enter_ai_mode():
            self._log.warning("AI controller blocked by safety manager")
            return
        self._active = True
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        self._log.info(f"AI controller started. Source: {self._source.value}")
        self.mode_changed.emit(self._source.value)

    def stop(self):
        self._active = False
        self._safety.exit_ai_mode()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._bridge.deactivate()
        self._log.info("AI controller stopped")
        self.mode_changed.emit("STOPPED")

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Source configuration
    # ------------------------------------------------------------------

    def set_source(self, source: TargetSource):
        with self._lock:
            self._source = source
        self.mode_changed.emit(source.value)

    def set_manual_target(self, angle: float):
        with self._lock:
            self._manual_target = angle

    def load_replay(self, filepath: str, loop: bool = False) -> bool:
        """Load a CSV replay file: each line is a target angle in degrees."""
        try:
            with open(filepath, "r") as f:
                lines = [l.strip() for l in f if l.strip()]
            data = [float(l.split(",")[0]) for l in lines if l]
            with self._lock:
                self._replay_data = data
                self._replay_index = 0
                self._replay_loop = loop
            self._log.info(f"Replay loaded: {len(data)} frames from {filepath}")
            return True
        except Exception as e:
            self._log.error(f"Replay load failed: {e}")
            return False

    def set_path_target(self, target: float):
        with self._lock:
            self._path_target = target

    # ------------------------------------------------------------------
    # Control loop
    # ------------------------------------------------------------------

    def _control_loop(self):
        """50 Hz control tick."""
        self._bridge.activate()
        dt = 0.02
        while self._active:
            t_start = time.time()
            self._safety.heartbeat()

            with self._lock:
                source = self._source

            target = self._compute_target(source)
            target = self._safety.clamp_target(target)
            self.target_computed.emit(target)

            if self._bridge.is_active and self._safety.is_connected_check():
                from core.serial_manager import SerialManager  # lazy import
                pass  # bridge.process_vehicle_state handled by signal

            # Direct serial send for non-BeamNG sources
            if source != TargetSource.BEAMNG:
                self._bridge._serial.set_target(target) if self._bridge._serial.is_connected else None

            elapsed = time.time() - t_start
            sleep_time = max(0.0, dt - elapsed)
            time.sleep(sleep_time)

    def _compute_target(self, source: TargetSource) -> float:
        if source == TargetSource.MANUAL_TEST:
            return self._manual_target

        elif source == TargetSource.REPLAY:
            with self._lock:
                if not self._replay_data:
                    return 0.0
                angle = self._replay_data[self._replay_index]
                self._replay_index += 1
                if self._replay_index >= len(self._replay_data):
                    if self._replay_loop:
                        self._replay_index = 0
                    else:
                        self._active = False
                        return 0.0
            return angle

        elif source == TargetSource.PATH_FOLLOW:
            # Simple proportional controller toward path_target
            current = 0.0  # would read from telemetry
            error = self._path_target - current
            return self._path_kp * error

        elif source == TargetSource.LANE_CENTER:
            # Stub: implement with camera/vision pipeline
            return 0.0

        elif source == TargetSource.BEAMNG:
            # Handled by bridge.process_vehicle_state
            return self._bridge.last_target

        return 0.0
