"""
desktop_app/pages/normal_wheel_page.py — Wheel Controller Panel (Section B).

Handles everything that talks to the physical wheel hardware: serial connection,
wheel setup parameters, PD controller gains, FFB effects, EEPROM profiles,
live telemetry charts, diagnostics, tests, and firmware build/flash.

AI / BeamNG controls live entirely on the dedicated BeamNG AI Mode page.

Layout (left-right split):
  LEFT (scrollable, 340px)  — collapsible control sections:
    ▾ CONNECTION
    ▾ WHEEL SETUP
    ▾ PD CONTROLLER
    ▾ FFB EFFECTS
    ▾ PROFILES
  RIGHT (flex)              — live panels stacked vertically:
    Wheel State strip
    Angle + Motor chart
    [Tabs] Diagnostics | Tests | Firmware
"""
import json
import os
import subprocess
import time
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QScrollArea,
    QGroupBox, QFormLayout, QTabWidget, QTextEdit, QProgressBar,
    QLineEdit, QCheckBox, QSplitter, QFrame, QListWidget,
    QListWidgetItem, QInputDialog, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from pages.base_page import BasePage
from ui.styles import COLORS
from widgets.collapsible import CollapsibleSection
from widgets.mini_chart import MiniChart
from widgets.status_badge import StatusBadge
from core.serial_manager import SerialManager


# ─────────────────────────────────────────────────────────────────────
#  Small helpers
# ─────────────────────────────────────────────────────────────────────

def _param_row(label: str, widget, tip: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    lbl = QLabel(label)
    lbl.setFixedWidth(130)
    lbl.setStyleSheet(f"color:{COLORS['text_secondary']};font-size:11px;")
    if tip:
        lbl.setToolTip(tip)
        widget.setToolTip(tip)
    row.addWidget(lbl)
    row.addWidget(widget, 1)
    return row


def _spin_d(lo, hi, val, decimals=2, step=0.01, suffix="", width=80) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(val)
    sb.setDecimals(decimals)
    sb.setSingleStep(step)
    if suffix:
        sb.setSuffix(f" {suffix}")
    sb.setFixedWidth(width)
    return sb


def _spin_i(lo, hi, val, width=80) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(val)
    sb.setFixedWidth(width)
    return sb


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{COLORS['border']};max-height:1px;margin:4px 0;")
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{COLORS['text_dim']};font-size:9px;font-weight:700;"
        f"letter-spacing:1.5px;padding:6px 0 2px 0;"
    )
    return lbl


# ─────────────────────────────────────────────────────────────────────
#  EMC Lite Plus Page
# ─────────────────────────────────────────────────────────────────────

class NormalWheelPage(BasePage):
    """
    Wheel Controller Panel — everything related to the physical steering wheel.
    Left: collapsible control sections (Connection / Setup / PD / FFB / Profiles).
    Right: live state, chart, diagnostic/test/firmware tabs.
    """

    def __init__(self, **kwargs):
        super().__init__(title="Normal Wheel Mode", **kwargs)
        self._config_cache: dict = {}
        self._profile_slots: list = []
        self._build()
        self._wire_signals()

    # ─── top-level layout ──────────────────────────────────────────

    def _build(self):
        # Override the base layout — we own the full page
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(f"QSplitter::handle{{background:{COLORS['border']};}}")

        split.addWidget(self._build_left())
        split.addWidget(self._build_right())
        split.setSizes([330, 999])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        self.content_layout.addWidget(split)

    # ─── LEFT PANEL ────────────────────────────────────────────────

    def _build_left(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{COLORS['bg_panel']};")
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        v.addWidget(self._sec_connection())
        v.addWidget(self._sec_wheel_setup())
        v.addWidget(self._sec_pd())
        v.addWidget(self._sec_ffb())
        v.addWidget(self._sec_profiles())
        v.addStretch()

        scroll.setWidget(inner)
        scroll.setFixedWidth(334)
        return scroll

    # ── Section: CONNECTION ────────────────────────────────────────

    def _sec_connection(self) -> CollapsibleSection:
        sec = CollapsibleSection("CONNECTION", collapsed=False)
        v = sec.content_layout

        # Port row
        port_row = QHBoxLayout()
        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setFixedWidth(100)
        self._refresh_ports()
        btn_r = QPushButton("↺")
        btn_r.setObjectName("btn_tool")
        btn_r.setFixedWidth(26)
        btn_r.setFixedHeight(22)
        btn_r.clicked.connect(self._refresh_ports)
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(["9600", "57600", "115200", "230400"])
        self._baud_combo.setCurrentText("115200")
        self._baud_combo.setFixedWidth(72)
        port_row.addWidget(QLabel("Port:"))
        port_row.addWidget(self._port_combo)
        port_row.addWidget(btn_r)
        port_row.addWidget(QLabel("Baud:"))
        port_row.addWidget(self._baud_combo)
        v.addLayout(port_row)

        # Connect row
        conn_row = QHBoxLayout()
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setObjectName("btn_primary")
        self._btn_connect.setFixedHeight(26)
        self._btn_connect.clicked.connect(self._toggle_connect)

        self._badge_conn = StatusBadge("Disconnected", "inactive")
        self._badge_fw   = StatusBadge("FW: —", "inactive")
        conn_row.addWidget(self._btn_connect)
        conn_row.addWidget(self._badge_conn)
        conn_row.addStretch()
        v.addLayout(conn_row)
        v.addWidget(self._badge_fw)

        # Mode buttons
        v.addWidget(_section_label("MODE"))
        mode_row1 = QHBoxLayout()
        mode_row2 = QHBoxLayout()
        for label, mode, row_h in [
            ("Idle",        "IDLE",        mode_row1),
            ("HID",         "NORMAL_HID",  mode_row1),
            ("Assist",      "ASSIST",      mode_row2),
            ("Angle Track", "ANGLE_TRACK", mode_row2),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _, m=mode: self._set_mode(m))
            row_h.addWidget(b)
        v.addLayout(mode_row1)
        v.addLayout(mode_row2)

        self._btn_estop = QPushButton("⚠  E-STOP")
        self._btn_estop.setObjectName("btn_danger")
        self._btn_estop.setFixedHeight(28)
        self._btn_estop.clicked.connect(self._do_estop)
        v.addWidget(self._btn_estop)

        return sec

    # ── Section: WHEEL SETUP ───────────────────────────────────────

    def _sec_wheel_setup(self) -> CollapsibleSection:
        sec = CollapsibleSection("WHEEL SETUP", collapsed=False)
        v = sec.content_layout

        self._sb_range    = _spin_d(90,  1080, 540, 0, 10, "°", 80)
        self._sb_cpr      = _spin_d(100, 100000, 2400, 0, 100, "", 80)
        self._sb_gear     = _spin_d(0.1, 20.0, 1.0, 2, 0.1, ":1", 80)
        self._cb_inv_enc  = QCheckBox("Invert Encoder")
        self._cb_inv_mot  = QCheckBox("Invert Motor")
        self._sb_max_mot  = _spin_i(0, 255, 200, 80)
        self._sb_slew     = _spin_d(0, 255, 20, 0, 5, "", 80)

        for lbl, w, tip in [
            ("Angle Range",   self._sb_range,   "Total rotation degrees (540 = ±270°)"),
            ("Encoder CPR",   self._sb_cpr,      "Counts per revolution (×4 quadrature)"),
            ("Gear Ratio",    self._sb_gear,     "Motor-to-shaft gear ratio"),
            ("Max Motor PWM", self._sb_max_mot,  "Absolute PWM ceiling 0-255"),
            ("Slew Rate",     self._sb_slew,     "Max PWM change per loop (0=off)"),
        ]:
            v.addLayout(_param_row(lbl, w, tip))

        v.addWidget(self._cb_inv_enc)
        v.addWidget(self._cb_inv_mot)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply Setup")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setFixedHeight(24)
        btn_apply.clicked.connect(self._apply_setup)
        btn_row.addWidget(btn_apply)
        btn_row.addStretch()
        v.addLayout(btn_row)

        return sec

    # ── Section: PD CONTROLLER ────────────────────────────────────

    def _sec_pd(self) -> CollapsibleSection:
        sec = CollapsibleSection("PD CONTROLLER", collapsed=False)
        v = sec.content_layout

        self._sb_kp   = _spin_d(0, 20,  1.8,  2, 0.05, "", 80)
        self._sb_kd   = _spin_d(0, 5,   0.12, 3, 0.01, "", 80)
        self._sb_ki   = _spin_d(0, 2,   0.0,  3, 0.005,"", 80)
        self._sb_dz   = _spin_d(0, 20,  1.5,  1, 0.5, "°", 80)

        for lbl, w, tip in [
            ("KP (Prop.)",  self._sb_kp, "Higher = faster/stiffer correction"),
            ("KD (Deriv.)", self._sb_kd, "Higher = less overshoot, more stable"),
            ("KI (Integ.)", self._sb_ki, "Use sparingly — fixes steady-state error"),
            ("Dead Zone",   self._sb_dz, "No output within this error band"),
        ]:
            v.addLayout(_param_row(lbl, w, tip))

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply PD")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setFixedHeight(24)
        btn_apply.clicked.connect(self._apply_pd)
        btn_default = QPushButton("Defaults")
        btn_default.setFixedHeight(24)
        btn_default.clicked.connect(self._default_pd)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_default)
        btn_row.addStretch()
        v.addLayout(btn_row)
        return sec

    # ── Section: FFB EFFECTS ──────────────────────────────────────

    def _sec_ffb(self) -> CollapsibleSection:
        sec = CollapsibleSection("FFB EFFECTS", collapsed=False)
        v = sec.content_layout

        self._sb_center   = _spin_d(0, 5.0,  1.0,  2, 0.05, "", 80)
        self._sb_damping  = _spin_d(0, 2.0,  0.12, 3, 0.01, "", 80)
        self._sb_friction = _spin_d(0, 1.0,  0.05, 3, 0.005,"", 80)
        self._sb_inertia  = _spin_d(0, 1.0,  0.04, 3, 0.005,"", 80)
        self._sb_smooth   = _spin_d(0, 0.95, 0.10, 2, 0.05, "", 80)

        effects = [
            ("Centering",  self._sb_center,   "Spring pull toward 0°"),
            ("Damping",    self._sb_damping,  "Velocity-proportional resistance"),
            ("Friction",   self._sb_friction, "Constant rotational resistance"),
            ("Inertia",    self._sb_inertia,  "Resists angular acceleration"),
            ("Smoothing",  self._sb_smooth,   "LP filter on motor output (0=off)"),
        ]
        for lbl, w, tip in effects:
            v.addLayout(_param_row(lbl, w, tip))

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply Effects")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setFixedHeight(24)
        btn_apply.clicked.connect(self._apply_ffb)
        btn_def = QPushButton("Defaults")
        btn_def.setFixedHeight(24)
        btn_def.clicked.connect(self._default_ffb)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_def)
        btn_row.addStretch()
        v.addLayout(btn_row)
        return sec

    # ── Section: PROFILES ─────────────────────────────────────────

    def _sec_profiles(self) -> CollapsibleSection:
        sec = CollapsibleSection("PROFILES  (EEPROM slots 0–3)", collapsed=False)
        v = sec.content_layout

        # Slot selector
        slot_row = QHBoxLayout()
        slot_row.addWidget(QLabel("Slot:"))
        self._slot_combo = QComboBox()
        self._slot_combo.setFixedWidth(40)
        self._slot_combo.addItems(["0", "1", "2", "3"])
        self._slot_name  = QLineEdit()
        self._slot_name.setPlaceholderText("Profile name (max 15 chars)")
        self._slot_name.setMaxLength(15)
        slot_row.addWidget(self._slot_combo)
        slot_row.addWidget(self._slot_name, 1)
        v.addLayout(slot_row)

        # EEPROM action buttons
        btn_row1 = QHBoxLayout()
        btn_save_slot = QPushButton("Save to Slot")
        btn_save_slot.setObjectName("btn_primary")
        btn_save_slot.setFixedHeight(24)
        btn_save_slot.clicked.connect(self._save_to_slot)
        btn_load_slot = QPushButton("Load Slot")
        btn_load_slot.setFixedHeight(24)
        btn_load_slot.clicked.connect(self._load_from_slot)
        btn_row1.addWidget(btn_save_slot)
        btn_row1.addWidget(btn_load_slot)
        v.addLayout(btn_row1)

        # EEPROM persist buttons
        btn_row2 = QHBoxLayout()
        btn_save_cfg = QPushButton("Save Config → EEPROM")
        btn_save_cfg.setFixedHeight(24)
        btn_save_cfg.setToolTip("Persist active config to EEPROM (survives power off)")
        btn_save_cfg.clicked.connect(self._save_config_eeprom)
        v.addLayout(btn_row2)
        v.addWidget(btn_save_cfg)

        btn_row3 = QHBoxLayout()
        btn_load_cfg = QPushButton("Reload from EEPROM")
        btn_load_cfg.setFixedHeight(24)
        btn_load_cfg.clicked.connect(self._load_config_eeprom)
        btn_reset = QPushButton("Factory Reset")
        btn_reset.setFixedHeight(24)
        btn_reset.setObjectName("btn_danger")
        btn_reset.clicked.connect(self._factory_reset)
        btn_row3.addWidget(btn_load_cfg)
        btn_row3.addWidget(btn_reset)
        v.addLayout(btn_row3)

        # Profile list (populated via list_profiles)
        self._profile_list = QListWidget()
        self._profile_list.setMaximumHeight(80)
        self._profile_list.setStyleSheet(
            f"font-size:11px;font-family:Consolas;background:{COLORS['bg_dark']};"
        )
        v.addWidget(self._profile_list)

        btn_refresh = QPushButton("↺ Refresh Slots")
        btn_refresh.setObjectName("btn_tool")
        btn_refresh.setFixedHeight(22)
        btn_refresh.clicked.connect(lambda: self._serial.list_profiles()
                                    if self._serial and self._serial.is_connected else None)
        v.addWidget(btn_refresh)

        # JSON file export / import
        io_row = QHBoxLayout()
        btn_export = QPushButton("Export JSON")
        btn_export.setObjectName("btn_tool")
        btn_export.setFixedHeight(22)
        btn_export.setToolTip("Save active device config to a JSON file")
        btn_export.clicked.connect(self._export_profile_json)
        btn_import = QPushButton("Import JSON")
        btn_import.setObjectName("btn_tool")
        btn_import.setFixedHeight(22)
        btn_import.setToolTip("Load config from a JSON file and push to device")
        btn_import.clicked.connect(self._import_profile_json)
        io_row.addWidget(btn_export)
        io_row.addWidget(btn_import)
        io_row.addStretch()
        v.addLayout(io_row)

        return sec

    # ─── RIGHT PANEL ───────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{COLORS['bg_dark']};")
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(6)

        # ── Wheel State strip ────────────────────────────────────
        v.addWidget(self._build_state_strip())

        # ── Charts ───────────────────────────────────────────────
        charts = QGroupBox("LIVE TELEMETRY")
        charts.setProperty("accent", "blue")
        cl = QVBoxLayout(charts)
        cl.setContentsMargins(6, 10, 6, 4)
        cl.setSpacing(4)

        self._chart_angle  = MiniChart(
            "Angle / Target", y_label="°",
            color=COLORS["accent_blue"], color2=COLORS["accent_green"],
            y_min=-270, y_max=270, height=110
        )
        self._chart_motor  = MiniChart(
            "Motor Output", y_label="pwm",
            color=COLORS["accent_yellow"],
            y_min=-260, y_max=260, height=80
        )
        cl.addWidget(self._chart_angle)
        cl.addWidget(self._chart_motor)
        v.addWidget(charts)

        # ── Tabs: Diagnostics / Tests / Firmware ─────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_diag_tab(), "Diagnostics")
        tabs.addTab(self._build_tests_tab(), "Tests")
        tabs.addTab(self._build_firmware_tab(), "Firmware")
        v.addWidget(tabs, 1)

        return w

    # ── State strip ───────────────────────────────────────────────

    def _build_state_strip(self) -> QGroupBox:
        grp = QGroupBox("WHEEL STATE")
        grp.setProperty("accent", "blue")
        h = QHBoxLayout(grp)
        h.setContentsMargins(8, 8, 8, 6)
        h.setSpacing(16)

        def stat(label):
            col = QVBoxLayout()
            col.setSpacing(1)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color:{COLORS['text_dim']};font-size:9px;font-weight:700;letter-spacing:1px;"
            )
            val = QLabel("—")
            val.setStyleSheet(
                f"color:{COLORS['text_primary']};font-size:18px;"
                f"font-weight:700;font-family:Consolas;"
            )
            col.addWidget(lbl)
            col.addWidget(val)
            h.addLayout(col)
            return val

        self._lbl_angle   = stat("ANGLE")
        self._lbl_target  = stat("TARGET")
        self._lbl_motor   = stat("MOTOR")
        self._lbl_vel     = stat("VEL°/S")
        self._lbl_enc     = stat("ENCODER")

        # Mode badge
        badge_col = QVBoxLayout()
        badge_col.setSpacing(2)
        badge_col.addWidget(QLabel("MODE"))
        self._badge_mode = StatusBadge("IDLE", "inactive")
        badge_col.addWidget(self._badge_mode)
        h.addLayout(badge_col)

        # Fault badge
        fault_col = QVBoxLayout()
        fault_col.setSpacing(2)
        fault_col.addWidget(QLabel("FAULT"))
        self._badge_fault = StatusBadge("None", "ok")
        fault_col.addWidget(self._badge_fault)
        h.addLayout(fault_col)

        # Motor bar
        bar_col = QVBoxLayout()
        bar_col.setSpacing(2)
        bar_col.addWidget(QLabel("MOTOR%"))
        self._motor_bar = QProgressBar()
        self._motor_bar.setRange(0, 255)
        self._motor_bar.setValue(0)
        self._motor_bar.setFixedWidth(90)
        self._motor_bar.setTextVisible(False)
        bar_col.addWidget(self._motor_bar)
        h.addLayout(bar_col)

        h.addStretch()
        return grp

    # ── Diagnostics tab ───────────────────────────────────────────

    def _build_diag_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        # Config readback
        grp_cfg = QGroupBox("ACTIVE CONFIG  (from device)")
        fl = QFormLayout(grp_cfg)
        fl.setContentsMargins(8, 10, 8, 6)
        fl.setSpacing(4)
        self._cfg_fields = {}
        for key in ["kp", "kd", "ki", "centering", "damping", "friction",
                    "inertia", "max_motor", "angle_range", "profile", "eeprom_ok"]:
            lbl_w = QLabel("—")
            lbl_w.setStyleSheet(
                f"font-family:Consolas;color:{COLORS['accent_cyan']};font-size:11px;"
            )
            fl.addRow(QLabel(f"{key}:"), lbl_w)
            self._cfg_fields[key] = lbl_w
        btn_get = QPushButton("↺ Read Config from Device")
        btn_get.setObjectName("btn_tool")
        btn_get.setFixedHeight(22)
        btn_get.clicked.connect(lambda: self._serial.get_config()
                                if self._serial and self._serial.is_connected else None)
        fl.addRow("", btn_get)
        v.addWidget(grp_cfg)

        # Serial log
        grp_log = QGroupBox("SERIAL LOG")
        ll = QVBoxLayout(grp_log)
        ll.setContentsMargins(6, 10, 6, 6)
        self._serial_log = QTextEdit()
        self._serial_log.setReadOnly(True)
        self._serial_log.setMaximumHeight(120)
        self._serial_log.setStyleSheet(
            f"font-family:Consolas;font-size:10px;background:{COLORS['bg_dark']};border:none;"
        )
        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("btn_tool")
        btn_clear.setFixedHeight(20)
        btn_clear.clicked.connect(self._serial_log.clear)
        ll.addWidget(self._serial_log)
        ll.addWidget(btn_clear)
        v.addWidget(grp_log, 1)

        return w

    # ── Tests tab ─────────────────────────────────────────────────

    def _build_tests_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        # Quick commands
        grp_quick = QGroupBox("QUICK COMMANDS")
        ql = QHBoxLayout(grp_quick)
        ql.setContentsMargins(8, 10, 8, 6)
        for label, fn in [
            ("Ping",        lambda: self._serial.ping()         if self._check() else None),
            ("Get Version", lambda: self._serial.get_version()  if self._check() else None),
            ("Clear Faults",lambda: self._serial.clear_faults() if self._check() else None),
            ("Get Config",  lambda: self._serial.get_config()   if self._check() else None),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.clicked.connect(fn)
            ql.addWidget(b)
        ql.addStretch()
        v.addWidget(grp_quick)

        # Sweep test
        grp_sweep = QGroupBox("SWEEP TEST")
        sl = QHBoxLayout(grp_sweep)
        sl.setContentsMargins(8, 10, 8, 6)
        sl.addWidget(QLabel("Range ±"))
        self._sweep_sb = _spin_d(10, 270, 90, 0, 10, "°", 72)
        self._sweep_bar = QProgressBar()
        self._sweep_bar.setRange(-100, 100)
        self._sweep_bar.setValue(0)
        self._sweep_bar.setFixedHeight(14)
        self._sweep_bar.setTextVisible(False)
        btn_sw_go  = QPushButton("▶ Start")
        btn_sw_go.setObjectName("btn_success")
        btn_sw_go.setFixedHeight(24)
        btn_sw_stop= QPushButton("■ Stop")
        btn_sw_stop.setFixedHeight(24)
        btn_sw_go.clicked.connect(self._start_sweep)
        btn_sw_stop.clicked.connect(self._stop_sweep)
        sl.addWidget(self._sweep_sb)
        sl.addWidget(btn_sw_go)
        sl.addWidget(btn_sw_stop)
        sl.addWidget(self._sweep_bar, 1)
        v.addWidget(grp_sweep)

        # Step test
        grp_step = QGroupBox("STEP TEST  (Angle Track)")
        stel = QHBoxLayout(grp_step)
        stel.setContentsMargins(8, 10, 8, 6)
        for deg, lbl in [(-90, "−90°"), (-45, "−45°"), (0, "0°"),
                          (45, "+45°"), (90, "+90°")]:
            b = QPushButton(lbl)
            b.setFixedHeight(24)
            b.setFixedWidth(52)
            b.clicked.connect(lambda _, d=deg: self._step_to(d))
            stel.addWidget(b)
        stel.addStretch()
        v.addWidget(grp_step)

        # Motor direction test (calibration mode only)
        grp_mot = QGroupBox("MOTOR TEST  (requires CALIBRATION mode)")
        ml = QHBoxLayout(grp_mot)
        ml.setContentsMargins(8, 10, 8, 6)
        ml.addWidget(QLabel("PWM:"))
        self._mot_test_pwm = _spin_i(10, 200, 60, 64)
        btn_cw  = QPushButton("▶ CW")
        btn_cw.setFixedHeight(24)
        btn_ccw = QPushButton("◀ CCW")
        btn_ccw.setFixedHeight(24)
        btn_cw.clicked.connect(lambda: self._motor_test(1))
        btn_ccw.clicked.connect(lambda: self._motor_test(-1))
        ml.addWidget(self._mot_test_pwm)
        ml.addWidget(btn_cw)
        ml.addWidget(btn_ccw)
        ml.addStretch()
        v.addWidget(grp_mot)

        # Calibration wizard (inline)
        grp_cal = QGroupBox("CALIBRATION WIZARD")
        cl = QVBoxLayout(grp_cal)
        cl.setContentsMargins(8, 10, 8, 6)
        cl.setSpacing(4)
        steps = [
            ("1 Enter Cal Mode", lambda: self._set_mode("CALIBRATION")),
            ("2 Zero Encoder",   lambda: self._serial.zero_encoder() if self._check() else None),
            ("3 Set Center",     lambda: self._serial.set_center()   if self._check() else None),
            ("4 Test CW  (+)",   lambda: self._motor_test(1)),
            ("5 Test CCW (−)",   lambda: self._motor_test(-1)),
            ("6 Back to IDLE",   lambda: self._set_mode("IDLE")),
        ]
        step_row1 = QHBoxLayout()
        step_row2 = QHBoxLayout()
        for i, (lbl, fn) in enumerate(steps):
            b = QPushButton(lbl)
            b.setFixedHeight(24)
            b.clicked.connect(fn)
            (step_row1 if i < 3 else step_row2).addWidget(b)
        cl.addLayout(step_row1)
        cl.addLayout(step_row2)
        v.addWidget(grp_cal)

        v.addStretch()

        # Sweep timer (not a widget)
        self._sweep_timer = QTimer()
        self._sweep_timer.timeout.connect(self._sweep_tick)
        self._sweep_angle = 0.0
        self._sweep_dir = 1

        return w

    # ── Firmware tab ──────────────────────────────────────────────

    def _build_firmware_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        grp_build = QGroupBox("BUILD & FLASH")
        bl = QVBoxLayout(grp_build)
        bl.setContentsMargins(8, 10, 8, 8)
        bl.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_build = QPushButton("⚙  Build Hex")
        btn_build.setObjectName("btn_primary")
        btn_build.setFixedHeight(28)
        btn_build.clicked.connect(self._run_build)

        btn_flash = QPushButton("⬆  Flash to Device")
        btn_flash.setFixedHeight(28)
        btn_flash.clicked.connect(self._run_flash)

        btn_open = QPushButton("📁  Open Output Folder")
        btn_open.setObjectName("btn_tool")
        btn_open.setFixedHeight(28)
        btn_open.clicked.connect(self._open_output)

        btn_update = QPushButton("🔄  Update Repo + Rebuild")
        btn_update.setObjectName("btn_warning")
        btn_update.setFixedHeight(28)
        btn_update.setToolTip("git pull → rebuild hex → copy to output/")
        btn_update.clicked.connect(self._run_update)

        btn_row.addWidget(btn_build)
        btn_row.addWidget(btn_flash)
        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_update)
        bl.addLayout(btn_row)

        # Hex path display
        self._hex_path_lbl = QLabel("Hex: not built yet")
        self._hex_path_lbl.setStyleSheet(
            f"color:{COLORS['text_dim']};font-size:10px;font-family:Consolas;"
        )
        bl.addWidget(self._hex_path_lbl)

        # Build output
        self._build_log = QTextEdit()
        self._build_log.setReadOnly(True)
        self._build_log.setStyleSheet(
            f"font-family:Consolas;font-size:10px;"
            f"background:{COLORS['bg_dark']};border:none;"
        )
        bl.addWidget(self._build_log)
        v.addWidget(grp_build)

        # Version info
        grp_ver = QGroupBox("FIRMWARE INFO")
        vl = QFormLayout(grp_ver)
        vl.setContentsMargins(8, 10, 8, 6)
        self._fw_ver_lbl = QLabel(self._serial.fw_version if self._serial else "—")
        self._fw_ver_lbl.setStyleSheet(
            f"color:{COLORS['accent_cyan']};font-family:Consolas;"
        )
        self._eeprom_lbl = QLabel("—")
        self._eeprom_lbl.setStyleSheet(
            f"font-family:Consolas;color:{COLORS['accent_green']};"
        )
        vl.addRow(QLabel("FW Version:"), self._fw_ver_lbl)
        vl.addRow(QLabel("EEPROM:"),     self._eeprom_lbl)
        v.addWidget(grp_ver)

        v.addStretch()
        return w

    # ─── Signal wiring ──────────────────────────────────────────────

    def _wire_signals(self):
        if self._serial:
            self._serial.connected.connect(self._on_connected)
            self._serial.disconnected.connect(self._on_disconnected)
            self._serial.telem_received.connect(self._on_telem)
            self._serial.config_received.connect(self._on_config)
            self._serial.profiles_received.connect(self._on_profiles)
            self._serial.raw_line.connect(
                lambda l: self._serial_log.append(f"{l}") if hasattr(self, "_serial_log") else None
            )
            self._serial.boot_received.connect(self._on_boot)

    # ─── Handlers ───────────────────────────────────────────────────

    def _check(self) -> bool:
        return bool(self._serial and self._serial.is_connected)

    def _refresh_ports(self):
        cur = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(SerialManager.list_ports())
        if cur:
            self._port_combo.setCurrentText(cur)

    def _toggle_connect(self):
        if not self._serial:
            return
        if self._serial.is_connected:
            self._serial.disconnect()
        else:
            port = self._port_combo.currentText().strip()
            baud = int(self._baud_combo.currentText())
            if not port:
                return
            ok = self._serial.connect(port, baud)
            if ok:
                # save to config
                if self._config:
                    self._config.set("serial.port", port)
                    self._config.set("serial.baud", baud)
                # fetch config + profiles after boot settle
                QTimer.singleShot(500, lambda: (
                    self._serial.get_config(),
                    self._serial.list_profiles()
                ) if self._serial.is_connected else None)

    def _on_connected(self):
        self._btn_connect.setText("Disconnect")
        self._badge_conn.set_ok("Connected")

    def _on_disconnected(self):
        self._btn_connect.setText("Connect")
        self._badge_conn.set_inactive("Disconnected")
        self._badge_mode.set_inactive("—")
        self._badge_fault.set_inactive("—")

    def _on_boot(self, obj: dict):
        ver = obj.get("version", "—")
        eep = obj.get("eeprom", False)
        self._badge_fw.set_state("active", f"FW {ver}")
        if hasattr(self, "_fw_ver_lbl"):
            self._fw_ver_lbl.setText(ver)
        if hasattr(self, "_eeprom_lbl"):
            self._eeprom_lbl.setText("Loaded" if eep else "Defaults")
            if not eep:
                self._eeprom_lbl.setStyleSheet(
                    f"font-family:Consolas;color:{COLORS['accent_yellow']};"
                )

    def _on_telem(self, obj: dict):
        angle  = obj.get("angle",  0.0)
        target = obj.get("target", 0.0)
        motor  = obj.get("motor",  0)
        vel    = obj.get("vel",    0.0)
        enc    = obj.get("enc",    0)
        fault  = obj.get("fault",  0)
        mode   = obj.get("mode",   "—")

        self._lbl_angle.setText(f"{angle:.1f}°")
        self._lbl_target.setText(f"{target:.1f}°")
        self._lbl_motor.setText(str(motor))
        self._lbl_vel.setText(f"{vel:.1f}")
        self._lbl_enc.setText(str(enc))
        self._motor_bar.setValue(abs(motor))

        # Mode badge
        mode_states = {
            "IDLE": "inactive", "NORMAL_HID": "ok",
            "ANGLE_TRACK": "active", "ASSIST": "active",
            "ESTOP": "estop", "CALIBRATION": "warn",
        }
        self._badge_mode.set_state(mode_states.get(mode, "inactive"), mode)

        # Fault badge
        if fault:
            fnames = []
            if fault & 0x01: fnames.append("SER_TIMEOUT")
            if fault & 0x02: fnames.append("ANG_CLAMP")
            if fault & 0x04: fnames.append("EEP_DEFAULTS")
            if fault & 0x08: fnames.append("MOT_OVERLOAD")
            self._badge_fault.set_error("|".join(fnames))
        else:
            self._badge_fault.set_ok("None")

        # Charts
        self._chart_angle.push(angle)
        self._chart_angle.push2(target)
        self._chart_motor.push(float(motor))

    def _on_config(self, obj: dict):
        self._config_cache = obj
        for key, lbl_w in self._cfg_fields.items():
            val = obj.get(key, "—")
            lbl_w.setText(str(val))
        # Sync spinboxes from device config
        self._sb_kp.setValue(obj.get("kp",           self._sb_kp.value()))
        self._sb_kd.setValue(obj.get("kd",           self._sb_kd.value()))
        self._sb_ki.setValue(obj.get("ki",           self._sb_ki.value()))
        self._sb_dz.setValue(obj.get("dead_zone",    self._sb_dz.value()))
        self._sb_range.setValue(obj.get("angle_range",   self._sb_range.value()))
        self._sb_cpr.setValue(obj.get("counts_per_rev",  self._sb_cpr.value()))
        self._sb_gear.setValue(obj.get("gear_ratio",     self._sb_gear.value()))
        self._sb_max_mot.setValue(int(obj.get("max_motor",   self._sb_max_mot.value())))
        self._sb_slew.setValue(obj.get("slew_rate",      self._sb_slew.value()))
        self._sb_center.setValue(obj.get("centering",    self._sb_center.value()))
        self._sb_damping.setValue(obj.get("damping",     self._sb_damping.value()))
        self._sb_friction.setValue(obj.get("friction",   self._sb_friction.value()))
        self._sb_inertia.setValue(obj.get("inertia",     self._sb_inertia.value()))
        self._sb_smooth.setValue(obj.get("smoothing",    self._sb_smooth.value()))
        self._cb_inv_enc.setChecked(bool(obj.get("invert_encoder", False)))
        self._cb_inv_mot.setChecked(bool(obj.get("invert_motor",   False)))
        eep_ok = obj.get("eeprom_ok", False)
        if hasattr(self, "_eeprom_lbl"):
            self._eeprom_lbl.setText("Loaded" if eep_ok else "Factory defaults")

    def _on_profiles(self, slots: list):
        self._profile_slots = slots
        self._profile_list.clear()
        for s in slots:
            name = s.get("name", "—") if s.get("valid") else "  (empty)"
            item = QListWidgetItem(f"  [{s['slot']}]  {name}")
            if not s.get("valid"):
                item.setForeground(Qt.GlobalColor.darkGray)
            self._profile_list.addItem(item)

    # ─── Apply buttons ──────────────────────────────────────────────

    def _set_mode(self, mode: str):
        if self._check():
            self._serial.set_mode(mode)

    def _do_estop(self):
        if self._check():
            self._serial.estop()
        if self._safety:
            self._safety.trigger_estop("Manual E-STOP from UI")

    def _apply_setup(self):
        if not self._check():
            return
        self._serial.push_config({
            "angle_range":   self._sb_range.value(),
            "counts_per_rev":self._sb_cpr.value(),
            "gear_ratio":    self._sb_gear.value(),
            "max_motor":     int(self._sb_max_mot.value()),
            "slew_rate":     self._sb_slew.value(),
            "invert_encoder":self._cb_inv_enc.isChecked(),
            "invert_motor":  self._cb_inv_mot.isChecked(),
        })

    def _apply_pd(self):
        if not self._check():
            return
        self._serial.push_config({
            "kp":       self._sb_kp.value(),
            "kd":       self._sb_kd.value(),
            "ki":       self._sb_ki.value(),
            "dead_zone":self._sb_dz.value(),
        })

    def _default_pd(self):
        self._sb_kp.setValue(1.8)
        self._sb_kd.setValue(0.12)
        self._sb_ki.setValue(0.0)
        self._sb_dz.setValue(1.5)
        self._apply_pd()

    def _apply_ffb(self):
        if not self._check():
            return
        self._serial.push_config({
            "centering": self._sb_center.value(),
            "damping":   self._sb_damping.value(),
            "friction":  self._sb_friction.value(),
            "inertia":   self._sb_inertia.value(),
            "smoothing": self._sb_smooth.value(),
        })

    def _default_ffb(self):
        self._sb_center.setValue(1.0)
        self._sb_damping.setValue(0.12)
        self._sb_friction.setValue(0.05)
        self._sb_inertia.setValue(0.04)
        self._sb_smooth.setValue(0.10)
        self._apply_ffb()

    # ─── EEPROM ─────────────────────────────────────────────────────

    def _save_config_eeprom(self):
        if self._check():
            self._serial.save_config()

    def _load_config_eeprom(self):
        if self._check():
            self._serial.load_config()
            QTimer.singleShot(300, lambda: self._serial.get_config()
                              if self._serial.is_connected else None)

    def _factory_reset(self):
        if QMessageBox.question(
            self, "Factory Reset",
            "This will erase ALL EEPROM data and restore firmware defaults.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            if self._check():
                self._serial.factory_reset()

    # ─── Profile slots ───────────────────────────────────────────────

    def _save_to_slot(self):
        slot = int(self._slot_combo.currentText())
        name = self._slot_name.text().strip() or f"Profile{slot}"
        if self._check():
            self._serial.save_profile(slot, name)
            QTimer.singleShot(200, lambda: self._serial.list_profiles()
                              if self._serial.is_connected else None)

    def _load_from_slot(self):
        slot = int(self._slot_combo.currentText())
        if self._check():
            self._serial.load_profile(slot)
            QTimer.singleShot(300, lambda: self._serial.get_config()
                              if self._serial.is_connected else None)

    # ─── Profile JSON export / import ────────────────────────────────

    # _EEPROM_CONFIG_KEYS mirrors the keys the firmware accepts via set_config
    _EEPROM_CONFIG_KEYS = (
        "kp", "kd", "ki", "dead_zone",
        "angle_range", "counts_per_rev", "gear_ratio",
        "invert_encoder", "invert_motor", "max_motor",
        "slew_rate", "centering", "damping",
        "friction", "inertia", "smoothing",
    )

    def _export_profile_json(self):
        """Save the last known device config to a JSON file on disk."""
        if not self._config_cache:
            QMessageBox.warning(
                self, "No Config",
                "No config loaded yet.\n"
                "Connect to the device and use Diagnostics → Read Config first."
            )
            return
        profile_name = self._config_cache.get("profile", "export")
        default_name = f"profile_{profile_name}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profile", default_name, "JSON (*.json)"
        )
        if not path:
            return
        data = {k: v for k, v in self._config_cache.items()
                if k in self._EEPROM_CONFIG_KEYS}
        data["profile"] = profile_name
        try:
            with open(path, "w") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))
            return
        if hasattr(self, "_serial_log"):
            self._serial_log.append(f"[export] {os.path.basename(path)}")

    def _import_profile_json(self):
        """Load a JSON profile from disk and push all config keys to the device."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Profile", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return
        if not self._check():
            QMessageBox.warning(self, "Not Connected", "Connect to device first.")
            return
        to_push = {k: data[k] for k in self._EEPROM_CONFIG_KEYS if k in data}
        if not to_push:
            QMessageBox.warning(
                self, "Nothing to Import",
                "The file contained no recognised config keys."
            )
            return
        self._serial.push_config(to_push)
        # Offer to save to EEPROM immediately
        if QMessageBox.question(
            self, "Save to EEPROM?",
            f"Imported {len(to_push)} keys from {os.path.basename(path)}.\n"
            "Save to EEPROM now so settings survive power-off?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._serial.save_config()
        QTimer.singleShot(300, lambda: self._serial.get_config()
                          if self._serial.is_connected else None)
        if hasattr(self, "_serial_log"):
            self._serial_log.append(
                f"[import] {os.path.basename(path)} → {len(to_push)} keys"
            )

    def _start_sweep(self):
        if not self._check():
            return
        self._serial.set_mode("ANGLE_TRACK")
        self._sweep_angle = 0.0
        self._sweep_dir   = 1
        self._sweep_timer.start(100)

    def _stop_sweep(self):
        self._sweep_timer.stop()
        if self._check():
            self._serial.set_target(0.0)
        self._sweep_bar.setValue(0)

    def _sweep_tick(self):
        mx = self._sweep_sb.value()
        self._sweep_angle += 5.0 * self._sweep_dir
        if   self._sweep_angle >= mx:  self._sweep_angle = mx;  self._sweep_dir = -1
        elif self._sweep_angle <= -mx: self._sweep_angle = -mx; self._sweep_dir =  1
        if self._check():
            self._serial.set_target(self._sweep_angle)
        self._sweep_bar.setValue(int(self._sweep_angle / mx * 100))

    # ─── Step test ───────────────────────────────────────────────────

    def _step_to(self, angle: int):
        if not self._check():
            return
        self._serial.set_mode("ANGLE_TRACK")
        self._serial.set_target(float(angle))

    # ─── Motor test ──────────────────────────────────────────────────

    def _motor_test(self, direction: int):
        if not self._check():
            return
        pwm = self._mot_test_pwm.value()
        self._serial.motor_test(direction, pwm)

    # ─── Firmware build / flash ──────────────────────────────────────

    def _run_script(self, script: str, label: str):
        self._build_log.clear()
        self._build_log.append(f"[{label}] Running {script} ...\n")
        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", script],
                capture_output=True, text=True, cwd=os.getcwd(), timeout=120
            )
            self._build_log.append(result.stdout)
            if result.stderr:
                self._build_log.append("[stderr]\n" + result.stderr)
            self._build_log.append(
                f"\n[{label}] {'Done ✓' if result.returncode == 0 else 'FAILED ✗'}"
            )
            # Look for hex path in output
            for line in result.stdout.splitlines():
                if ".hex" in line.lower() and ("output" in line.lower() or "copied" in line.lower()):
                    self._hex_path_lbl.setText(f"Hex: {line.strip()}")
                    break
        except FileNotFoundError:
            self._build_log.append(f"[{label}] ERROR: PowerShell not found (Windows only).")
        except subprocess.TimeoutExpired:
            self._build_log.append(f"[{label}] ERROR: Timed out after 120 s.")

    def _run_build(self):
        self._run_script("build_hex.ps1", "BUILD")

    def _run_flash(self):
        self._run_script("flash_hex.ps1", "FLASH")

    def _run_update(self):
        self._run_script("update_repo.ps1", "UPDATE")

    def _open_output(self):
        path = os.path.abspath("output/firmware")
        if os.path.exists(path):
            try:
                os.startfile(path)
            except AttributeError:
                pass  # non-Windows

    # ─── Periodic refresh ────────────────────────────────────────────

    def refresh(self):
        # Called by main window timer — nothing extra needed; telem signal drives updates
        pass
