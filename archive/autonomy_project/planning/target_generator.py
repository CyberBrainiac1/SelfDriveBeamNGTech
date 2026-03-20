"""
Target generator — converts the planned path + behavior mode into
concrete steering / speed targets for the control layer.
"""

from __future__ import annotations
from dataclasses import dataclass

from config import CFG
from planning.behavior_planner import DrivingMode
from planning.path_planner import PlannedPath
from perception.obstacle_detection import ObstacleResult
from perception.state_estimation import EgoState


@dataclass
class ControlTargets:
    """What the control layer should aim for this tick."""
    steering_target: float = 0.0    # -1 … +1
    speed_target_kph: float = 0.0
    emergency_stop: bool = False


class TargetGenerator:
    """Produce ControlTargets each tick."""

    def generate(
        self,
        mode: DrivingMode,
        path: PlannedPath,
        obstacle: ObstacleResult,
        ego: EgoState,
    ) -> ControlTargets:
        if mode == DrivingMode.EMERGENCY:
            return ControlTargets(
                steering_target=0.0,
                speed_target_kph=0.0,
                emergency_stop=True,
            )

        if mode == DrivingMode.STOPPED:
            return ControlTargets(
                steering_target=0.0,
                speed_target_kph=0.0,
                emergency_stop=False,
            )

        # Normal driving — modulate speed near obstacles
        target_speed = CFG.speed.target_speed_kph
        if obstacle.min_distance_m < 30.0:
            # Proportionally reduce speed as we get closer
            frac = max(0.0, obstacle.min_distance_m / 30.0)
            target_speed *= frac

        return ControlTargets(
            steering_target=path.steering_target,
            speed_target_kph=target_speed,
            emergency_stop=False,
        )
