"""
desktop_app/pages/base_page.py — Base class for all pages.
Provides a compact title bar and a content_layout for subclasses to fill.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt
from ui.styles import COLORS


class BasePage(QWidget):
    """
    All pages inherit from this. Provides:
      - compact page title bar
      - self.content_layout  (QVBoxLayout)
      - refs to serial, config, logger, safety, telemetry
      - _sep() helper for horizontal rule
    """
    def __init__(self, title: str = "", serial=None, config=None,
                 logger=None, safety=None, telemetry=None, parent=None, **_):
        super().__init__(parent)
        self._serial   = serial
        self._config   = config
        self._log      = logger
        self._safety   = safety
        self._telemetry= telemetry

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Compact page title bar
        if title:
            bar = QFrame()
            bar.setFixedHeight(32)
            bar.setStyleSheet(
                f"background:{COLORS['bg_panel']};"
                f"border-bottom:1px solid {COLORS['border']};"
            )
            bl = QHBoxLayout(bar)
            bl.setContentsMargins(12, 0, 12, 0)
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};font-size:10px;"
                f"font-weight:700;letter-spacing:2px;"
            )
            bl.addWidget(lbl)
            bl.addStretch()
            root.addWidget(bar)

        # Content area
        content_w = QWidget()
        content_w.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(content_w)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(6)
        root.addWidget(content_w, 1)

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(
            f"background:{COLORS['border']};max-height:1px;margin:4px 0;"
        )
        return f

    def refresh(self):
        """Override in subclasses that need periodic updates."""
        pass
