"""
Control arbiter — merges steering + speed outputs into a single
ControlCommand and applies safety overrides.

This is the integration point between planning/control and the vehicle.
Future features like shared control or manual override plug in here.
"""

from __future__ import annotations

from config import CFG
from control.steering_controller import SteeringController
from control.speed_controller import SpeedController
from planning.target_generator import ControlTargets
from planning.behavior_planner import DrivingMode
from beamng_interface.vehicle_control import ControlCommand
from perception.state_estimation import EgoState


class ControlArbiter:
    """Produces the final ControlCommand each tick."""

    def __init__(self) -> None:
        self.steer_ctrl = SteeringController()
        self.speed_ctrl = SpeedController()

    def compute(
        self,
        targets: ControlTargets,
        mode: DrivingMode,
        ego: EgoState,
    ) -> ControlCommand:
        # Emergency override
        if targets.emergency_stop or mode == DrivingMode.EMERGENCY:
            self.steer_ctrl.reset()
            self.speed_ctrl.reset()
            return ControlCommand(steering=0.0, throttle=0.0, brake=CFG.safety.emergency_brake_force)

        # Stopped
        if mode == DrivingMode.STOPPED:
            return ControlCommand(steering=0.0, throttle=0.0, brake=0.3)

        # Normal driving
        steering = self.steer_ctrl.compute(targets.steering_target)
        throttle, brake = self.speed_ctrl.compute(targets.speed_target_kph, ego.speed_kph)

        return ControlCommand(steering=steering, throttle=throttle, brake=brake)
