"""
State estimation — aggregates vehicle data into a single EgoState.

Currently just wraps SensorBundle data.  A Kalman filter or
complementary filter can be added here later without touching
the rest of the code.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

from beamng_interface.sensors import SensorBundle


@dataclass
class EgoState:
    speed_kph: float = 0.0
    position: Optional[Tuple[float, float, float]] = None
    direction: Optional[Tuple[float, float, float]] = None
    lateral_g: float = 0.0
    longitudinal_g: float = 0.0
    gear: int = 0
    rpm: float = 0.0
    damage_total: float = 0.0


class StateEstimator:
    """Produces an EgoState from raw sensor data."""

    def update(self, bundle: SensorBundle) -> EgoState:
        gf = bundle.gforces
        elec = bundle.electrics
        dmg = bundle.damage

        return EgoState(
            speed_kph=bundle.speed_kph,
            position=bundle.position,
            direction=bundle.direction,
            lateral_g=float(gf.get("gx2", 0.0) or 0.0),
            longitudinal_g=float(gf.get("gx", 0.0) or 0.0),
            gear=int(elec.get("gear_index", 0) or 0),
            rpm=float(elec.get("rpm", 0.0) or 0.0),
            damage_total=float(dmg.get("damage", 0.0) or 0.0),
        )
