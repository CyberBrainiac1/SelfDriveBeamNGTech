"""
Path planner — generates a desired path for the vehicle to follow.

v1: trivial "follow the lane centre" — the path is just the lane offset
     converted to a steering target.

Future upgrades:
  • Waypoint‑following with a list of (x, y) world coordinates.
  • A* or lattice planner for obstacle avoidance.
  • Trajectory optimisation for smooth cornering.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from perception.lane_detection import LaneDetectionResult
from perception.state_estimation import EgoState


@dataclass
class PlannedPath:
    """Describes the desired path — for now just a steering target."""
    steering_target: float = 0.0    # normalised: -1 … +1
    speed_target_kph: float = 40.0
    # Placeholder for future waypoint list
    waypoints: List[Tuple[float, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.waypoints is None:
            self.waypoints = []


class PathPlanner:
    """Currently a pass‑through: steering target = lane offset."""

    def plan(
        self,
        lane_result: LaneDetectionResult,
        ego: EgoState,
    ) -> PlannedPath:
        # Directly use lane offset as steering target
        return PlannedPath(
            steering_target=lane_result.offset,
        )
