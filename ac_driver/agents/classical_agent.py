"""
classical_agent.py
==================
Concrete agent implementing classical CV + PID control.

Architecture
------------
  frame  →  LaneDetector  →  offset (-1…+1)
                                   ↓
                           SteeringController (PID)  →  steer cmd
  speed_kph  →  SpeedController (PID)  →  throttle / brake

This agent requires no training data or model file and works
out-of-the-box as long as the road has visible lane markings.
"""

from __future__ import annotations

from config import CFG
from agents.base_agent import AbstractAgent, Observation
from control.control_arbiter import ControlCommand
from control.steering_controller import SteeringController
from control.speed_controller import SpeedController
from perception.lane_detection import LaneDetector, LaneDetectionResult


class ClassicalAgent(AbstractAgent):
    """
    Lane-detection + PID agent.

    Falls back to straight (steer=0) when lane detection confidence
    is below threshold, to avoid overreacting on noisy frames.
    """

    _MIN_CONFIDENCE = 0.3   # below this, ignore lane result and coast

    def __init__(self) -> None:
        self.detector      = LaneDetector(CFG.perception)
        self.steer_ctrl    = SteeringController()
        self.speed_ctrl    = SpeedController()
        self._fail_frames  = 0

    def select_action(self, obs: Observation) -> ControlCommand:
        result: LaneDetectionResult = self.detector.detect(obs.frame)

        if result.valid and result.confidence >= self._MIN_CONFIDENCE:
            steer_target    = result.offset
            self._fail_frames = 0
        else:
            steer_target    = 0.0
            self._fail_frames += 1

        steering          = self.steer_ctrl.compute(steer_target)
        throttle, brake   = self.speed_ctrl.compute(CFG.speed.target_kph,
                                                    obs.speed_kph)

        # Gentle braking on consecutive perception failures
        if self._fail_frames > CFG.safety.perception_fail_frames:
            brake = max(brake, 0.3)

        return ControlCommand(steering=steering, throttle=throttle, brake=brake)

    def reset(self) -> None:
        self.steer_ctrl.reset()
        self.speed_ctrl.reset()
        self._fail_frames = 0

    @property
    def last_detection(self) -> LaneDetectionResult:
        """Most recent lane detection — useful for the debug overlay."""
        return self.detector.last_result if hasattr(self.detector, "last_result") else None
