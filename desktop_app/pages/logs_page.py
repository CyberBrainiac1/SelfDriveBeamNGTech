"""
desktop_app/pages/logs_page.py — Logs: live log viewer, level filter, export.
"""
import os
import time
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QFileDialog
from pages.base_page import BasePage
from ui.styles import COLORS

LEVEL_COLORS = {
    "DEBUG":    COLORS["text_dim"],
    "INFO":     COLORS["text_secondary"],
    "SUCCESS":  COLORS["accent_green"],
    "WARNING":  COLORS["accent_yellow"],
    "ERROR":    COLORS["accent_red"],
    "CRITICAL": COLORS["accent_red"],
}
LEVEL_ORDER = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


class LogsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Logs", **kwargs)
        self._entries = []
        self._build()

    def _build(self):
        # ── Filter bar ───────────────────────────────────────────────
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Level:"))
        self._level_cb = QComboBox()
        self._level_cb.addItems(["ALL"] + LEVEL_ORDER)
        self._level_cb.setCurrentText("INFO")
        self._level_cb.setFixedWidth(100)
        self._level_cb.currentTextChanged.connect(self._refilter)
        frow.addWidget(self._level_cb)

        frow.addWidget(QLabel("Contains:"))
        self._text_filter = QLineEdit()
        self._text_filter.setPlaceholderText("filter text...")
        self._text_filter.setFixedWidth(180)
        self._text_filter.textChanged.connect(self._refilter)
        frow.addWidget(self._text_filter)

        self._autoscroll = QCheckBox("Auto-scroll")
        self._autoscroll.setChecked(True)
        frow.addWidget(self._autoscroll)
        frow.addStretch()
        self.content_layout.addLayout(frow)

        # ── Log view ─────────────────────────────────────────────────
        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setStyleSheet(
            f"font-family:Consolas;font-size:11px;"
            f"background:{COLORS['bg_panel']};border:none;"
        )
        self.content_layout.addWidget(self._view, 1)

        # ── Buttons ───────────────────────────────────────────────────
        brow = QHBoxLayout()
        for label, fn in [("Clear", self._view.clear),
                          ("Export...", self._export),
                          ("Open Folder", self._open_folder)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            brow.addWidget(b)
        brow.addStretch()
        self.content_layout.addLayout(brow)

    def append_log(self, level: str, message: str):
        entry = {"level": level, "message": message, "time": time.time()}
        self._entries.append(entry)
        if self._passes_filter(level, message):
            self._render_entry(level, message, entry["time"])

    def _passes_filter(self, level, message):
        lf = self._level_cb.currentText()
        tf = self._text_filter.text().lower()
        if lf != "ALL":
            min_i = LEVEL_ORDER.index(lf) if lf in LEVEL_ORDER else 0
            if level in LEVEL_ORDER and LEVEL_ORDER.index(level) < min_i:
                return False
        if tf and tf not in message.lower():
            return False
        return True

    def _render_entry(self, level, message, ts):
        color = LEVEL_COLORS.get(level, COLORS["text_secondary"])
        cursor = self._view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"[{time.strftime('%H:%M:%S', time.localtime(ts))}] {level:<8} {message}\n")
        if self._autoscroll.isChecked():
            self._view.setTextCursor(cursor)
            self._view.ensureCursorVisible()

    def _refilter(self):
        self._view.clear()
        for e in self._entries:
            if self._passes_filter(e["level"], e["message"]):
                self._render_entry(e["level"], e["message"], e["time"])

    def _export(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", f"logs_{time.strftime('%Y%m%d_%H%M%S')}.txt", "Text (*.txt)")
        if path:
            with open(path, "w") as f:
                for e in self._entries:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["time"]))
                    f.write(f"[{ts}] {e['level']:<8} {e['message']}\n")

    def _open_folder(self):
        d = "output/logs"
        if os.path.exists(d):
            os.startfile(os.path.abspath(d))
