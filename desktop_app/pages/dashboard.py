"""
desktop_app/pages/dashboard.py — Main dashboard page.
Shows connection status, live telemetry at a glance, and quick actions.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame, QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from pages.base_page import BasePage
from ui.styles import COLORS


class _TelemetryCard(QFrame):
    """A small card showing a single telemetry value."""
    def __init__(self, label: str, unit: str = ""):
        super().__init__()
        self.setStyleSheet(
            f"background-color: {COLORS['bg_panel']}; "
            f"border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(78)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._label = QLabel(label.upper())
        self._label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; "
            f"font-weight: 600; letter-spacing: 1px;"
        )
        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 22px; "
            f"font-weight: 700; font-family: Consolas;"
        )
        self._unit = unit
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, val, unit: str = None):
        u = unit if unit else self._unit
        if isinstance(val, float):
            self._value.setText(f"{val:.1f}{u}")
        else:
            self._value.setText(f"{val}{u}")

    def set_color(self, color: str):
        self._value.setStyleSheet(
            f"color: {color}; font-size: 22px; "
            f"font-weight: 700; font-family: Consolas;"
        )


class _StatusRow(QFrame):
    """A horizontal status indicator row."""
    def __init__(self, label: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._dot = QLabel("●")
        self._dot.setFixedWidth(16)
        self._name = QLabel(label)
        self._name.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._status = QLabel("Unknown")
        self._status.setStyleSheet(f"color: {COLORS['text_dim']};")
        layout.addWidget(self._dot)
        layout.addWidget(self._name)
        layout.addStretch()
        layout.addWidget(self._status)

    def set_ok(self, text: str = "OK"):
        self._dot.setStyleSheet(f"color: {COLORS['accent_green']};")
        self._status.setStyleSheet(f"color: {COLORS['accent_green']};")
        self._status.setText(text)

    def set_warn(self, text: str = "Warning"):
        self._dot.setStyleSheet(f"color: {COLORS['accent_yellow']};")
        self._status.setStyleSheet(f"color: {COLORS['accent_yellow']};")
        self._status.setText(text)

    def set_error(self, text: str = "Error"):
        self._dot.setStyleSheet(f"color: {COLORS['accent_red']};")
        self._status.setStyleSheet(f"color: {COLORS['accent_red']};")
        self._status.setText(text)

    def set_inactive(self, text: str = "—"):
        self._dot.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._status.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._status.setText(text)


class DashboardPage(BasePage):
    def __init__(self, **kwargs):
        self._beamng_manager = kwargs.pop("beamng_manager", None)
        self._profiles = kwargs.pop("profiles", None)
        super().__init__(
            title="Dashboard",
            subtitle="System overview and quick actions",
            **kwargs
        )
        self._build_content()

    def _build_content(self):
        main_h = QHBoxLayout()
        main_h.setSpacing(16)
        self.content_layout.addLayout(main_h)
        self.content_layout.addStretch()

        # ---- Left column: status + telemetry cards ----
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Connection status panel
        status_group = QGroupBox("SYSTEM STATUS")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(6)

        self._sr_serial  = _StatusRow("Serial / USB")
        self._sr_device  = _StatusRow("Wheel Controller")
        self._sr_encoder = _StatusRow("Encoder")
        self._sr_beamng  = _StatusRow("BeamNG.tech")
        self._sr_safety  = _StatusRow("Safety")

        for row in [self._sr_serial, self._sr_device, self._sr_encoder,
                    self._sr_beamng, self._sr_safety]:
            status_layout.addWidget(row)

        self._sr_serial.set_inactive("Not connected")
        self._sr_device.set_inactive("—")
        self._sr_encoder.set_inactive("—")
        self._sr_beamng.set_inactive("Not connected")
        self._sr_safety.set_ok("Ready")

        left_col.addWidget(status_group)

        # Info: firmware version + profile
        info_group = QGroupBox("DEVICE INFO")
        info_layout = QGridLayout(info_group)
        info_layout.setHorizontalSpacing(12)
        info_layout.setVerticalSpacing(6)

        def info_row(row, label, attr):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
            val = QLabel("—")
            val.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas;")
            info_layout.addWidget(lbl, row, 0)
            info_layout.addWidget(val, row, 1)
            return val

        self._fw_ver_lbl   = info_row(0, "Firmware:", "fw_version")
        self._mode_lbl     = info_row(1, "Mode:", "mode")
        self._profile_lbl  = info_row(2, "Profile:", "profile")
        self._fault_lbl    = info_row(3, "Faults:", "faults")

        left_col.addWidget(info_group)
        left_col.addStretch()

        # ---- Right column: live telemetry cards + quick actions ----
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # Telemetry cards grid
        cards_label = QLabel("LIVE TELEMETRY")
        cards_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; font-weight: 600; letter-spacing: 1px;"
        )
        right_col.addWidget(cards_label)

        cards_grid = QGridLayout()
        cards_grid.setSpacing(8)

        self._card_angle  = _TelemetryCard("Current Angle", "°")
        self._card_target = _TelemetryCard("Target Angle", "°")
        self._card_motor  = _TelemetryCard("Motor Output", "%")
        self._card_enc    = _TelemetryCard("Encoder Counts", "")

        cards_grid.addWidget(self._card_angle,  0, 0)
        cards_grid.addWidget(self._card_target, 0, 1)
        cards_grid.addWidget(self._card_motor,  1, 0)
        cards_grid.addWidget(self._card_enc,    1, 1)
        right_col.addLayout(cards_grid)

        # Quick actions
        qa_group = QGroupBox("QUICK ACTIONS")
        qa_layout = QHBoxLayout(qa_group)
        qa_layout.setSpacing(8)

        # COM port quick connect
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(110)
        self._port_combo.setPlaceholderText("COM port")
        self._refresh_ports()

        btn_refresh = QPushButton("↺")
        btn_refresh.setFixedWidth(30)
        btn_refresh.setToolTip("Refresh COM ports")
        btn_refresh.clicked.connect(self._refresh_ports)

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setObjectName("btn_primary")
        self._btn_connect.setFixedWidth(90)
        self._btn_connect.clicked.connect(self._on_connect_toggle)

        btn_estop = QPushButton("⚠ E-STOP")
        btn_estop.setObjectName("btn_danger")
        btn_estop.setFixedWidth(100)
        btn_estop.clicked.connect(self._on_estop)

        qa_layout.addWidget(QLabel("Port:"))
        qa_layout.addWidget(self._port_combo)
        qa_layout.addWidget(btn_refresh)
        qa_layout.addWidget(self._btn_connect)
        qa_layout.addStretch()
        qa_layout.addWidget(btn_estop)

        right_col.addWidget(qa_group)
        right_col.addStretch()

        main_h.addLayout(left_col, 2)
        main_h.addLayout(right_col, 3)

        # Connect signals
        if self._serial:
            self._serial.connected.connect(lambda p: self._on_connected(p))
            self._serial.disconnected.connect(self._on_disconnected)

    def _refresh_ports(self):
        from core.serial_manager import SerialManager
        current = self._port_combo.currentText()
        self._port_combo.clear()
        ports = SerialManager.list_ports()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)

    def _on_connect_toggle(self):
        if self._serial.is_connected:
            self._serial.disconnect()
        else:
            port = self._port_combo.currentText()
            if port:
                baud = self._config.get("serial.baud", 115200) if self._config else 115200
                self._serial.connect(port, baud)

    def _on_connected(self, port: str):
        self._btn_connect.setText("Disconnect")
        self._sr_serial.set_ok(f"Connected ({port})")
        self._sr_device.set_ok("Ready")

    def _on_disconnected(self):
        self._btn_connect.setText("Connect")
        self._sr_serial.set_inactive("Not connected")
        self._sr_device.set_inactive("—")

    def _on_estop(self):
        if self._safety:
            self._safety.trigger_estop("manual UI button")

    def refresh(self):
        telem = self._telemetry.latest if self._telemetry else None
        if telem:
            self._card_angle.set_value(telem.angle, "°")
            self._card_target.set_value(telem.target, "°")
            motor_pct = (telem.motor / 255.0) * 100.0
            self._card_motor.set_value(motor_pct, "%")
            self._card_enc.set_value(telem.enc, "")
            self._mode_lbl.setText(telem.mode)

            if telem.has_fault():
                self._sr_encoder.set_error(", ".join(telem.fault_names()))
                self._fault_lbl.setText(", ".join(telem.fault_names()))
                self._fault_lbl.setStyleSheet(f"color: {COLORS['accent_red']};")
            else:
                self._sr_encoder.set_ok("OK")
                self._fault_lbl.setText("None")
                self._fault_lbl.setStyleSheet(f"color: {COLORS['accent_green']};")

            # Motor color by output
            pct = abs(motor_pct)
            if pct > 80:
                self._card_motor.set_color(COLORS['accent_red'])
            elif pct > 50:
                self._card_motor.set_color(COLORS['accent_yellow'])
            else:
                self._card_motor.set_color(COLORS['accent_green'])

        if self._serial and self._serial.is_connected:
            fw = self._serial.fw_version
            self._fw_ver_lbl.setText(fw)

        if self._profiles and self._profiles.current_name:
            self._profile_lbl.setText(self._profiles.current_name)

        if self._beamng_manager:
            if self._beamng_manager.is_connected:
                self._sr_beamng.set_ok("Connected")
            else:
                self._sr_beamng.set_inactive("Not connected")
