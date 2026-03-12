"""
Sends steering / throttle / brake commands to the ego vehicle.

This is the ONLY place that talks to the vehicle actuators.
Everything upstream just produces a ControlCommand; this module applies it.
"""

from __future__ import annotations
from dataclasses import dataclass

from beamngpy import Vehicle


@dataclass
class ControlCommand:
    """
    Normalised actuation values sent to BeamNG each tick.
    steering : -1.0 (full left) … +1.0 (full right)
    throttle :  0.0 … 1.0
    brake    :  0.0 … 1.0
    """
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0

    def clamp(self) -> "ControlCommand":
        """Ensure all values are within legal ranges."""
        self.steering = max(-1.0, min(1.0, self.steering))
        self.throttle = max(0.0, min(1.0, self.throttle))
        self.brake = max(0.0, min(1.0, self.brake))
        return self


class VehicleController:
    """Applies a ControlCommand to a BeamNGpy Vehicle."""

    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle
        self.last_cmd = ControlCommand()

    def apply(self, cmd: ControlCommand) -> None:
        """Send commands to the simulator."""
        cmd.clamp()
        self._vehicle.control(
            steering=cmd.steering,
            throttle=cmd.throttle,
            brake=cmd.brake,
        )
        self.last_cmd = cmd

    def emergency_stop(self) -> None:
        """Full brake, zero throttle, zero steering."""
        self.apply(ControlCommand(steering=0.0, throttle=0.0, brake=1.0))
