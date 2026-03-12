"""
desktop_app/ui/main_window.py — Main window: left sidebar + stacked pages.
Simple: compact sidebar, no toolbar clutter.
"""
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel,
    QFrame, QStatusBar
)
from PySide6.QtCore import Qt, QSize
from ui.styles import DARK_STYLESHEET, COLORS
from pages.dashboard import DashboardPage
from pages.normal_wheel_page import NormalWheelPage
from pages.tuning_page import TuningPage
from pages.calibration_page import CalibrationPage
from pages.tests_diagnostics_page import TestsDiagnosticsPage
from pages.beamng_ai_page import BeamNGAIPage
from pages.profiles_page import ProfilesPage
from pages.settings_page import SettingsPage
from pages.logs_page import LogsPage


# (display label, page key)  — None = thin separator
NAV = [
    ("Dashboard",           "dashboard"),
    ("Normal Wheel Mode",   "normal_wheel"),
    ("Tuning",              "tuning"),
    ("Calibration",         "calibration"),
    ("Tests & Diagnostics", "tests_diag"),
    None,
    ("BeamNG.tech AI Mode", "beamng_ai"),
    None,
    ("Profiles",            "profiles"),
    ("Settings",            "settings"),
    ("Logs",                "logs"),
]


class MainWindow(QMainWindow):
    def __init__(self, serial, config, logger, safety, telemetry,
                 beamng_manager, profiles):
        super().__init__()
        self._serial = serial
        self._config = config
        self._log = logger
        self._safety = safety
        self._telemetry = telemetry
        self._beamng_manager = beamng_manager
        self._profiles = profiles

        self.setWindowTitle("SelfDriveBeamNGTech")
        self.setMinimumSize(960, 620)
        self.resize(1200, 760)
        self.setStyleSheet(DARK_STYLESHEET)
        self._build()
        self._connect_signals()
        self._nav.setCurrentRow(0)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Sidebar
        h.addWidget(self._build_sidebar())

        # Divider
        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f"background:{COLORS['border']};")
        h.addWidget(div)

        # Pages
        self._stack = QStackedWidget()
        h.addWidget(self._stack, 1)

        kw = dict(serial=self._serial, config=self._config, logger=self._log,
                  safety=self._safety, telemetry=self._telemetry)
        self._pages = {
            "dashboard":    DashboardPage(**kw, beamng_manager=self._beamng_manager, profiles=self._profiles),
            "normal_wheel": NormalWheelPage(**kw),
            "tuning":       TuningPage(**kw),
            "calibration":  CalibrationPage(**kw),
            "tests_diag":   TestsDiagnosticsPage(**kw),
            "beamng_ai":    BeamNGAIPage(**kw, beamng_manager=self._beamng_manager),
            "profiles":     ProfilesPage(**kw, profiles=self._profiles),
            "settings":     SettingsPage(**kw),
            "logs":         LogsPage(**kw),
        }
        self._page_idx = {}
        for key, page in self._pages.items():
            self._page_idx[key] = self._stack.addWidget(page)

        # Status bar
        sb = QStatusBar()
        sb.setFixedHeight(24)
        sb.setStyleSheet(
            f"QStatusBar{{background:{COLORS['bg_panel']};"
            f"color:{COLORS['text_secondary']};"
            f"border-top:1px solid {COLORS['border']};"
            f"font-size:11px;padding:0 8px;}}"
        )
        self.setStatusBar(sb)
        self._s_serial = QLabel("Serial: —")
        self._s_mode   = QLabel("Mode: —")
        self._s_angle  = QLabel("Angle: —")
        for w in [self._s_serial, self._s_mode, self._s_angle]:
            sb.addWidget(w)

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(186)
        sb.setStyleSheet(f"background:{COLORS['bg_panel']};")
        v = QVBoxLayout(sb)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # App name
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"background:{COLORS['bg_dark']};"
            f"border-bottom:1px solid {COLORS['border']};"
        )
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(0)
        a = QLabel("SelfDrive")
        a.setStyleSheet(f"color:{COLORS['text_primary']};font-size:15px;font-weight:700;")
        b = QLabel("BeamNG Wheel")
        b.setStyleSheet(f"color:{COLORS['text_dim']};font-size:10px;")
        hl.addWidget(a)
        hl.addWidget(b)
        v.addWidget(hdr)

        # Nav list
        self._nav = QListWidget()
        self._nav.setObjectName("nav_list")
        self._nav.setSpacing(0)
        self._nav_row_to_key = {}
        nav_row = 0

        for item in NAV:
            if item is None:
                sep = QListWidgetItem()
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                sep.setSizeHint(QSize(186, 8))
                self._nav.addItem(sep)
                sep_w = QFrame()
                sep_w.setFixedHeight(1)
                sep_w.setStyleSheet(f"background:{COLORS['border']};")
                self._nav.setItemWidget(sep, sep_w)
                nav_row += 1
                continue
            label, key = item
            li = QListWidgetItem(f"  {label}")
            li.setSizeHint(QSize(186, 36))
            self._nav.addItem(li)
            self._nav_row_to_key[nav_row] = key
            nav_row += 1

        self._nav.currentRowChanged.connect(self._on_nav)
        v.addWidget(self._nav, 1)

        ver = QLabel("v1.0.0")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setFixedHeight(24)
        ver.setStyleSheet(
            f"color:{COLORS['text_dim']};font-size:10px;"
            f"border-top:1px solid {COLORS['border']};"
        )
        v.addWidget(ver)
        return sb

    def _connect_signals(self):
        self._serial.connected.connect(self._update_status)
        self._serial.disconnected.connect(self._update_status)
        self._serial.telem_received.connect(self._update_status)
        self._safety.safety_estop.connect(
            lambda r: self._s_mode.setStyleSheet(f"color:{COLORS['accent_red']};font-weight:700;")
        )
        self._log.log_message.connect(self._pages["logs"].append_log)

    def _on_nav(self, row):
        key = self._nav_row_to_key.get(row)
        if key and key in self._page_idx:
            self._stack.setCurrentIndex(self._page_idx[key])

    def navigate_to(self, page_key: str):
        for row, key in self._nav_row_to_key.items():
            if key == page_key:
                self._nav.setCurrentRow(row)
                return

    def refresh_dynamic(self):
        page = self._stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()
        self._update_status()

    def _update_status(self):
        if self._serial.is_connected:
            self._s_serial.setText(f"Serial: OK")
            self._s_serial.setStyleSheet(f"color:{COLORS['accent_green']};")
        else:
            self._s_serial.setText("Serial: —")
            self._s_serial.setStyleSheet(f"color:{COLORS['text_dim']};")
        self._s_mode.setText(f"Mode: {self._serial.device_mode if self._serial.is_connected else '—'}")
        t = self._telemetry.latest
        if t:
            self._s_angle.setText(f"Angle: {t.angle:.1f}°")

    def closeEvent(self, event):
        self._serial.disconnect()
        self._beamng_manager.disconnect()
        self._safety.stop_watchdog()
        event.accept()
