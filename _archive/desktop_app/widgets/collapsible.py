"""
desktop_app/widgets/collapsible.py
A collapsible/expandable section widget.
Click the header arrow to show/hide the content widget.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from ui.styles import COLORS


class CollapsibleSection(QWidget):
    """
    Usage:
        sec = CollapsibleSection("ADVANCED OPTIONS", collapsed=True)
        sec.content_layout.addWidget(...)
    """
    def __init__(self, title: str, collapsed: bool = False, parent=None):
        super().__init__(parent)
        self._collapsed = collapsed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header button
        self._hdr = QPushButton()
        self._hdr.setFixedHeight(26)
        self._hdr.setCheckable(True)
        self._hdr.setChecked(not collapsed)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr.setStyleSheet(
            f"QPushButton {{"
            f"  background: {COLORS['bg_panel']}; "
            f"  color: {COLORS['text_dim']}; "
            f"  border: none; border-top: 1px solid {COLORS['border']}; "
            f"  text-align: left; padding: 0 8px; "
            f"  font-size: 10px; font-weight: 700; letter-spacing: 1.2px;"
            f"}}"
            f"QPushButton:hover {{ color: {COLORS['text_secondary']}; }}"
        )
        self._set_header_text(title, not collapsed)
        self._title = title
        self._hdr.toggled.connect(self._on_toggle)
        outer.addWidget(self._hdr)

        # Content frame
        self._body = QFrame()
        self._body.setStyleSheet(
            f"background: transparent; "
            f"border-left: 2px solid {COLORS['border']}; "
            f"margin-left: 4px;"
        )
        self.content_layout = QVBoxLayout(self._body)
        self.content_layout.setContentsMargins(8, 6, 4, 6)
        self.content_layout.setSpacing(6)
        outer.addWidget(self._body)

        self._body.setVisible(not collapsed)

    def _set_header_text(self, title: str, expanded: bool):
        arrow = "▾" if expanded else "▸"
        self._hdr.setText(f"  {arrow}  {title}")

    def _on_toggle(self, checked: bool):
        self._body.setVisible(checked)
        self._set_header_text(self._title, checked)

    def set_collapsed(self, collapsed: bool):
        self._hdr.setChecked(not collapsed)
