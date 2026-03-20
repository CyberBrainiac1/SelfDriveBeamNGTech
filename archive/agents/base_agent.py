"""
base_agent.py
=============
Abstract agent interface + Observation dataclass for AC Driver.

Inspired by learn-to-race/l2r (github.com/learn-to-race/l2r) —
in particular l2r/core/templates.py's AbstractInterface pattern and the
multimodal observation philosophy.  Original implementation for AC.

All concrete agents (ClassicalAgent, NeuralAgent, etc.) inherit from
AbstractAgent so they are drop-in replaceable in the main loop.
"""

from __future__ import annotations
import abc
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from control.control_arbiter import ControlCommand


@dataclass
class Observation:
    """
    A single timestep snapshot handed to the agent.

    Bundles raw pixels + AC telemetry so that every agent implementation
    sees the same unified input structure regardless of which sensors it
    actually uses.

    Analogous to l2r's multimodal observation dict, adapted for Assetto
    Corsa telemetry.
    """
    # Visual
    frame: np.ndarray = field(default_factory=lambda: np.zeros((66, 200, 3), dtype=np.uint8))

    # Kinematics (from ACDriverApp telemetry JSON)
    speed_kph:    float = 0.0
    steer_norm:   float = 0.0   # -1 … +1  (steer_deg / 450)
    gas:          float = 0.0
    brake:        float = 0.0
    gear:         int   = 0
    rpm:          float = 0.0

    # Track position — AC's NormalizedSplinePosition (0 … 1)
    # Analogous to l2r's race_idx / n_indices
    lap_progress: float = 0.0
    lap_count:    int   = 0

    # Validity flag — False if telemetry is stale
    valid: bool = True


class AbstractAgent(abc.ABC):
    """
    Abstract base class for all driving agents.

    Inspired by l2r's AbstractInterface template — enforces a consistent
    interface so that agents are interchangeable in the main loop.

        obs = Observation(...)
        cmd = agent.select_action(obs)
        arbiter.apply(cmd)
    """

    @abc.abstractmethod
    def select_action(self, obs: Observation) -> ControlCommand:
        """
        Given the current observation, return a ControlCommand.

        This is the single method every agent must implement.  The main
        loop calls it once per tick.

        :param obs: current multimodal observation
        :return: steering + throttle + brake command
        """
        ...

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset any internal state between episodes / restarts."""
        ...

    def on_lap_complete(self, lap_time: float) -> None:
        """
        Optional hook called by the main loop when a lap is finished.
        Override to log, adjust policy, etc.
        """
