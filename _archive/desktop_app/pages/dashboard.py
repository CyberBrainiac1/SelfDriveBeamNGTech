"""
desktop_app/pages/dashboard.py — Dashboard.
Engineering panel: status grid + badges + angle/motor chart + quick actions.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from widgets.mini_chart import MiniChart
from widgets.status_badge import StatusBadge
from ui.styles import COLORS


class DashboardPage(BasePage):
    def __init__(self, beamng_manager=None, profiles=None, **kwargs):
        self._beamng_manager = beamng_manager
        self._profiles = profiles
        super().__init__(title="Dashboard", **kwargs)
        self._build()
        self._wire()

    def _build(self):
        h = QHBoxLayout()
        h.setSpacing(8)
        h.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addLayout(h)

        # ── Left column ───────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(self._build_status())
        left.addWidget(self._build_telemetry())
        left.addWidget(self._build_quick_actions())
        left.addStretch()
        h.addLayout(left, 3)

        # ── Right column ──────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(self._build_charts())
        right.addStretch()
        h.addLayout(right, 4)

    # ── Status group ──────────────────────────────────────────────

    def _build_status(self) -> QGroupBox:
        grp = QGroupBox("STATUS")
        g = QGridLayout(grp)
        g.setContentsMargins(8, 12, 8, 8)
        g.setSpacing(8)
        g.setColumnStretch(1, 1)

        def row(r, label, badge_attr, val_attr=None):
            g.addWidget(QLabel(label), r, 0)
            if badge_attr:
                badge = StatusBadge("—", "inactive")
                setattr(self, badge_attr, badge)
                g.addWidget(badge, r, 1, Qt.AlignmentFlag.AlignLeft)
            if val_attr:
                val = QLabel("—")
                val.setStyleSheet(
                    f"color:{COLORS['accent_cyan']};font-family:Consolas;font-size:11px;"
                )
                setattr(self, val_attr, val)
                g.addWidget(val, r, 2)

        row(0, "Serial",   "_b_serial")
        row(1, "Mode",     "_b_mode")
        row(2, "Firmware", "_b_fw")
        row(3, "BeamNG",   "_b_bng")
        row(4, "EEPROM",   "_b_eeprom")
        row(5, "Profile",  None, "_v_profile")
        row(6, "Faults",   "_b_fault")
        return grp

    # ── Telemetry group ───────────────────────────────────────────

    def _build_telemetry(self) -> QGroupBox:
        grp = QGroupBox("TELEMETRY")
        g = QGridLayout(grp)
        g.setContentsMargins(8, 12, 8, 8)
        g.setSpacing(8)
        g.setColumnMinimumWidth(1, 80)
        g.setColumnMinimumWidth(3, 80)

        def cell(row, col, label, attr, color=None):
            g.addWidget(QLabel(label), row, col * 2)
            val = QLabel("—")
            c = color or COLORS["text_primary"]
            val.setStyleSheet(
                f"color:{c};font-size:20px;font-weight:700;font-family:Consolas;"
            )
            g.addWidget(val, row, col * 2 + 1)
            setattr(self, attr, val)

        cell(0, 0, "Angle",   "_tv_angle",  COLORS["accent_blue"])
        cell(0, 1, "Target",  "_tv_target", COLORS["accent_green"])
        cell(1, 0, "Motor",   "_tv_motor",  COLORS["accent_yellow"])
        cell(1, 1, "Vel °/s", "_tv_vel",    COLORS["text_secondary"])
        return grp

    # ── Quick actions ─────────────────────────────────────────────

    def _build_quick_actions(self) -> QGroupBox:
        grp = QGroupBox("QUICK ACTIONS")
        h = QHBoxLayout(grp)
        h.setContentsMargins(8, 12, 8, 8)
        h.setSpacing(6)
        actions = [
            ("IDLE",         lambda: self._mode("IDLE")),
            ("HID Mode",     lambda: self._mode("NORMAL_HID")),
            ("Angle Track",  lambda: self._mode("ANGLE_TRACK")),
        ]
        for lbl, fn in actions:
            b = QPushButton(lbl)
            b.setFixedHeight(26)
            b.clicked.connect(fn)
            h.addWidget(b)

        btn_estop = QPushButton("⚠ E-STOP")
        btn_estop.setObjectName("btn_danger")
        btn_estop.setFixedHeight(26)
        btn_estop.clicked.connect(self._estop)
        h.addStretch()
        h.addWidget(btn_estop)
        return grp

    # ── Charts ────────────────────────────────────────────────────

    def _build_charts(self) -> QGroupBox:
        grp = QGroupBox("LIVE CHARTS")
        v = QVBoxLayout(grp)
        v.setContentsMargins(6, 12, 6, 6)
        v.setSpacing(6)
        self._ch_angle = MiniChart(
            "Angle / Target", color=COLORS["accent_blue"],
            color2=COLORS["accent_green"],
            y_min=-270, y_max=270, height=120
        )
        self._ch_motor = MiniChart(
            "Motor Output", color=COLORS["accent_yellow"],
            y_min=-260, y_max=260, height=80
        )
        v.addWidget(self._ch_angle)
        v.addWidget(self._ch_motor)
        return grp

    # ── Wiring ────────────────────────────────────────────────────

    def _wire(self):
        if self._serial:
            self._serial.connected.connect(self._on_connect)
            self._serial.disconnected.connect(self._on_disconnect)
            self._serial.telem_received.connect(self._on_telem)
            self._serial.boot_received.connect(self._on_boot)
        if self._beamng_manager:
            self._beamng_manager.connected.connect(
                lambda: self._b_bng.set_ok("Connected")
            )
            self._beamng_manager.disconnected.connect(
                lambda: self._b_bng.set_inactive("Disconnected")
            )

    def _on_connect(self):
        self._b_serial.set_ok("Connected")
        self._b_fw.set_active(self._serial.fw_version)

    def _on_disconnect(self):
        self._b_serial.set_inactive("Disconnected")
        self._b_mode.set_inactive("—")
        self._b_fw.set_inactive("FW: —")

    def _on_boot(self, obj):
        ver = obj.get("version", "—")
        eep = obj.get("eeprom",  False)
        self._b_fw.set_active(f"FW {ver}")
        self._b_eeprom.set_state("ok" if eep else "warn",
                                 "Loaded" if eep else "Defaults")

    def _on_telem(self, obj):
        angle  = obj.get("angle",  0.0)
        target = obj.get("target", 0.0)
        motor  = obj.get("motor",  0)
        vel    = obj.get("vel",    0.0)
        fault  = obj.get("fault",  0)
        mode   = obj.get("mode",   "—")
        profile= obj.get("profile","—")

        self._tv_angle.setText(f"{angle:.1f}°")
        self._tv_target.setText(f"{target:.1f}°")
        self._tv_motor.setText(str(motor))
        self._tv_vel.setText(f"{vel:.1f}")
        self._v_profile.setText(profile)

        mode_map = {
            "IDLE": "inactive", "NORMAL_HID": "ok",
            "ANGLE_TRACK": "active", "ASSIST": "active",
            "ESTOP": "estop", "CALIBRATION": "warn",
        }
        self._b_mode.set_state(mode_map.get(mode, "inactive"), mode)

        if fault:
            self._b_fault.set_error(f"0x{fault:02X}")
        else:
            self._b_fault.set_ok("None")

        self._ch_angle.push(angle)
        self._ch_angle.push2(target)
        self._ch_motor.push(float(motor))

    def _mode(self, m):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode(m)

    def _estop(self):
        if self._serial and self._serial.is_connected:
            self._serial.estop()
        if self._safety:
            self._safety.trigger_estop("Dashboard E-STOP")

    def refresh(self):
        if self._profiles and hasattr(self, "_v_profile"):
            cur = self._profiles.current_name
            if cur:
                self._v_profile.setText(cur)
