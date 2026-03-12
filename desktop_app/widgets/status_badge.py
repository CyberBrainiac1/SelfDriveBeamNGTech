"""
desktop_app/widgets/status_badge.py
Colored pill-shaped inline status labels.
"""
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from ui.styles import COLORS


_PRESETS = {
    "ok":       (COLORS["accent_green"],  "#0a1f0a"),
    "warn":     (COLORS["accent_yellow"], "#1f1800"),
    "error":    (COLORS["accent_red"],    "#1f0808"),
    "inactive": (COLORS["text_dim"],      "#202020"),
    "active":   (COLORS["accent_blue"],   "#0a1428"),
    "estop":    ("#ff4444",               "#1a0000"),
}


class StatusBadge(QLabel):
    """
    Small colored badge label.
    Usage: badge.set_state("ok", "Connected")
           badge.set_state("error", "FAULT")
    """
    def __init__(self, text: str = "—", state: str = "inactive", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply(state, text)

    def set_state(self, state: str, text: str = None):
        self._apply(state, text or self.text())

    def set_ok(self, text: str = "OK"):        self._apply("ok",       text)
    def set_warn(self, text: str = "WARN"):    self._apply("warn",     text)
    def set_error(self, text: str = "ERR"):    self._apply("error",    text)
    def set_inactive(self, text: str = "—"):   self._apply("inactive", text)
    def set_active(self, text: str = "ACTIVE"):self._apply("active",   text)
    def set_estop(self, text: str = "ESTOP"):  self._apply("estop",    text)

    def _apply(self, state: str, text: str):
        fg, bg = _presets(state)
        self.setText(text)
        self.setStyleSheet(
            f"color: {fg}; background: {bg}; border: 1px solid {fg}; "
            f"border-radius: 3px; padding: 1px 6px; "
            f"font-size: 11px; font-weight: 600; font-family: Consolas;"
        )


def _presets(state: str):
    return _PRESETS.get(state, _PRESETS["inactive"])
