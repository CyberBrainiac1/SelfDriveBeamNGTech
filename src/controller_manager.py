"""
controller_manager.py — Select and invoke lateral + speed controllers.

Reads the lateral controller choice from config and delegates accordingly.
"""

from typing import Optional

from logger import get_logger
from controllers.controller_base import ControlOutput, ControllerBase
from controllers.pid_speed_controller import PIDSpeedController


class ControllerManager:
    """
    Manages lateral controller selection and invocation.

    Lateral controllers:
        'mpcc_inspired'  (default)
        'pure_pursuit'
        'stanley'

    Speed controller: always PIDSpeedController.
    """

    LATERAL_OPTIONS = ("mpcc_inspired", "pure_pursuit", "stanley")

    def __init__(self, config=None):
        self._config = config
        self._logger = get_logger("ControllerManager", config)

        # Determine selected lateral controller
        lateral_name = "mpcc_inspired"
        try:
            lateral_name = str(config.controllers.lateral).lower()
        except AttributeError:
            pass

        if lateral_name not in self.LATERAL_OPTIONS:
            self._logger.warning(
                "Unknown lateral controller '%s'. Defaulting to 'mpcc_inspired'.", lateral_name
            )
            lateral_name = "mpcc_inspired"

        self._lateral_name = lateral_name
        self._lateral: ControllerBase = self._build_lateral(lateral_name, config)
        self._speed: PIDSpeedController = PIDSpeedController(config)
        self._logger.info("Lateral controller: %s", lateral_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        vehicle_state,
        local_target,
        curvature_est=None,
        conf_est=None,
        classification=None,
        commitment: float = 0.80,
        target_kph: float = 60.0,
        dt: float = 0.04,
        corridor=None,
    ) -> ControlOutput:
        """
        Compute a full control output (steering + throttle + brake).

        Parameters
        ----------
        vehicle_state : VehicleState
        local_target  : LocalTarget
        curvature_est : CurvatureEstimate
        conf_est      : ConfidenceEstimate
        classification: Classification
        commitment    : float [0,1]
        target_kph    : desired speed
        dt            : timestep
        corridor      : CorridorEstimate (passed to MPCC)

        Returns
        -------
        ControlOutput
        """
        # Lateral steering
        lat_out = self._lateral.compute(
            vehicle_state,
            local_target,
            curvature_est=curvature_est,
            conf_est=conf_est,
            commitment=commitment,
            corridor=corridor,
        )

        # Speed control
        throttle, brake = self._speed.compute(
            target_kph=target_kph,
            current_kph=vehicle_state.speed_kph,
            steering=lat_out.steering,
            dt=dt,
        )

        return ControlOutput(
            steering=lat_out.steering,
            throttle=throttle,
            brake=brake,
            notes={**lat_out.notes, "target_kph": target_kph},
        )

    def reset(self) -> None:
        """Reset all controller internal state."""
        self._lateral.reset()
        self._speed.reset()

    @property
    def lateral_name(self) -> str:
        return self._lateral_name

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def _build_lateral(name: str, config) -> ControllerBase:
        if name == "mpcc_inspired":
            from controllers.mpcc_inspired_controller import MPCCInspiredController
            return MPCCInspiredController(config)
        elif name == "pure_pursuit":
            from controllers.pure_pursuit_controller import PurePursuitController
            return PurePursuitController(config)
        elif name == "stanley":
            from controllers.stanley_controller import StanleyController
            return StanleyController(config)
        else:
            from controllers.mpcc_inspired_controller import MPCCInspiredController
            return MPCCInspiredController(config)
