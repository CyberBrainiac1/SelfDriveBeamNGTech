"""
desktop_app/beamng/shared_control.py — Shared control between human and AI.

Blends human wheel input and AI steering commands using a configurable
authority weight. authority=0.0 → full human, authority=1.0 → full AI.
"""
from PySide6.QtCore import QObject, Signal


class SharedControlMode(str):
    HUMAN_ONLY  = "HUMAN_ONLY"
    BLEND       = "BLEND"
    AI_ONLY     = "AI_ONLY"
    ASSIST      = "ASSIST"


class SharedControl(QObject):
    """
    Blends human steering input and AI steering targets.
    Sends the blended result to the wheel controller.
    """
    blended_target = Signal(float)    # final angle in degrees

    def __init__(self, serial_manager, safety_manager, logger):
        super().__init__()
        self._serial = serial_manager
        self._safety = safety_manager
        self._log = logger
        self._mode = SharedControlMode.HUMAN_ONLY
        self._authority: float = 0.0     # 0.0 human .. 1.0 AI
        self._human_angle: float = 0.0
        self._ai_angle: float = 0.0
        self._active = False

    def activate(self, mode: str = SharedControlMode.BLEND, authority: float = 0.5):
        self._mode = mode
        self._authority = max(0.0, min(1.0, authority))
        self._active = True
        self._log.info(f"Shared control: mode={mode}, authority={authority:.2f}")

    def deactivate(self):
        self._active = False

    def set_human_angle(self, angle: float):
        self._human_angle = angle
        if self._active:
            self._compute_and_send()

    def set_ai_angle(self, angle: float):
        self._ai_angle = angle
        if self._active:
            self._compute_and_send()

    def set_authority(self, authority: float):
        self._authority = max(0.0, min(1.0, authority))

    def _compute_and_send(self):
        if self._mode == SharedControlMode.HUMAN_ONLY:
            target = self._human_angle
        elif self._mode == SharedControlMode.AI_ONLY:
            target = self._ai_angle
        elif self._mode == SharedControlMode.ASSIST:
            # AI gives a light assist nudge
            assist_weight = self._authority * 0.3
            target = self._human_angle * (1.0 - assist_weight) + self._ai_angle * assist_weight
        else:  # BLEND
            target = (self._human_angle * (1.0 - self._authority) +
                      self._ai_angle * self._authority)

        target = self._safety.clamp_target(target)
        self.blended_target.emit(target)
        if self._serial.is_connected:
            self._serial.set_target(target)
