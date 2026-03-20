"""
controller_base.py - Abstract base class for lateral controllers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ControlOutput:
    """Output of a lateral + speed controller computation."""
    steering: float          # [-1, 1]
    throttle: float          # [0, 1]
    brake: float             # [0, 1]
    notes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def zero(cls) -> "ControlOutput":
        return cls(steering=0.0, throttle=0.0, brake=0.0)

    @classmethod
    def coast(cls, steering: float = 0.0) -> "ControlOutput":
        return cls(steering=steering, throttle=0.0, brake=0.0)


class ControllerBase(ABC):
    """
    Abstract base class for all lateral controllers.

    Subclasses implement:
        compute(vehicle_state, local_target, **kwargs) -> ControlOutput
        reset()
    """

    @abstractmethod
    def compute(self, vehicle_state, local_target, **kwargs) -> ControlOutput:
        """
        Compute a steering (and optionally throttle/brake) command.

        Parameters
        ----------
        vehicle_state : VehicleState
        local_target  : LocalTarget
        **kwargs      : additional inputs (curvature_est, conf_est, commitment, etc.)

        Returns
        -------
        ControlOutput
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state (e.g. integrators, filters)."""
        ...
