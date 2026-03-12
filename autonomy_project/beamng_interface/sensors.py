"""
Configures and polls all sensors attached to the ego vehicle.

Sensor roster (v1):
  • Front camera  – colour + depth
  • Electrics      – speed, RPM, gear, signals, lights …
  • Damage         – collision / deformation state
  • GForces        – longitudinal / lateral acceleration
  • State          – position, rotation, velocity (vehicle.state)

More sensors (LIDAR, ultrasonic, IMU) can be added here later.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np
from beamngpy import Vehicle
from beamngpy.sensors import Camera, Damage, Electrics, GForces

from config import CFG


# ── Sensor data container ──────────────────────────────────────────
@dataclass
class SensorBundle:
    """All sensor readings for a single tick, in one place."""
    colour_image: Optional[np.ndarray] = None       # H×W×3 uint8 BGR
    depth_image: Optional[np.ndarray] = None         # H×W float32 metres
    electrics: Dict[str, Any] = field(default_factory=dict)
    damage: Dict[str, Any] = field(default_factory=dict)
    gforces: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)

    # convenience helpers
    @property
    def speed_mps(self) -> float:
        """Vehicle speed in m/s from electrics, 0 if unavailable."""
        spd = self.electrics.get("wheelspeed", 0.0)
        if spd is None:
            return 0.0
        return float(spd)

    @property
    def speed_kph(self) -> float:
        return self.speed_mps * 3.6

    @property
    def position(self) -> Optional[tuple]:
        return self.state.get("pos")

    @property
    def direction(self) -> Optional[tuple]:
        return self.state.get("dir")


# ── Sensor manager ─────────────────────────────────────────────────
class SensorSuite:
    """Attaches sensors to a vehicle and provides a unified poll()."""

    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle
        self._cam: Optional[Camera] = None
        self._electrics: Optional[Electrics] = None
        self._damage: Optional[Damage] = None
        self._gforces: Optional[GForces] = None

    # ── setup ──────────────────────────────────────────────────────
    def attach_all(self) -> None:
        """Attach the full sensor suite to the ego vehicle."""
        cc = CFG.camera
        print(f"[sensors] Attaching camera '{cc.name}' "
              f"({cc.resolution[0]}×{cc.resolution[1]}, fov={cc.fov}) …")

        self._cam = Camera(
            cc.name,
            self._vehicle.vid,
            requested_update_time=-1.0,
            pos=cc.pos,
            dir=cc.direction,
            field_of_view_y=cc.fov,
            resolution=cc.resolution,
            near_far_planes=cc.near_far_planes,
            is_render_colours=cc.colour,
            is_render_depth=cc.depth,
            is_render_annotations=cc.annotation,
        )
        self._cam.attach(self._vehicle, cc.name)

        self._electrics = Electrics()
        self._electrics.attach(self._vehicle, "electrics")

        self._damage = Damage()
        self._damage.attach(self._vehicle, "damage")

        self._gforces = GForces()
        self._gforces.attach(self._vehicle, "gforces")

        print("[sensors] All sensors attached.")

    # ── poll ───────────────────────────────────────────────────────
    def poll(self) -> SensorBundle:
        """Read all sensors and return a SensorBundle."""
        bundle = SensorBundle()

        # Vehicle state (position, velocity, rotation)
        self._vehicle.sensors.poll()

        # Camera
        try:
            cam_data = self._cam.poll()
            if "colour" in cam_data:
                img = np.array(cam_data["colour"])
                # BeamNGpy returns RGBA PIL image → convert to BGR numpy
                if img.ndim == 3 and img.shape[2] == 4:
                    img = img[:, :, :3][:, :, ::-1]  # RGBA→RGB→BGR
                elif img.ndim == 3 and img.shape[2] == 3:
                    img = img[:, :, ::-1]  # RGB→BGR
                bundle.colour_image = img
            if "depth" in cam_data:
                bundle.depth_image = np.array(cam_data["depth"], dtype=np.float32)
        except Exception as exc:
            print(f"[sensors] Camera poll error: {exc}")

        # Electrics
        try:
            elec_data = self._electrics.poll()
            bundle.electrics = dict(elec_data) if elec_data else {}
        except Exception as exc:
            print(f"[sensors] Electrics poll error: {exc}")

        # Damage
        try:
            dmg_data = self._damage.poll()
            bundle.damage = dict(dmg_data) if dmg_data else {}
        except Exception as exc:
            print(f"[sensors] Damage poll error: {exc}")

        # GForces
        try:
            gf_data = self._gforces.poll()
            bundle.gforces = dict(gf_data) if gf_data else {}
        except Exception as exc:
            print(f"[sensors] GForces poll error: {exc}")

        # Vehicle state
        try:
            state = self._vehicle.state
            bundle.state = {
                "pos": state.get("pos"),
                "dir": state.get("dir"),
                "up": state.get("up"),
                "vel": state.get("vel"),
            }
        except Exception as exc:
            print(f"[sensors] State read error: {exc}")

        return bundle
