"""
desktop_app/core/telemetry.py — Thread-safe telemetry buffer.
Stores the most recent telemetry frame and a history ring buffer for charts.
"""
import threading
import time
from collections import deque
from typing import Optional, Deque, Dict, Any

HISTORY_SECONDS = 15
HISTORY_MAX = HISTORY_SECONDS * 20  # 20 Hz max telem rate


class TelemetryFrame:
    """Single telemetry snapshot from the wheel controller."""
    __slots__ = [
        "angle", "target", "motor", "mode",
        "enc", "fault", "ts_device", "ts_host"
    ]

    def __init__(self):
        self.angle: float = 0.0
        self.target: float = 0.0
        self.motor: int = 0
        self.mode: str = "IDLE"
        self.enc: int = 0
        self.fault: int = 0
        self.ts_device: int = 0
        self.ts_host: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TelemetryFrame":
        f = cls()
        f.angle = float(d.get("angle", 0.0))
        f.target = float(d.get("target", 0.0))
        f.motor = int(d.get("motor", 0))
        f.mode = str(d.get("mode", "IDLE"))
        f.enc = int(d.get("enc", 0))
        f.fault = int(d.get("fault", 0))
        f.ts_device = int(d.get("ts", 0))
        f.ts_host = time.time()
        return f

    def has_fault(self) -> bool:
        return self.fault != 0

    def fault_names(self):
        names = []
        if self.fault & 0x01: names.append("SERIAL_TIMEOUT")
        if self.fault & 0x02: names.append("ANGLE_CLAMP")
        if self.fault & 0x04: names.append("INVALID_CMD")
        if self.fault & 0x08: names.append("MOTOR_ESTOP")
        if self.fault & 0x10: names.append("ENC_NOISE")
        return names


class TelemetryBuffer:
    """
    Thread-safe buffer for telemetry data.
    latest  — most recent TelemetryFrame (or None)
    history — deque of TelemetryFrames for charting
    """

    def __init__(self, max_history: int = HISTORY_MAX):
        self._lock = threading.Lock()
        self._latest: Optional[TelemetryFrame] = None
        self._history: Deque[TelemetryFrame] = deque(maxlen=max_history)
        self._last_update: float = 0.0

    def push(self, frame: TelemetryFrame):
        with self._lock:
            self._latest = frame
            self._history.append(frame)
            self._last_update = frame.ts_host

    def push_dict(self, d: Dict[str, Any]):
        self.push(TelemetryFrame.from_dict(d))

    @property
    def latest(self) -> Optional[TelemetryFrame]:
        with self._lock:
            return self._latest

    def get_history(self) -> list:
        with self._lock:
            return list(self._history)

    def get_angle_history(self) -> tuple:
        """Returns (timestamps, angles) for chart plotting."""
        with self._lock:
            frames = list(self._history)
        if not frames:
            return [], []
        t0 = frames[0].ts_host
        ts = [f.ts_host - t0 for f in frames]
        angles = [f.angle for f in frames]
        return ts, angles

    def get_motor_history(self) -> tuple:
        with self._lock:
            frames = list(self._history)
        if not frames:
            return [], []
        t0 = frames[0].ts_host
        ts = [f.ts_host - t0 for f in frames]
        motors = [f.motor for f in frames]
        return ts, motors

    @property
    def age_seconds(self) -> float:
        """Seconds since last telemetry update."""
        if self._last_update == 0:
            return float("inf")
        return time.time() - self._last_update

    def is_stale(self, threshold: float = 3.0) -> bool:
        return self.age_seconds > threshold

    def clear(self):
        with self._lock:
            self._latest = None
            self._history.clear()
            self._last_update = 0.0
