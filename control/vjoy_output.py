"""
vjoy_output.py
==============
Smooth analog steering via a vJoy virtual joystick device.

This is the PREFERRED control method — vJoy gives proper analog axes
instead of on/off key presses, which results in much smoother driving.

REQUIREMENTS
------------
1. Install vJoy driver from https://github.com/jshafer817/vJoy/releases
2. Configure device #1 in vJoyConf.exe with:
   - Axis X  (steering)
   - Axis Y  (throttle)
   - Axis Z  (brake)
3. pip install pyvjoy
4. In Assetto Corsa Controls settings, assign axes from the vJoy device.

AXIS MAPPING
------------
  Axis X  centre = 0x4000  →  steering  left = 0x0001, right = 0x7FFF
  Axis Y  0x0001           →  throttle  0 = none, 0x7FFF = full
  Axis Z  0x0001           →  brake     0 = none, 0x7FFF = full

NOTE: If pyvjoy is not installed, this module disables itself gracefully
and the system falls back to DirectInput keys.
"""

from __future__ import annotations
from typing import Optional

try:
    import pyvjoy
    _VJOY_AVAILABLE = True
except ImportError:
    _VJOY_AVAILABLE = False

_VJOY_MAX   = 0x8000   # 32768
_VJOY_MID   = 0x4000   # 16384  — axis centre
_VJOY_MIN   = 0x0001   # 1


def _to_vjoy(value: float, centre: bool = False) -> int:
    """
    Map a float to a vJoy axis integer.
    If centre=True: -1 … +1 input  mapped to  1 … 32767  (centre=16384)
    If centre=False: 0 … 1 input   mapped to  1 … 32767
    """
    if centre:
        scaled = (value + 1.0) / 2.0        # -1…+1 → 0…1
    else:
        scaled = value                       # already 0…1
    raw = int(scaled * (_VJOY_MAX - _VJOY_MIN) + _VJOY_MIN)
    return max(_VJOY_MIN, min(_VJOY_MAX, raw))


class VJoyOutput:
    """Controls a vJoy device with steering, throttle, brake axes."""

    def __init__(self, device_id: int = 1) -> None:
        self._device: Optional[object] = None
        self._device_id = device_id
        self._available = False

    def open(self) -> bool:
        """Try to acquire the vJoy device. Returns True on success."""
        if not _VJOY_AVAILABLE:
            print("[vjoy] pyvjoy not installed — vJoy output disabled.")
            print("[vjoy] Install: pip install pyvjoy  (+ vJoy driver)")
            return False
        try:
            self._device = pyvjoy.VJoyDevice(self._device_id)
            self._available = True
            print(f"[vjoy] vJoy device {self._device_id} acquired.")
            return True
        except Exception as exc:
            print(f"[vjoy] Could not open vJoy device {self._device_id}: {exc}")
            return False

    def set(self, steer: float, throttle: float, brake: float) -> None:
        """
        steer    : -1 (left) … +1 (right)
        throttle : 0 … 1
        brake    : 0 … 1
        """
        if not self._available or self._device is None:
            return
        try:
            self._device.data.wAxisX = _to_vjoy(steer, centre=True)
            self._device.data.wAxisY = _to_vjoy(throttle, centre=False)
            self._device.data.wAxisZ = _to_vjoy(brake, centre=False)
            self._device.update()
        except Exception as exc:
            print(f"[vjoy] Update error: {exc}")

    def reset(self) -> None:
        """Centre all axes."""
        self.set(0.0, 0.0, 0.0)

    def close(self) -> None:
        if self._available:
            self.reset()
        self._available = False

    @property
    def available(self) -> bool:
        return self._available
