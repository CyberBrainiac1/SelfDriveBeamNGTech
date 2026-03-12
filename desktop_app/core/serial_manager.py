"""
desktop_app/core/serial_manager.py — Serial communication with the wheel controller.
Runs a background thread to read telemetry and dispatch commands.
"""
import json
import threading
import time
from typing import Optional, Callable
import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal


class SerialManager(QObject):
    """
    Manages the serial connection to the Arduino wheel controller.

    Signals:
        connected(port)    — emitted on successful connection
        disconnected()     — emitted on disconnect
        raw_line(str)      — every line received from device
        telem_received()   — new telemetry frame pushed to buffer
        error(str)         — serial error message
    """
    connected = Signal(str)
    disconnected = Signal()
    raw_line = Signal(str)
    telem_received = Signal()
    error = Signal(str)

    def __init__(self, telemetry, logger):
        super().__init__()
        self._telem = telemetry
        self._log = logger
        self._port: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._fw_version: str = "unknown"
        self._device_mode: str = "IDLE"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def list_ports() -> list:
        """Return list of available COM port names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port: str, baud: int = 115200) -> bool:
        """Open serial connection to wheel controller."""
        if self.is_connected:
            self.disconnect()
        try:
            s = serial.Serial(port, baud, timeout=0.1)
            with self._lock:
                self._port = s
            self._running = True
            self._thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._thread.start()
            self._log.info(f"Serial connected: {port} @ {baud}")
            self.connected.emit(port)
            return True
        except serial.SerialException as e:
            self._log.error(f"Serial connect failed: {e}")
            self.error.emit(str(e))
            return False

    def disconnect(self):
        """Close serial connection gracefully."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        with self._lock:
            if self._port and self._port.is_open:
                try:
                    self._port.close()
                except Exception:
                    pass
            self._port = None
        self._log.info("Serial disconnected")
        self.disconnected.emit()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._port is not None and self._port.is_open

    @property
    def fw_version(self) -> str:
        return self._fw_version

    @property
    def device_mode(self) -> str:
        return self._device_mode

    def send_command(self, cmd_dict: dict) -> bool:
        """Serialize dict to JSON and send as a newline-terminated string."""
        if not self.is_connected:
            return False
        try:
            line = json.dumps(cmd_dict, separators=(",", ":")) + "\n"
            with self._lock:
                self._port.write(line.encode("ascii"))
            return True
        except serial.SerialException as e:
            self._log.error(f"Serial write error: {e}")
            self.error.emit(str(e))
            self.disconnect()
            return False

    # Convenience command helpers
    def ping(self):
        return self.send_command({"cmd": "ping"})

    def estop(self):
        return self.send_command({"cmd": "estop"})

    def set_mode(self, mode: str):
        return self.send_command({"cmd": "set_mode", "mode": mode})

    def set_target(self, angle: float):
        return self.send_command({"cmd": "set_target", "angle": round(angle, 2)})

    def zero_encoder(self):
        return self.send_command({"cmd": "zero_encoder"})

    def set_center(self):
        return self.send_command({"cmd": "set_center"})

    def clear_faults(self):
        return self.send_command({"cmd": "clear_faults"})

    def get_version(self):
        return self.send_command({"cmd": "get_version"})

    def set_config(self, key: str, value):
        return self.send_command({"cmd": "set_config", "key": key, "value": value})

    # ------------------------------------------------------------------
    # Background reader thread
    # ------------------------------------------------------------------

    def _reader_loop(self):
        buf = b""
        while self._running:
            try:
                with self._lock:
                    port = self._port
                if port is None or not port.is_open:
                    break
                chunk = port.read(256)
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.decode("ascii", errors="replace").strip()
                        if line:
                            self.raw_line.emit(line)
                            self._dispatch_line(line)
                else:
                    time.sleep(0.005)
            except serial.SerialException as e:
                self._log.error(f"Serial read error: {e}")
                self.error.emit(str(e))
                break
            except Exception as e:
                self._log.error(f"Reader loop error: {e}")
                break

        if self._running:
            self._running = False
            with self._lock:
                self._port = None
            self.disconnected.emit()

    def _dispatch_line(self, line: str):
        """Parse incoming JSON line and route to appropriate handler."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "telem":
            self._device_mode = data.get("mode", self._device_mode)
            self._telem.push_dict(data)
            self.telem_received.emit()

        elif msg_type == "ready":
            self._fw_version = data.get("fw", "unknown")
            self._device_mode = "IDLE"
            self._log.info(f"Device ready. FW: {self._fw_version}")

        elif msg_type == "version":
            self._fw_version = data.get("fw", "unknown")

        elif msg_type == "estop":
            self._device_mode = "ESTOP"
            self._log.warning("Device ESTOP triggered")

        elif msg_type == "err":
            self._log.error(f"Device error: {data.get('msg', '')}")
