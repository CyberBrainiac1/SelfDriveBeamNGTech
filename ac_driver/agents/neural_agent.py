"""
neural_agent.py
===============
Concrete agent implementing NVIDIA CNN end-to-end steering inference.

Architecture
------------
  frame  →  SteeringPredictor (CNN)  →  steer (-1…+1)
  speed_kph  →  SpeedController (PID)  →  throttle / brake

The model must be trained first via:
  python ac_driver/scripts/train.py

The steering network predicts a normalised steering angle directly from
raw pixels — it does NOT use explicit lane detection, making it more
robust to unusual lighting or track markings.
"""

from __future__ import annotations

from config import CFG
from agents.base_agent import AbstractAgent, Observation
from control.control_arbiter import ControlCommand
from control.speed_controller import SpeedController
from training.infer import SteeringPredictor


class NeuralAgent(AbstractAgent):
    """
    NVIDIA CNN steering + PID speed agent.

    On init, tries to load the model from CFG.training.model_path.
    Raises FileNotFoundError if not found — train first.
    """

    def __init__(self) -> None:
        self.predictor = SteeringPredictor(CFG.training.model_path)
        if not self.predictor.load():
            raise FileNotFoundError(
                f"No model found at '{CFG.training.model_path}'.\n"
                "Run:  python ac_driver/scripts/train.py"
            )
        self.speed_ctrl = SpeedController()

    def select_action(self, obs: Observation) -> ControlCommand:
        steering          = float(self.predictor.predict(obs.frame))
        throttle, brake   = self.speed_ctrl.compute(CFG.speed.target_kph,
                                                    obs.speed_kph)
        return ControlCommand(steering=steering, throttle=throttle, brake=brake)

    def reset(self) -> None:
        self.speed_ctrl.reset()
