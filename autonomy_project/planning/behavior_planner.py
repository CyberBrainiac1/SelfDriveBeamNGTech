"""
Behavior planner — decides *what* the vehicle should be doing.

v1 modes:
  DRIVE        – normal lane following
  EMERGENCY    – road lost or obstacle; decelerate / stop
  STOPPED      – vehicle at rest; wait for conditions to clear

Future modes: OVERTAKE, FOLLOW, YIELD, PARK, SHARED_CONTROL …
"""

from __future__ import annotations
from enum import Enum, auto

from config import CFG
from perception.lane_detection import LaneDetectionResult
from perception.obstacle_detection import ObstacleResult
from perception.state_estimation import EgoState


class DrivingMode(Enum):
    DRIVE = auto()
    EMERGENCY = auto()
    STOPPED = auto()


class BehaviorPlanner:
    """Very simple state machine that picks a DrivingMode."""

    def __init__(self) -> None:
        self.mode = DrivingMode.DRIVE
        self._no_road_count: int = 0

    def update(
        self,
        lane: LaneDetectionResult,
        obstacle: ObstacleResult,
        ego: EgoState,
    ) -> DrivingMode:
        scfg = CFG.safety

        # Count consecutive frames without road detection
        if lane.confidence == 0.0:
            self._no_road_count += 1
        else:
            self._no_road_count = 0

        # Decide mode
        if obstacle.obstacle_ahead:
            self.mode = DrivingMode.EMERGENCY
        elif self._no_road_count >= scfg.perception_fail_frames:
            self.mode = DrivingMode.EMERGENCY
        elif ego.speed_kph > scfg.max_speed_kph:
            self.mode = DrivingMode.EMERGENCY
        elif ego.speed_kph < 0.5 and self.mode == DrivingMode.EMERGENCY:
            self.mode = DrivingMode.STOPPED
        else:
            self.mode = DrivingMode.DRIVE

        return self.mode
