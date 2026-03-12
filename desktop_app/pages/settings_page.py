"""
desktop_app/pages/settings_page.py — Application settings page.
COM port, simulator, logging, theme, safety options.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit,
    QFormLayout, QFileDialog
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS
from core.serial_manager import SerialManager


class SettingsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Settings",
            subtitle="Serial, simulator, logging, and safety configuration",
            **kwargs
        )
        self._build_content()
        self._load_settings()

    def _build_content(self):
        main_h = QHBoxLayout()
        main_h.setSpacing(16)
        self.content_layout.addLayout(main_h)
        self.content_layout.addStretch()

        left = QVBoxLayout()
        right = QVBoxLayout()
        main_h.addLayout(left, 1)
        main_h.addLayout(right, 1)

        # ---- Serial ----
        serial_group = QGroupBox("SERIAL / USB")
        serial_form = QFormLayout(serial_group)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._refresh_ports()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(70)
        btn_refresh.clicked.connect(self._refresh_ports)

        port_row = QHBoxLayout()
        port_row.addWidget(self._port_combo)
        port_row.addWidget(btn_refresh)
        serial_form.addRow("COM Port:", port_row)

        self._baud_combo = QComboBox()
        self._baud_combo.addItems(["9600", "57600", "115200", "230400"])
        self._baud_combo.setCurrentText("115200")
        serial_form.addRow("Baud Rate:", self._baud_combo)

        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(0.1, 10.0)
        self._timeout_spin.setValue(2.0)
        self._timeout_spin.setSuffix(" s")
        serial_form.addRow("Serial Timeout:", self._timeout_spin)
        left.addWidget(serial_group)

        # ---- Simulator ----
        sim_group = QGroupBox("SIMULATOR / BEAMNG")
        sim_form = QFormLayout(sim_group)

        self._bng_host_edit = QLineEdit("localhost")
        self._bng_port_spin = QSpinBox()
        self._bng_port_spin.setRange(1000, 65535)
        self._bng_port_spin.setValue(64256)

        self._auto_connect_cb = QCheckBox("Auto-connect on startup")
        sim_form.addRow("BeamNG Host:", self._bng_host_edit)
        sim_form.addRow("BeamNG Port:", self._bng_port_spin)
        sim_form.addRow("", self._auto_connect_cb)
        left.addWidget(sim_group)

        # ---- Update rates ----
        rates_group = QGroupBox("UPDATE RATES")
        rates_form = QFormLayout(rates_group)

        self._ui_rate_spin = QSpinBox()
        self._ui_rate_spin.setRange(1, 60)
        self._ui_rate_spin.setValue(10)
        self._ui_rate_spin.setSuffix(" Hz")

        self._telem_history_spin = QSpinBox()
        self._telem_history_spin.setRange(5, 60)
        self._telem_history_spin.setValue(15)
        self._telem_history_spin.setSuffix(" s")

        rates_form.addRow("UI Refresh Rate:", self._ui_rate_spin)
        rates_form.addRow("Chart History:", self._telem_history_spin)
        left.addWidget(rates_group)
        left.addStretch()

        # ---- Logging ----
        log_group = QGroupBox("LOGGING")
        log_form = QFormLayout(log_group)

        self._log_dir_edit = QLineEdit("output/logs")
        btn_browse_log = QPushButton("Browse")
        btn_browse_log.setFixedWidth(70)
        btn_browse_log.clicked.connect(self._browse_log_dir)
        log_dir_row = QHBoxLayout()
        log_dir_row.addWidget(self._log_dir_edit)
        log_dir_row.addWidget(btn_browse_log)
        log_form.addRow("Log Directory:", log_dir_row)

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._log_level_combo.setCurrentText("INFO")
        log_form.addRow("Log Level:", self._log_level_combo)
        right.addWidget(log_group)

        # ---- Safety ----
        safety_group = QGroupBox("SAFETY OPTIONS")
        safety_form = QFormLayout(safety_group)

        self._max_angle_spin = QDoubleSpinBox()
        self._max_angle_spin.setRange(90, 1080)
        self._max_angle_spin.setValue(540)
        self._max_angle_spin.setSuffix("°")

        self._max_motor_spin = QSpinBox()
        self._max_motor_spin.setRange(0, 255)
        self._max_motor_spin.setValue(200)

        self._max_ai_rate_spin = QDoubleSpinBox()
        self._max_ai_rate_spin.setRange(10, 1000)
        self._max_ai_rate_spin.setValue(180)
        self._max_ai_rate_spin.setSuffix(" °/s")

        self._watchdog_cb = QCheckBox("Enable AI watchdog timer")
        self._watchdog_cb.setChecked(True)

        safety_form.addRow("Max Angle Clamp:", self._max_angle_spin)
        safety_form.addRow("Max Motor PWM:", self._max_motor_spin)
        safety_form.addRow("Max AI Steer Rate:", self._max_ai_rate_spin)
        safety_form.addRow("", self._watchdog_cb)
        right.addWidget(safety_group)

        # ---- Save / Reload ----
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save Settings")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save_settings)
        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self._load_settings)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_reload)
        btn_row.addStretch()
        right.addWidget(QPushButton())  # spacer
        right.addStretch()
        self.content_layout.addLayout(btn_row)

    def _refresh_ports(self):
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItems(SerialManager.list_ports())
        if current:
            self._port_combo.setCurrentText(current)

    def _browse_log_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if d:
            self._log_dir_edit.setText(d)

    def _save_settings(self):
        if not self._config:
            return
        self._config.set("serial.port", self._port_combo.currentText())
        self._config.set("serial.baud", int(self._baud_combo.currentText()))
        self._config.set("serial.timeout", self._timeout_spin.value())
        self._config.set("beamng.host", self._bng_host_edit.text())
        self._config.set("beamng.port", self._bng_port_spin.value())
        self._config.set("beamng.auto_connect", self._auto_connect_cb.isChecked())
        self._config.set("ui.update_rate_hz", self._ui_rate_spin.value())
        self._config.set("logging.log_dir", self._log_dir_edit.text())
        self._config.set("logging.level", self._log_level_combo.currentText())
        if self._safety:
            self._safety.configure(
                max_angle=self._max_angle_spin.value(),
                max_motor=self._max_motor_spin.value(),
                max_ai_rate=self._max_ai_rate_spin.value(),
            )
        if self._log:
            self._log.info("Settings saved")

    def _load_settings(self):
        if not self._config:
            return
        port = self._config.get("serial.port", "")
        if port:
            self._port_combo.setCurrentText(port)
        self._baud_combo.setCurrentText(str(self._config.get("serial.baud", 115200)))
        self._timeout_spin.setValue(self._config.get("serial.timeout", 2.0))
        self._bng_host_edit.setText(self._config.get("beamng.host", "localhost"))
        self._bng_port_spin.setValue(self._config.get("beamng.port", 64256))
        self._auto_connect_cb.setChecked(self._config.get("beamng.auto_connect", False))
        self._ui_rate_spin.setValue(self._config.get("ui.update_rate_hz", 10))
        self._max_angle_spin.setValue(self._config.get("wheel.angle_range", 540))
        self._max_motor_spin.setValue(self._config.get("wheel.max_motor_output", 200))
