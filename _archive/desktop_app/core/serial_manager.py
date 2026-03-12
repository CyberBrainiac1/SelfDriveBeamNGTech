"""
desktop_app/core/serial_manager.py
Handles all serial communication with the wheel controller firmware.
Matches wheel_controller.ino v2.0.0 JSON protocol (EEPROM-aware).
"""
import json
import threading
import time
from typing import Optional, List

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal


class SerialManager(QObject):
    connected      = Signal()
    disconnected   = Signal()
    telem_received = Signal(dict)
    raw_line       = Signal(str)
    config_received = Signal(dict)
    profiles_received = Signal(list)   # list of {"slot", "valid", "name?"}
    boot_received  = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self.is_connected = False
        self.device_mode  = "—"
        self.fw_version   = "—"

    # ── Connection ─────────────────────────────────────────────────

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baud: int = 115200) -> bool:
        try:
            self._port = serial.Serial(port, baud, timeout=0.05)
            time.sleep(0.1)          # let Leonardo reboot if needed
            self._running = True
            self.is_connected = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            self.connected.emit()
            return True
        except (serial.SerialException, OSError) as exc:
            self.is_connected = False
            return False

    def disconnect(self):
        self._running = False
        self.is_connected = False
        if self._port and self._port.is_open:
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None
        self.device_mode = "—"
        self.disconnected.emit()

    # ── Low-level send ─────────────────────────────────────────────

    def send_command(self, obj: dict):
        if not self.is_connected or self._port is None:
            return
        try:
            line = json.dumps(obj) + "\n"
            with self._lock:
                self._port.write(line.encode("utf-8"))
        except (serial.SerialException, OSError):
            self.disconnect()

    # ── Named commands (mirrors firmware command set) ──────────────

    def ping(self):
        self.send_command({"cmd": "ping"})

    def get_version(self):
        self.send_command({"cmd": "get_version"})

    def set_mode(self, mode: str):
        self.send_command({"cmd": "set_mode", "mode": mode})
        self.device_mode = mode

    def set_target(self, angle: float):
        self.send_command({"cmd": "set_target", "angle": round(angle, 2)})

    def zero_encoder(self):
        self.send_command({"cmd": "zero_encoder"})

    def set_center(self):
        self.send_command({"cmd": "set_center"})

    def estop(self):
        self.send_command({"cmd": "estop"})
        self.device_mode = "ESTOP"

    def clear_faults(self):
        self.send_command({"cmd": "clear_faults"})

    # ── Config (individual key) ────────────────────────────────────

    def set_config(self, key: str, value):
        self.send_command({"cmd": "set_config", "key": key, "value": value})

    def get_config(self):
        """Request full config dump from firmware."""
        self.send_command({"cmd": "get_config"})

    # ── EEPROM persistence ─────────────────────────────────────────

    def save_config(self):
        """Write active config to EEPROM."""
        self.send_command({"cmd": "save_config"})

    def load_config(self):
        """Reload config from EEPROM."""
        self.send_command({"cmd": "load_config"})

    def factory_reset(self):
        """Erase EEPROM and restore firmware defaults."""
        self.send_command({"cmd": "factory_reset"})

    # ── Profile slots ──────────────────────────────────────────────

    def save_profile(self, slot: int, name: str):
        self.send_command({"cmd": "save_profile", "slot": slot, "name": name[:15]})

    def load_profile(self, slot: int):
        self.send_command({"cmd": "load_profile", "slot": slot})

    def list_profiles(self):
        self.send_command({"cmd": "list_profiles"})

    # ── Diagnostics / test ─────────────────────────────────────────

    def motor_test(self, direction: int, pwm: int):
        """direction: +1 or -1, pwm: 0..255. Firmware must be in CALIBRATION mode."""
        self.send_command({"cmd": "motor_test", "dir": direction, "pwm": pwm})

    # ── Bulk config push (write all params at once) ────────────────

    def push_config(self, params: dict):
        """
        Send multiple config keys in sequence.
        params = {"kp": 1.8, "kd": 0.12, ...}
        """
        for key, value in params.items():
            self.set_config(key, value)

    # ── Read loop ──────────────────────────────────────────────────

    def _read_loop(self):
        buf = b""
        while self._running:
            try:
                if not self._port or not self._port.is_open:
                    break
                chunk = self._port.read(256)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line_b, buf = buf.split(b"\n", 1)
                    line = line_b.decode("utf-8", errors="replace").strip()
                    if line:
                        self.raw_line.emit(line)
                        self._parse_line(line)
            except (serial.SerialException, OSError):
                break

        self.disconnect()

    def _parse_line(self, line: str):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return

        t = obj.get("t", "")

        if t == "telem":
            self.device_mode = obj.get("mode", self.device_mode)
            self.telem_received.emit(obj)

        elif t == "config":
            self.config_received.emit(obj)

        elif t == "profiles":
            self.profiles_received.emit(obj.get("slots", []))

        elif t == "version":
            self.fw_version = obj.get("version", "—")

        elif t == "boot":
            self.fw_version = obj.get("version", "—")
            self.boot_received.emit(obj)

        elif t in ("ok", "error", "pong"):
            pass   # desktop app can subscribe to raw_line for these
