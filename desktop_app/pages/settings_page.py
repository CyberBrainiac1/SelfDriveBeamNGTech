"""
desktop_app/pages/settings_page.py — Settings.
COM port, BeamNG host/port, safety limits, log path. Flat form.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QFormLayout, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS
from core.serial_manager import SerialManager


class SettingsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Settings", **kwargs)
        self._build()
        self._load()

    def _build(self):
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)
        self.content_layout.addLayout(form)

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{COLORS['text_secondary']};")
            return l

        # Serial
        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setFixedWidth(140)
        self._refresh_ports()
        port_row = QHBoxLayout()
        port_row.addWidget(self._port_combo)
        btn_r = QPushButton("↺")
        btn_r.setFixedWidth(28)
        btn_r.clicked.connect(self._refresh_ports)
        port_row.addWidget(btn_r)
        port_row.addStretch()
        form.addRow(lbl("COM Port:"), port_row)

        self._baud = QComboBox()
        self._baud.addItems(["9600", "57600", "115200", "230400"])
        self._baud.setCurrentText("115200")
        self._baud.setFixedWidth(100)
        form.addRow(lbl("Baud Rate:"), self._baud)

        form.addRow(self._sep())

        # BeamNG
        self._bng_host = QLineEdit("localhost")
        self._bng_host.setFixedWidth(140)
        form.addRow(lbl("BeamNG Host:"), self._bng_host)

        self._bng_port = QSpinBox()
        self._bng_port.setRange(1000, 65535)
        self._bng_port.setValue(64256)
        self._bng_port.setFixedWidth(100)
        form.addRow(lbl("BeamNG Port:"), self._bng_port)

        form.addRow(self._sep())

        # Safety
        self._max_angle = QDoubleSpinBox()
        self._max_angle.setRange(90, 1080)
        self._max_angle.setValue(540)
        self._max_angle.setSuffix("°")
        self._max_angle.setFixedWidth(100)
        form.addRow(lbl("Max Angle Clamp:"), self._max_angle)

        self._max_motor = QSpinBox()
        self._max_motor.setRange(0, 255)
        self._max_motor.setValue(200)
        self._max_motor.setFixedWidth(100)
        form.addRow(lbl("Max Motor PWM:"), self._max_motor)

        form.addRow(self._sep())

        # Logging
        self._log_dir = QLineEdit("output/logs")
        self._log_dir.setFixedWidth(220)
        log_row = QHBoxLayout()
        log_row.addWidget(self._log_dir)
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse)
        log_row.addWidget(btn_browse)
        log_row.addStretch()
        form.addRow(lbl("Log Directory:"), log_row)

        self.content_layout.addStretch()

        # Save button
        btn_save = QPushButton("Save Settings")
        btn_save.setObjectName("btn_primary")
        btn_save.setFixedWidth(140)
        btn_save.clicked.connect(self._save)
        self.content_layout.addWidget(btn_save)

    def _sep(self):
        from PySide6.QtWidgets import QFrame
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"background:{COLORS['border']};max-height:1px;")
        return f

    def _refresh_ports(self):
        cur = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(SerialManager.list_ports())
        if cur:
            self._port_combo.setCurrentText(cur)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Log Directory")
        if d:
            self._log_dir.setText(d)

    def _save(self):
        if not self._config:
            return
        self._config.set("serial.port", self._port_combo.currentText())
        self._config.set("serial.baud", int(self._baud.currentText()))
        self._config.set("beamng.host", self._bng_host.text())
        self._config.set("beamng.port", self._bng_port.value())
        self._config.set("wheel.angle_range", self._max_angle.value())
        self._config.set("wheel.max_motor_output", self._max_motor.value())
        self._config.set("logging.log_dir", self._log_dir.text())
        if self._safety:
            self._safety.configure(max_angle=self._max_angle.value(),
                                   max_motor=self._max_motor.value())
        if self._log:
            self._log.info("Settings saved")

    def _load(self):
        if not self._config:
            return
        port = self._config.get("serial.port", "")
        if port:
            self._port_combo.setCurrentText(port)
        self._baud.setCurrentText(str(self._config.get("serial.baud", 115200)))
        self._bng_host.setText(self._config.get("beamng.host", "localhost"))
        self._bng_port.setValue(self._config.get("beamng.port", 64256))
        self._max_angle.setValue(self._config.get("wheel.angle_range", 540))
        self._max_motor.setValue(self._config.get("wheel.max_motor_output", 200))
