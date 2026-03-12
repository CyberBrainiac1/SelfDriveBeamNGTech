"""
desktop_app/pages/dashboard.py — Dashboard: connection, live telemetry, E-STOP.
Simple: one row to connect, four telemetry values, one big ESTOP button.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox, QFrame
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS
from core.serial_manager import SerialManager


class DashboardPage(BasePage):
    def __init__(self, **kwargs):
        self._beamng_manager = kwargs.pop("beamng_manager", None)
        self._profiles = kwargs.pop("profiles", None)
        super().__init__(title="Dashboard", **kwargs)
        self._build()

    def _build(self):
        # ── Connection row ──────────────────────────────────────────
        row = QHBoxLayout()
        row.setSpacing(8)
        self._port_combo = QComboBox()
        self._port_combo.setFixedWidth(130)
        self._port_combo.setPlaceholderText("COM port")
        self._refresh_ports()

        btn_ref = QPushButton("↺")
        btn_ref.setFixedWidth(28)
        btn_ref.setToolTip("Refresh ports")
        btn_ref.clicked.connect(self._refresh_ports)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setObjectName("btn_primary")
        self._btn_connect.setFixedWidth(88)
        self._btn_connect.clicked.connect(self._toggle_connect)

        self._conn_lbl = QLabel("Disconnected")
        self._conn_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")

        row.addWidget(QLabel("Port:"))
        row.addWidget(self._port_combo)
        row.addWidget(btn_ref)
        row.addWidget(self._btn_connect)
        row.addWidget(self._conn_lbl)
        row.addStretch()
        self.content_layout.addLayout(row)
        self.content_layout.addWidget(self._sep())

        # ── Four live values ─────────────────────────────────────────
        grid = QHBoxLayout()
        grid.setSpacing(12)
        self._v_angle  = self._card("Angle",    "0.0°")
        self._v_target = self._card("Target",   "0.0°")
        self._v_motor  = self._card("Motor",    "0%")
        self._v_mode   = self._card("Mode",     "IDLE")
        for c in [self._v_angle, self._v_target, self._v_motor, self._v_mode]:
            grid.addWidget(c)
        self.content_layout.addLayout(grid)
        self.content_layout.addWidget(self._sep())

        # ── Info row: FW + Profile + Faults ─────────────────────────
        info = QHBoxLayout()
        info.setSpacing(24)
        self._fw_lbl     = self._kv("Firmware", "—")
        self._profile_lbl = self._kv("Profile", "—")
        self._fault_lbl  = self._kv("Faults",  "None")
        self._bng_lbl    = self._kv("BeamNG",  "—")
        for w in [self._fw_lbl, self._profile_lbl, self._fault_lbl, self._bng_lbl]:
            info.addWidget(w)
        info.addStretch()
        self.content_layout.addLayout(info)

        self.content_layout.addStretch()

        # ── E-STOP ───────────────────────────────────────────────────
        estop = QPushButton("⚠  EMERGENCY STOP")
        estop.setObjectName("btn_danger")
        estop.setFixedHeight(44)
        estop.clicked.connect(self._estop)
        self.content_layout.addWidget(estop)

        # signals
        if self._serial:
            self._serial.connected.connect(self._on_connected)
            self._serial.disconnected.connect(self._on_disconnected)

    # helpers ────────────────────────────────────────────────────────
    def _card(self, label: str, initial: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"background:{COLORS['bg_panel']}; border:1px solid {COLORS['border']};"
            f"border-radius:4px;"
        )
        v = QVBoxLayout(f)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(f"color:{COLORS['text_dim']};font-size:10px;letter-spacing:1px;")
        val = QLabel(initial)
        val.setStyleSheet(
            f"color:{COLORS['text_primary']};font-size:20px;font-weight:700;font-family:Consolas;"
        )
        v.addWidget(lbl)
        v.addWidget(val)
        f._val = val          # store for updates
        return f

    def _kv(self, key: str, val: str) -> QFrame:
        f = QFrame()
        h = QHBoxLayout(f)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        k = QLabel(key + ":")
        k.setStyleSheet(f"color:{COLORS['text_dim']};font-size:11px;")
        v = QLabel(val)
        v.setStyleSheet(f"color:{COLORS['text_secondary']};font-size:11px;font-family:Consolas;")
        h.addWidget(k)
        h.addWidget(v)
        f._val = v
        return f

    def _refresh_ports(self):
        cur = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(SerialManager.list_ports())
        if cur:
            self._port_combo.setCurrentText(cur)

    def _toggle_connect(self):
        if self._serial.is_connected:
            self._serial.disconnect()
        else:
            port = self._port_combo.currentText()
            if port:
                baud = self._config.get("serial.baud", 115200) if self._config else 115200
                self._serial.connect(port, baud)

    def _on_connected(self, port):
        self._btn_connect.setText("Disconnect")
        self._conn_lbl.setText(f"Connected  ({port})")
        self._conn_lbl.setStyleSheet(f"color:{COLORS['accent_green']};")

    def _on_disconnected(self):
        self._btn_connect.setText("Connect")
        self._conn_lbl.setText("Disconnected")
        self._conn_lbl.setStyleSheet(f"color:{COLORS['text_dim']};")

    def _estop(self):
        if self._safety:
            self._safety.trigger_estop("dashboard button")

    def refresh(self):
        t = self._telemetry.latest if self._telemetry else None
        if t:
            self._v_angle._val.setText(f"{t.angle:.1f}°")
            self._v_target._val.setText(f"{t.target:.1f}°")
            pct = int(abs(t.motor) / 255 * 100)
            self._v_motor._val.setText(f"{pct}%")
            self._v_mode._val.setText(t.mode)

            faults = t.fault_names()
            self._fault_lbl._val.setText(", ".join(faults) if faults else "None")
            self._fault_lbl._val.setStyleSheet(
                f"color:{COLORS['accent_red'] if faults else COLORS['accent_green']};"
                f"font-size:11px;font-family:Consolas;"
            )

        if self._serial and self._serial.is_connected:
            self._fw_lbl._val.setText(self._serial.fw_version)

        if self._profiles and self._profiles.current_name:
            self._profile_lbl._val.setText(self._profiles.current_name)

        if self._beamng_manager:
            self._bng_lbl._val.setText(
                "Connected" if self._beamng_manager.is_connected else "—"
            )

