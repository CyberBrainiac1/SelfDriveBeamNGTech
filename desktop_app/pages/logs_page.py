"""
desktop_app/pages/logs_page.py — Application log viewer with filtering and export.
"""
import os
import time
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QTextEdit, QComboBox, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from pages.base_page import BasePage
from ui.styles import COLORS


# Color mapping for log levels
LEVEL_COLORS = {
    "DEBUG":    COLORS["text_dim"],
    "INFO":     COLORS["text_secondary"],
    "SUCCESS":  COLORS["accent_green"],
    "WARNING":  COLORS["accent_yellow"],
    "ERROR":    COLORS["accent_red"],
    "CRITICAL": COLORS["accent_red"],
}


class LogsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Logs",
            subtitle="Application log viewer with filtering",
            **kwargs
        )
        self._log_entries = []
        self._build_content()

    def _build_content(self):
        # Filter bar
        filter_group = QGroupBox("FILTERS")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Level:"))
        self._level_filter = QComboBox()
        self._level_filter.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_filter.setCurrentText("INFO")
        self._level_filter.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._level_filter)

        filter_layout.addWidget(QLabel("Contains:"))
        from PySide6.QtWidgets import QLineEdit
        self._text_filter = QLineEdit()
        self._text_filter.setPlaceholderText("Filter text...")
        self._text_filter.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._text_filter)

        self._autoscroll_cb = QCheckBox("Auto-scroll")
        self._autoscroll_cb.setChecked(True)
        filter_layout.addWidget(self._autoscroll_cb)
        filter_layout.addStretch()
        self.content_layout.addWidget(filter_group)

        # Log view
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet(
            f"font-family: Consolas; font-size: 12px; "
            f"background: {COLORS['bg_dark']}; "
            f"color: {COLORS['text_secondary']}; border: none;"
        )
        self.content_layout.addWidget(self._log_view, 1)

        # Bottom toolbar
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._log_view.clear)
        btn_export = QPushButton("Export Logs...")
        btn_export.clicked.connect(self._export_logs)
        btn_open_dir = QPushButton("Open Log Folder")
        btn_open_dir.clicked.connect(self._open_log_dir)

        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_open_dir)
        btn_layout.addStretch()
        self.content_layout.addLayout(btn_layout)

    def append_log(self, level: str, message: str):
        """Called by AppLogger signal to add a new log entry."""
        entry = {"level": level, "message": message, "time": time.time()}
        self._log_entries.append(entry)

        # Apply filter before displaying
        level_filter = self._level_filter.currentText()
        text_filter  = self._text_filter.text().lower()

        if level_filter != "ALL":
            order = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
            min_idx = order.index(level_filter) if level_filter in order else 0
            if level in order and order.index(level) < min_idx:
                return

        if text_filter and text_filter not in message.lower():
            return

        self._append_entry(level, message)

    def _append_entry(self, level: str, message: str):
        color = LEVEL_COLORS.get(level, COLORS["text_secondary"])
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)

        ts = time.strftime("%H:%M:%S")
        cursor.insertText(f"[{ts}] {level:<8} {message}\n")

        if self._autoscroll_cb.isChecked():
            self._log_view.setTextCursor(cursor)
            self._log_view.ensureCursorVisible()

    def _apply_filter(self):
        """Re-render all log entries with current filter."""
        self._log_view.clear()
        level_filter = self._level_filter.currentText()
        text_filter  = self._text_filter.text().lower()
        order = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        min_idx = order.index(level_filter) if level_filter in order else 0

        for entry in self._log_entries:
            lvl = entry["level"]
            msg = entry["message"]

            if level_filter != "ALL":
                if lvl in order and order.index(lvl) < min_idx:
                    continue

            if text_filter and text_filter not in msg.lower():
                continue

            self._append_entry(lvl, msg)

    def _export_logs(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs", f"logs_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "Text (*.txt)"
        )
        if path:
            with open(path, "w") as f:
                for entry in self._log_entries:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["time"]))
                    f.write(f"[{ts}] {entry['level']:<8} {entry['message']}\n")

    def _open_log_dir(self):
        log_dir = "output/logs"
        if os.path.exists(log_dir):
            os.startfile(os.path.abspath(log_dir))
