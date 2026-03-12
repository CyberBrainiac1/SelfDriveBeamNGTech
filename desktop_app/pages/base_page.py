"""
desktop_app/pages/base_page.py — Base class for all application pages.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from ui.styles import COLORS


class BasePage(QWidget):
    """
    Base page class. Provides a standard title bar and content area.
    Subclasses call self.content_layout to add their widgets.
    """

    def __init__(self, title: str, subtitle: str = "",
                 serial=None, config=None, logger=None,
                 safety=None, telemetry=None, **kwargs):
        super().__init__()
        self._serial = serial
        self._config = config
        self._log = logger
        self._safety = safety
        self._telemetry = telemetry

        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title bar
        title_bar = self._build_title_bar(title, subtitle)
        outer.addWidget(title_bar)

        # Content area
        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(20, 16, 20, 16)
        self.content_layout.setSpacing(12)
        outer.addWidget(content_frame, 1)

    def _build_title_bar(self, title: str, subtitle: str) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet(
            f"background-color: {COLORS['bg_panel']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("page_title")
        title_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 17px; font-weight: 600;"
        )
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("page_subtitle")
            sub_label.setStyleSheet(
                f"color: {COLORS['text_secondary']}; font-size: 11px;"
            )
            layout.addWidget(sub_label)

        return bar

    def refresh(self):
        """Override in subclass to update live values."""
        pass

    def _make_label(self, text: str, style: str = "") -> QLabel:
        lbl = QLabel(text)
        if style:
            lbl.setStyleSheet(style)
        return lbl

    def _make_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        return sep
