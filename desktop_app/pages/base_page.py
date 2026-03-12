"""
desktop_app/pages/base_page.py — Base class for all application pages.
Simple: title label at top, then content fills the rest.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from ui.styles import COLORS


class BasePage(QWidget):
    """
    Minimal base page. Thin title bar + content area.
    Subclasses add to self.content_layout.
    """

    def __init__(self, title: str,
                 serial=None, config=None, logger=None,
                 safety=None, telemetry=None, **kwargs):
        super().__init__()
        self._serial = serial
        self._config = config
        self._log = logger
        self._safety = safety
        self._telemetry = telemetry

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Thin title strip
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"background-color: {COLORS['bg_panel']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(20, 0, 20, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 15px; font-weight: 600;"
        )
        bar_layout.addWidget(lbl)
        outer.addWidget(bar)

        # Content
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(20, 14, 20, 14)
        self.content_layout.setSpacing(10)
        outer.addLayout(self.content_layout, 1)

    def refresh(self):
        """Override to update live values."""
        pass

    def _sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px;")
        return sep
