"""
desktop_app/core/safety_manager.py — Safety watchdog and limit enforcement.

Responsibilities:
  - Software angle clamp enforcement
  - Emergency stop coordination
  - AI-mode safety limits
  - Watchdog timer: trigger ESTOP if no heartbeat from upper layer
"""
import threading
import time
from PySide6.QtCore import QObject, Signal


# Safety limits (can be overridden by config)
DEFAULT_MAX_ANGLE = 540.0      # degrees absolute
DEFAULT_MAX_MOTOR = 200        # 0-255
DEFAULT_MAX_AI_RATE = 180.0    # deg/s max steering rate in AI mode
WATCHDOG_TIMEOUT_S = 3.0       # seconds before safety estop


class SafetyManager(QObject):
    """
    Monitors system state and enforces safety limits.
    Call heartbeat() regularly from the main loop to keep the watchdog alive.
    """
    safety_estop = Signal(str)  # reason string
    fault_cleared = Signal()

    def __init__(self, serial_manager, logger):
        super().__init__()
        self._serial = serial_manager
        self._log = logger
        self._estop_active = False
        self._max_angle = DEFAULT_MAX_ANGLE
        self._max_motor = DEFAULT_MAX_MOTOR
        self._max_ai_rate = DEFAULT_MAX_AI_RATE
        self._ai_mode_active = False
        self._watchdog_enabled = False
        self._last_heartbeat = time.time()
        self._watchdog_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, max_angle: float = DEFAULT_MAX_ANGLE,
                  max_motor: int = DEFAULT_MAX_MOTOR,
                  max_ai_rate: float = DEFAULT_MAX_AI_RATE):
        self._max_angle = max_angle
        self._max_motor = max_motor
        self._max_ai_rate = max_ai_rate

    # ------------------------------------------------------------------
    # ESTOP
    # ------------------------------------------------------------------

    def trigger_estop(self, reason: str = "manual"):
        """Immediately halt all motor activity."""
        self._estop_active = True
        self._ai_mode_active = False
        if self._serial.is_connected:
            self._serial.estop()
        self._log.warning(f"SAFETY ESTOP: {reason}")
        self.safety_estop.emit(reason)

    def clear_estop(self):
        """Clear ESTOP and return to IDLE (requires manual confirmation)."""
        if not self._serial.is_connected:
            return
        self._estop_active = False
        self._serial.clear_faults()
        self._serial.set_mode("IDLE")
        self._log.info("ESTOP cleared, mode → IDLE")
        self.fault_cleared.emit()

    @property
    def estop_active(self) -> bool:
        return self._estop_active

    # ------------------------------------------------------------------
    # Angle / target validation
    # ------------------------------------------------------------------

    def clamp_target(self, angle: float) -> float:
        """Clamp a target angle to the configured safe range."""
        return max(-self._max_angle, min(self._max_angle, angle))

    def validate_target(self, angle: float) -> bool:
        return abs(angle) <= self._max_angle

    def validate_ai_rate(self, current_angle: float, target_angle: float,
                         dt: float) -> bool:
        """Return False if the AI is requesting an unsafe rate of change."""
        if dt <= 0:
            return True
        rate = abs(target_angle - current_angle) / dt
        return rate <= self._max_ai_rate

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def start_watchdog(self):
        """Start background watchdog thread."""
        self._watchdog_enabled = True
        self._last_heartbeat = time.time()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True
        )
        self._watchdog_thread.start()

    def stop_watchdog(self):
        self._watchdog_enabled = False

    def heartbeat(self):
        """Call this periodically to keep watchdog alive."""
        self._last_heartbeat = time.time()

    def _watchdog_loop(self):
        while self._watchdog_enabled:
            time.sleep(0.5)
            if self._ai_mode_active:
                age = time.time() - self._last_heartbeat
                if age > WATCHDOG_TIMEOUT_S:
                    self.trigger_estop(f"watchdog timeout ({age:.1f}s)")

    # ------------------------------------------------------------------
    # AI mode gate
    # ------------------------------------------------------------------

    def enter_ai_mode(self) -> bool:
        """Attempt to enter AI mode. Returns False if unsafe."""
        if self._estop_active:
            self._log.warning("Cannot enter AI mode: ESTOP active")
            return False
        if not self._serial.is_connected:
            self._log.warning("Cannot enter AI mode: serial not connected")
            return False
        self._ai_mode_active = True
        self._last_heartbeat = time.time()
        self._log.info("Safety: AI mode entered")
        return True

    def exit_ai_mode(self):
        self._ai_mode_active = False
        self._log.info("Safety: AI mode exited")

    @property
    def ai_mode_active(self) -> bool:
        return self._ai_mode_active
