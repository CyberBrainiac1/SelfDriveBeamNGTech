"""
desktop_app/ui/main_window.py — Main application window with left sidebar navigation.
"""
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel,
    QFrame, QSizePolicy, QStatusBar
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon

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


# Navigation items: (display_name, icon_text, page_key)
NAV_ITEMS = [
    ("Dashboard",           "⬡",  "dashboard"),
    ("Normal Wheel Mode",   "🎮",  "normal_wheel"),
    ("Tuning",              "⚙",  "tuning"),
    ("Calibration",         "✦",  "calibration"),
    ("Tests & Diagnostics", "🔬",  "tests_diag"),
    None,  # separator
    ("BeamNG.tech AI Mode", "🤖",  "beamng_ai"),
    None,  # separator
    ("Profiles",            "📁",  "profiles"),
    ("Settings",            "☰",  "settings"),
    ("Logs",                "📋",  "logs"),
]


class MainWindow(QMainWindow):
    """
    Main application window.
    Left sidebar for navigation, right stacked widget for page content.
    """

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

        self.setWindowTitle("SelfDriveBeamNGTech — Wheel Control System")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)
        self.setStyleSheet(DARK_STYLESHEET)

        self._build_ui()
        self._connect_signals()
        self._update_status_bar()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Sidebar ----
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        # ---- Vertical divider ----
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']};")
        root_layout.addWidget(divider)

        # ---- Page area ----
        self._stack = QStackedWidget()
        self._stack.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._stack, 1)

        # ---- Build pages ----
        page_args = dict(
            serial=self._serial,
            config=self._config,
            logger=self._log,
            safety=self._safety,
            telemetry=self._telemetry,
        )
        self._pages = {
            "dashboard":    DashboardPage(**page_args, beamng_manager=self._beamng_manager, profiles=self._profiles),
            "normal_wheel": NormalWheelPage(**page_args),
            "tuning":       TuningPage(**page_args),
            "calibration":  CalibrationPage(**page_args),
            "tests_diag":   TestsDiagnosticsPage(**page_args),
            "beamng_ai":    BeamNGAIPage(**page_args, beamng_manager=self._beamng_manager),
            "profiles":     ProfilesPage(**page_args, profiles=self._profiles),
            "settings":     SettingsPage(**page_args),
            "logs":         LogsPage(**page_args),
        }

        self._page_index = {}
        for key, page in self._pages.items():
            idx = self._stack.addWidget(page)
            self._page_index[key] = idx

        # ---- Status bar ----
        self._status_bar = QStatusBar()
        self._status_bar.setFixedHeight(28)
        self._status_bar.setStyleSheet(
            f"QStatusBar {{ background-color: {COLORS['bg_panel']}; "
            f"color: {COLORS['text_secondary']}; "
            f"border-top: 1px solid {COLORS['border']}; "
            f"font-size: 11px; padding: 0 8px; }}"
        )
        self.setStatusBar(self._status_bar)

        self._status_serial = QLabel("Serial: Disconnected")
        self._status_mode   = QLabel("Mode: IDLE")
        self._status_angle  = QLabel("Angle: 0.0°")
        self._status_bar.addWidget(self._status_serial)
        self._status_bar.addWidget(self._make_sep())
        self._status_bar.addWidget(self._status_mode)
        self._status_bar.addWidget(self._make_sep())
        self._status_bar.addWidget(self._status_angle)

        # Navigate to dashboard by default
        self._nav_list.setCurrentRow(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_panel']};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App title
        title_frame = QFrame()
        title_frame.setFixedHeight(56)
        title_frame.setStyleSheet(
            f"background-color: {COLORS['bg_dark']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(16, 12, 16, 12)
        title_layout.setSpacing(0)

        app_name = QLabel("SelfDrive")
        app_name.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700;"
        )
        sub_name = QLabel("BeamNG Wheel System")
        sub_name.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px;"
        )
        title_layout.addWidget(app_name)
        title_layout.addWidget(sub_name)
        layout.addWidget(title_frame)

        # Navigation list
        self._nav_list = QListWidget()
        self._nav_list.setObjectName("nav_list")
        self._nav_list.setSpacing(0)
        self._nav_list.setIconSize(QSize(18, 18))

        self._nav_page_keys = []
        nav_row = 0
        self._nav_row_to_key = {}

        for item in NAV_ITEMS:
            if item is None:
                # Separator
                sep = QListWidgetItem()
                sep.setFlags(Qt.ItemFlag.NoItemFlags)
                sep.setSizeHint(QSize(200, 10))
                sep.setBackground(Qt.GlobalColor.transparent)
                sep_widget = QFrame()
                sep_widget.setFixedHeight(1)
                sep_widget.setStyleSheet(f"background-color: {COLORS['border']};")
                self._nav_list.addItem(sep)
                self._nav_list.setItemWidget(sep, sep_widget)
                nav_row += 1
                continue

            display, icon, key = item
            list_item = QListWidgetItem(f"  {icon}  {display}")
            list_item.setSizeHint(QSize(200, 38))
            self._nav_list.addItem(list_item)
            self._nav_row_to_key[nav_row] = key
            nav_row += 1

        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self._nav_list, 1)

        # Version label at bottom
        ver_label = QLabel("v1.0.0")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setFixedHeight(28)
        ver_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; "
            f"border-top: 1px solid {COLORS['border']};"
        )
        layout.addWidget(ver_label)

        return sidebar

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(14)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        return sep

    def _connect_signals(self):
        self._serial.connected.connect(self._on_serial_connected)
        self._serial.disconnected.connect(self._on_serial_disconnected)
        self._serial.telem_received.connect(self._update_status_bar)
        self._safety.safety_estop.connect(self._on_estop)

        # Connect logger to logs page
        self._log.log_message.connect(self._pages["logs"].append_log)

    def _on_nav_changed(self, row: int):
        key = self._nav_row_to_key.get(row)
        if key and key in self._page_index:
            self._stack.setCurrentIndex(self._page_index[key])

    def navigate_to(self, page_key: str):
        """Programmatically navigate to a page by key."""
        # Find the nav row for this key
        for row, key in self._nav_row_to_key.items():
            if key == page_key:
                self._nav_list.setCurrentRow(row)
                return

    def refresh_dynamic(self):
        """Called by app.py timer at 10 Hz to update live page data."""
        current_idx = self._stack.currentIndex()
        current_page = self._stack.currentWidget()
        if hasattr(current_page, "refresh"):
            current_page.refresh()
        self._update_status_bar()

    def _update_status_bar(self):
        if self._serial.is_connected:
            self._status_serial.setText(f"Serial: Connected")
            self._status_serial.setStyleSheet(f"color: {COLORS['accent_green']};")
        else:
            self._status_serial.setText("Serial: Disconnected")
            self._status_serial.setStyleSheet(f"color: {COLORS['text_dim']};")

        mode = self._serial.device_mode if self._serial.is_connected else "IDLE"
        self._status_mode.setText(f"Mode: {mode}")

        telem = self._telemetry.latest
        if telem:
            self._status_angle.setText(f"Angle: {telem.angle:.1f}°")

    def _on_serial_connected(self, port: str):
        self._update_status_bar()

    def _on_serial_disconnected(self):
        self._update_status_bar()

    def _on_estop(self, reason: str):
        self._status_mode.setText("ESTOP!")
        self._status_mode.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: 700;")

    def closeEvent(self, event):
        """Clean shutdown."""
        self._serial.disconnect()
        self._beamng_manager.disconnect()
        self._safety.stop_watchdog()
        event.accept()
