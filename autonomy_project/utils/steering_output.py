"""
Steering output hook — sends the current steering target to an external device.

This module is the integration point for a DIY force-feedback steering wheel.
In the first version it just logs the target; once you have your hardware
ready, uncomment the serial section and point it at your microcontroller.

Usage in the control arbiter or main loop:
    from utils.steering_output import SteeringOutput
    wheel = SteeringOutput()
    wheel.send(cmd.steering)
"""

from __future__ import annotations

import time
from typing import Optional


class SteeringOutput:
    """Sends the autonomous steering target to an external device (e.g. serial)."""

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        enabled: bool = False,
    ) -> None:
        self._enabled = enabled
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._last_value: float = 0.0

        if enabled and port:
            self._open_serial(port, baudrate)

    def _open_serial(self, port: str, baudrate: int) -> None:
        """Attempt to open the serial port. Requires pyserial."""
        try:
            import serial  # type: ignore
            self._serial = serial.Serial(port, baudrate, timeout=0.01)
            print(f"[steering_output] Opened {port} @ {baudrate}")
        except ImportError:
            print("[steering_output] pyserial not installed — serial output disabled.")
            self._enabled = False
        except Exception as exc:
            print(f"[steering_output] Failed to open {port}: {exc}")
            self._enabled = False

    def send(self, steering: float) -> None:
        """
        Send steering value to the external device.

        `steering` is in [-1.0, +1.0] where -1 = full left, +1 = full right.

        Protocol (simple ASCII for now):
            "S<value>\n"  e.g. "S+0.325\n"

        Replace this with your own binary protocol if needed.
        """
        self._last_value = steering
        if not self._enabled or self._serial is None:
            return
        try:
            msg = f"S{steering:+.4f}\n"
            self._serial.write(msg.encode("ascii"))
        except Exception as exc:
            print(f"[steering_output] Write error: {exc}")

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
                print("[steering_output] Serial port closed.")
            except Exception:
                pass
            self._serial = None

    @property
    def last_value(self) -> float:
        return self._last_value
