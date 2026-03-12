"""
desktop_app/beamng/beamng_bridge.py — Bridge between BeamNG vehicle state
and the real wheel controller.

Converts BeamNG normalized steering (-1..+1) to real wheel target angles,
applies safety limits, and routes targets to SerialManager.
"""
from typing import Optional
from PySide6.QtCore import QObject, Signal


class BeamNGBridge(QObject):
    """
    Converts BeamNG vehicle telemetry into wheel target angles
    and sends them to the physical wheel controller via serial.

    steer_scale   — multiplier: 1.0 = BeamNG range maps to angle_range
    angle_range   — physical wheel range in degrees (e.g., 540.0)
    safety_max    — absolute angle limit for AI commands (degrees)
    """
    target_updated = Signal(float)  # new target angle in degrees

    def __init__(self, serial_manager, safety_manager, config):
        super().__init__()
        self._serial = serial_manager
        self._safety = safety_manager
        self._config = config
        self._active = False
        self._last_target: float = 0.0

    def configure_from_config(self):
        self._steer_scale = self._config.get("beamng.steer_scale", 1.0)
        self._angle_range = self._config.get("wheel.angle_range", 540.0)
        self._safety_max = self._config.get("beamng.safety_max_angle", 450.0)

    def activate(self):
        """Enable bridge — start forwarding BeamNG steering to wheel."""
        self.configure_from_config()
        self._active = True

    def deactivate(self):
        """Disable bridge — stop sending targets."""
        self._active = False
        if self._serial.is_connected:
            self._serial.set_target(0.0)

    @property
    def is_active(self) -> bool:
        return self._active

    def process_vehicle_state(self, state: dict):
        """
        Called with a new BeamNG vehicle state dict.
        Extracts steering_input, converts to angle, sends to wheel.
        """
        if not self._active:
            return

        normalized = float(state.get("steering_input", 0.0))
        angle = self.normalized_to_angle(normalized)
        angle = self._safety.clamp_target(angle)

        if abs(angle) > self._safety_max:
            self._safety.trigger_estop(f"AI angle limit exceeded: {angle:.1f}°")
            return

        self._last_target = angle
        self.target_updated.emit(angle)

        if self._serial.is_connected:
            self._serial.set_target(angle)

    def normalized_to_angle(self, normalized: float) -> float:
        """
        Convert BeamNG normalized steering (-1..+1) to wheel degrees.
        e.g., normalized=-1 → -270° (for 540° range)
        """
        half_range = (self._angle_range / 2.0) * self._steer_scale
        return normalized * half_range

    def angle_to_normalized(self, angle: float) -> float:
        """Inverse conversion: wheel degrees → normalized steering."""
        half_range = (self._angle_range / 2.0) * self._steer_scale
        if half_range == 0:
            return 0.0
        return max(-1.0, min(1.0, angle / half_range))

    @property
    def last_target(self) -> float:
        return self._last_target
