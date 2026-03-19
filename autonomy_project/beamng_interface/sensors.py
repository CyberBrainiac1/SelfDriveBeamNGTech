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

    def __init__(self, vehicle: Vehicle, bng: Optional[Any] = None) -> None:
        self._vehicle = vehicle
        self._bng = bng
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

        self._cam = self._build_camera(cc)
        self._attach_sensor(cc.name, self._cam)

        self._electrics = Electrics()
        self._attach_sensor("electrics", self._electrics)

        self._damage = Damage()
        self._attach_sensor("damage", self._damage)

        self._gforces = GForces()
        self._attach_sensor("gforces", self._gforces)

        print("[sensors] All sensors attached.")

    # ── poll ───────────────────────────────────────────────────────
    def poll(self) -> SensorBundle:
        """Read all sensors and return a SensorBundle."""
        bundle = SensorBundle()

        # Vehicle state (position, velocity, rotation)
        self._poll_vehicle_sensors()

        # Camera
        try:
            cam_data = self._cam.poll()
            if "colour" in cam_data:
                bundle.colour_image = self._to_colour_image(cam_data["colour"])
            if "depth" in cam_data:
                bundle.depth_image = self._to_depth_image(cam_data["depth"])
        except Exception as exc:
            print(f"[sensors] Camera poll error: {exc}")

        # Electrics
        try:
            bundle.electrics = dict(self._electrics) if self._electrics else {}
        except Exception as exc:
            print(f"[sensors] Electrics poll error: {exc}")

        # Damage
        try:
            bundle.damage = dict(self._damage) if self._damage else {}
        except Exception as exc:
            print(f"[sensors] Damage poll error: {exc}")

        # GForces
        try:
            bundle.gforces = dict(self._gforces) if self._gforces else {}
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

    def _build_camera(self, cc: Any) -> Camera:
        """Create a Camera object compatible with old/new BeamNGpy signatures."""
        kwargs = {
            "requested_update_time": cc.update_time_s,
            "pos": cc.pos,
            "dir": cc.direction,
            "field_of_view_y": cc.fov,
            "resolution": cc.resolution,
            "near_far_planes": cc.near_far_planes,
            "is_render_colours": cc.colour,
            "is_render_depth": cc.depth,
            "is_render_annotations": cc.annotation,
        }
        if self._bng is not None:
            try:
                return Camera(cc.name, self._bng, vehicle=self._vehicle, **kwargs)
            except TypeError:
                pass
        try:
            return Camera(cc.name, self._vehicle.vid, **kwargs)
        except TypeError:
            if self._bng is None:
                raise RuntimeError(
                    "BeamNGpy Camera constructor requires a BeamNGpy instance; "
                    "pass `bng` into SensorSuite(...)."
                )
            return Camera(cc.name, self._bng, vehicle=self._vehicle, **kwargs)

    def _attach_sensor(self, name: str, sensor: Any) -> None:
        """Attach sensor using whichever API is available."""
        if not hasattr(sensor, "attach"):
            # Newer BeamNGpy sensors like Camera self-register at construction time.
            return
        if hasattr(self._vehicle, "attach_sensor"):
            self._vehicle.attach_sensor(name, sensor)
        elif hasattr(self._vehicle, "sensors") and hasattr(self._vehicle.sensors, "attach"):
            self._vehicle.sensors.attach(name, sensor)
        else:
            sensor.attach(self._vehicle, name)

    def _poll_vehicle_sensors(self) -> None:
        """Poll using compatible API across BeamNGpy versions."""
        if hasattr(self._vehicle, "poll_sensors"):
            self._vehicle.poll_sensors()
            return
        sensors = getattr(self._vehicle, "sensors", None)
        if sensors is not None and hasattr(sensors, "poll"):
            sensors.poll()

    @staticmethod
    def _to_colour_image(value: object) -> Optional[np.ndarray]:
        """Convert BeamNG camera colour output into a BGR image or None."""
        if value is None:
            return None
        try:
            img = np.asarray(value)
        except Exception:
            return None
        if img.size == 0 or img.ndim != 3:
            return None
        if img.shape[2] == 4:
            return img[:, :, 2::-1]
        if img.shape[2] == 3:
            return img[:, :, ::-1]
        return None

    @staticmethod
    def _to_depth_image(value: object) -> Optional[np.ndarray]:
        """Convert BeamNG camera depth output into a 2D float image or None."""
        if value is None:
            return None
        try:
            depth = np.asarray(value, dtype=np.float32)
        except Exception:
            return None
        if depth.size == 0:
            return None
        if depth.ndim == 3 and depth.shape[2] == 1:
            depth = depth[:, :, 0]
        if depth.ndim != 2:
            return None
        return depth
