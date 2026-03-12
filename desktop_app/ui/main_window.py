"""
desktop_app/ui/main_window.py
Main application window: compact sidebar + persistent telemetry strip + stacked pages.
Engineering/sim-racing dashboard aesthetic.

The sidebar is split into two clearly labelled sections:
  WHEEL CONTROLLER — hardware-facing pages (wheel setup, tuning, calibration, tests)
  AI / BEAMNG      — autonomous driving pages (BeamNG.tech AI Mode)
  SYSTEM           — app management pages (profiles, settings, logs)
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel,
    QFrame, QStatusBar, QProgressBar
)
from PySide6.QtCore import Qt, QSize, QTimer
from ui.styles import DARK_STYLESHEET, COLORS
from widgets.status_badge import StatusBadge

from pages.dashboard            import DashboardPage
from pages.normal_wheel_page    import NormalWheelPage
from pages.tuning_page          import TuningPage
from pages.calibration_page     import CalibrationPage
from pages.tests_diagnostics_page import TestsDiagnosticsPage
from pages.beamng_ai_page       import BeamNGAIPage
from pages.profiles_page        import ProfilesPage
from pages.settings_page        import SettingsPage
from pages.logs_page            import LogsPage


# NAV_ITEMS entries:
#   (label, page_key) — navigable page
#   None              — thin separator line
#   str               — non-clickable section header label
NAV_ITEMS = [
    "WHEEL CONTROLLER",
    ("Dashboard",           "dashboard"),
    ("Normal Wheel Mode",   "normal_wheel"),
    ("Tuning",              "tuning"),
    ("Calibration",         "calibration"),
    ("Tests & Diagnostics", "tests_diag"),
    "AI / BEAMNG",
    ("BeamNG.tech AI Mode", "beamng_ai"),
    "SYSTEM",
    ("Profiles",            "profiles"),
    ("Settings",            "settings"),
    ("Logs",                "logs"),
]


class MainWindow(QMainWindow):
    def __init__(self, serial, config, logger, safety, telemetry,
                 beamng_manager, profiles):
        super().__init__()
        self._serial         = serial
        self._config         = config
        self._log            = logger
        self._safety         = safety
        self._telemetry      = telemetry
        self._beamng_manager = beamng_manager
        self._profiles       = profiles

        self.setWindowTitle("SelfDriveBeamNGTech")
        self.setMinimumSize(1000, 640)
        self.resize(1280, 800)
        self.setStyleSheet(DARK_STYLESHEET)
        self._build()
        self._connect_signals()

        # Refresh timer (active page periodic update)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)   # 10 Hz UI refresh
        self._refresh_timer.timeout.connect(self._tick)
        self._refresh_timer.start()

        self._nav.setCurrentRow(0)

    # ─── Build ────────────────────────────────────────────────────

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Sidebar
        h.addWidget(self._build_sidebar())

        # Right side: telemetry strip + pages
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self._build_telem_strip())

        # Thin separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{COLORS['border']};")
        rv.addWidget(sep)

        # Page stack
        self._stack = QStackedWidget()
        rv.addWidget(self._stack, 1)
        h.addWidget(right, 1)

        # Build pages
        kw = dict(serial=self._serial, config=self._config, logger=self._log,
                  safety=self._safety, telemetry=self._telemetry)
        self._pages = {
            "dashboard":    DashboardPage(**kw, beamng_manager=self._beamng_manager,
                                          profiles=self._profiles),
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
        self._build_status_bar()

    # ─── Sidebar ──────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(176)
        sb.setStyleSheet(
            f"background:{COLORS['bg_panel']};"
            f"border-right:1px solid {COLORS['border']};"
        )
        v = QVBoxLayout(sb)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # App header
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            f"background:{COLORS['bg_dark']};"
            f"border-bottom:2px solid {COLORS['accent_blue']};"
        )
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(0)
        a = QLabel("SelfDrive")
        a.setStyleSheet(
            f"color:{COLORS['text_primary']};font-size:14px;font-weight:700;"
            f"letter-spacing:0.5px;"
        )
        b = QLabel("BeamNG Wheel System")
        b.setStyleSheet(f"color:{COLORS['text_dim']};font-size:9px;letter-spacing:0.5px;")
        hl.addWidget(a)
        hl.addWidget(b)
        v.addWidget(hdr)

        # Nav list
        self._nav = QListWidget()
        self._nav.setObjectName("nav_list")
        self._nav_row_to_key: dict = {}
        nav_row = 0

        for item in NAV_ITEMS:
            if item is None:
                sep_item = QListWidgetItem()
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
                sep_item.setSizeHint(QSize(176, 1))
                sep_item.setBackground(Qt.GlobalColor.transparent)
                self._nav.addItem(sep_item)
                sep_w = QFrame()
                sep_w.setFixedHeight(1)
                sep_w.setStyleSheet(f"background:{COLORS['border']};")
                self._nav.setItemWidget(sep_item, sep_w)
                nav_row += 1
                continue

            label, key = item
            # Indent BeamNG.tech entry for visual grouping
            prefix = "    " if key == "beamng_ai" else "  "
            li = QListWidgetItem(f"{prefix}{label}")
            li.setSizeHint(QSize(176, 32))
            self._nav.addItem(li)
            self._nav_row_to_key[nav_row] = key
            nav_row += 1

        self._nav.currentRowChanged.connect(self._on_nav)
        v.addWidget(self._nav, 1)

        # Section labels in nav (visual hints)
        # Footer: version
        footer = QLabel("v2.0.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFixedHeight(22)
        footer.setStyleSheet(
            f"color:{COLORS['text_dim']};font-size:9px;"
            f"border-top:1px solid {COLORS['border']};"
            f"letter-spacing:0.5px;"
        )
        v.addWidget(footer)
        return sb

    # ─── Telemetry strip ──────────────────────────────────────────

    def _build_telem_strip(self) -> QFrame:
        """Persistent horizontal strip always visible above all pages."""
        strip = QFrame()
        strip.setFixedHeight(38)
        strip.setStyleSheet(
            f"background:{COLORS['bg_panel']};"
            f"border-bottom:1px solid {COLORS['border']};"
        )
        h = QHBoxLayout(strip)
        h.setContentsMargins(12, 4, 12, 4)
        h.setSpacing(14)

        def cell(label, attr, color=None):
            col = QHBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color:{COLORS['text_dim']};font-size:9px;"
                f"font-weight:700;letter-spacing:1px;"
            )
            val = QLabel("—")
            val.setStyleSheet(
                f"color:{color or COLORS['text_primary']};"
                f"font-size:13px;font-weight:700;font-family:Consolas;"
                f"min-width:56px;"
            )
            col.addWidget(lbl)
            col.addWidget(val)
            h.addLayout(col)
            setattr(self, attr, val)

        cell("ANGLE",  "_ts_angle",  COLORS["accent_blue"])
        cell("TARGET", "_ts_target", COLORS["accent_green"])
        cell("MOTOR",  "_ts_motor",  COLORS["accent_yellow"])
        cell("VEL",    "_ts_vel",    COLORS["text_secondary"])
        cell("ENC",    "_ts_enc",    COLORS["text_secondary"])

        # Thin divider
        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f"background:{COLORS['border']};")
        h.addWidget(div)

        # Mode badge
        self._ts_mode = StatusBadge("IDLE", "inactive")
        h.addWidget(self._ts_mode)

        # Fault badge
        self._ts_fault = StatusBadge("OK", "ok")
        h.addWidget(self._ts_fault)

        # Motor bar
        self._ts_motor_bar = QProgressBar()
        self._ts_motor_bar.setRange(0, 255)
        self._ts_motor_bar.setValue(0)
        self._ts_motor_bar.setFixedWidth(70)
        self._ts_motor_bar.setFixedHeight(10)
        self._ts_motor_bar.setTextVisible(False)
        h.addWidget(self._ts_motor_bar)

        h.addStretch()

        # Serial status
        self._ts_serial = StatusBadge("No Device", "inactive")
        h.addWidget(self._ts_serial)

        return strip

    # ─── Status bar ───────────────────────────────────────────────

    def _build_status_bar(self):
        sb = QStatusBar()
        sb.setFixedHeight(20)
        sb.setStyleSheet(
            f"QStatusBar{{background:{COLORS['bg_dark']};"
            f"color:{COLORS['text_dim']};font-size:10px;"
            f"border-top:1px solid {COLORS['border']};padding:0 8px;}}"
        )
        self.setStatusBar(sb)
        self._sb_fw = QLabel("FW: —")
        self._sb_profile = QLabel("Profile: —")
        sb.addWidget(self._sb_fw)
        sb.addWidget(QLabel(" | "))
        sb.addWidget(self._sb_profile)

    # ─── Signals ──────────────────────────────────────────────────

    def _connect_signals(self):
        self._serial.connected.connect(self._on_connected)
        self._serial.disconnected.connect(self._on_disconnected)
        self._serial.telem_received.connect(self._on_telem)
        self._serial.boot_received.connect(self._on_boot)
        self._safety.safety_estop.connect(self._on_estop)
        self._log.log_message.connect(self._pages["logs"].append_log)

    def _on_connected(self):
        self._ts_serial.set_ok("Connected")

    def _on_disconnected(self):
        self._ts_serial.set_inactive("No Device")
        self._ts_mode.set_inactive("—")
        self._ts_fault.set_ok("OK")
        self._ts_angle.setText("—")
        self._ts_target.setText("—")
        self._ts_motor.setText("—")

    def _on_boot(self, obj):
        ver = obj.get("version", "—")
        self._sb_fw.setText(f"FW: {ver}")

    def _on_telem(self, obj):
        angle  = obj.get("angle",  0.0)
        target = obj.get("target", 0.0)
        motor  = obj.get("motor",  0)
        vel    = obj.get("vel",    0.0)
        enc    = obj.get("enc",    0)
        fault  = obj.get("fault",  0)
        mode   = obj.get("mode",   "—")
        profile= obj.get("profile", "")

        self._ts_angle.setText(f"{angle:.1f}°")
        self._ts_target.setText(f"{target:.1f}°")
        self._ts_motor.setText(str(motor))
        self._ts_vel.setText(f"{vel:.1f}")
        self._ts_enc.setText(str(enc))
        self._ts_motor_bar.setValue(abs(motor))

        if profile:
            self._sb_profile.setText(f"Profile: {profile}")

        mode_map = {
            "IDLE": "inactive", "NORMAL_HID": "ok",
            "ANGLE_TRACK": "active", "ASSIST": "active",
            "ESTOP": "estop", "CALIBRATION": "warn",
        }
        self._ts_mode.set_state(mode_map.get(mode, "inactive"), mode)

        if fault:
            self._ts_fault.set_error(f"0x{fault:02X}")
        else:
            self._ts_fault.set_ok("OK")

    def _on_estop(self, reason: str):
        self._ts_mode.set_estop("ESTOP")
        self._ts_fault.set_error("ESTOP")

    # ─── Nav ──────────────────────────────────────────────────────

    def _on_nav(self, row: int):
        key = self._nav_row_to_key.get(row)
        if key and key in self._page_idx:
            self._stack.setCurrentIndex(self._page_idx[key])

    def navigate_to(self, page_key: str):
        for row, key in self._nav_row_to_key.items():
            if key == page_key:
                self._nav.setCurrentRow(row)
                return

    # ─── Tick ─────────────────────────────────────────────────────

    def _tick(self):
        page = self._stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    # ─── Close ────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._refresh_timer.stop()
        self._serial.disconnect()
        self._beamng_manager.disconnect()
        self._safety.stop_watchdog()
        event.accept()
