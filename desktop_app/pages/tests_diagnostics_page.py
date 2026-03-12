"""
desktop_app/pages/tests_diagnostics_page.py — Tests & Diagnostics page.
Serial, motor, encoder, sweep, and telemetry stream tests.
"""
import json
import time
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QTextEdit, QProgressBar, QFormLayout, QDoubleSpinBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QTimer
from pages.base_page import BasePage
from ui.styles import COLORS


class TestsDiagnosticsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Tests & Diagnostics",
            subtitle="Serial, encoder, motor, and telemetry diagnostics",
            **kwargs
        )
        self._build_content()
        self._sweep_timer = QTimer()
        self._sweep_timer.timeout.connect(self._sweep_tick)
        self._sweep_angle = 0.0
        self._sweep_dir = 1
        self._sweep_step = 5.0
        self._sweep_max = 90.0

    def _build_content(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QHBoxLayout(inner)
        inner_layout.setSpacing(16)
        scroll.setWidget(inner)
        self.content_layout.addWidget(scroll)

        left = QVBoxLayout()
        right = QVBoxLayout()
        inner_layout.addLayout(left, 1)
        inner_layout.addLayout(right, 1)

        # ---- Serial communication test ----
        serial_group = QGroupBox("SERIAL COMMUNICATION TEST")
        serial_layout = QVBoxLayout(serial_group)

        btn_row = QHBoxLayout()
        btn_ping = QPushButton("Send Ping")
        btn_ping.clicked.connect(self._test_ping)
        btn_ver = QPushButton("Get Firmware Version")
        btn_ver.clicked.connect(self._test_version)
        btn_telem = QPushButton("Request Telemetry")
        btn_telem.clicked.connect(self._test_telem)
        btn_row.addWidget(btn_ping)
        btn_row.addWidget(btn_ver)
        btn_row.addWidget(btn_telem)
        serial_layout.addLayout(btn_row)

        self._serial_status_lbl = QLabel("Not tested")
        self._serial_status_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        serial_layout.addWidget(self._serial_status_lbl)
        left.addWidget(serial_group)

        # ---- Angle step test ----
        step_group = QGroupBox("ANGLE STEP TEST")
        step_layout = QVBoxLayout(step_group)
        step_form = QFormLayout()

        self._step_angle_spin = QDoubleSpinBox()
        self._step_angle_spin.setRange(-270, 270)
        self._step_angle_spin.setValue(30.0)
        self._step_angle_spin.setSuffix("°")
        step_form.addRow("Step Angle:", self._step_angle_spin)
        step_layout.addLayout(step_form)

        step_btn_row = QHBoxLayout()
        btn_step_pos = QPushButton("Step Positive")
        btn_step_pos.clicked.connect(lambda: self._step_test(1))
        btn_step_neg = QPushButton("Step Negative")
        btn_step_neg.clicked.connect(lambda: self._step_test(-1))
        btn_step_zero = QPushButton("Return to 0°")
        btn_step_zero.clicked.connect(lambda: self._send_target(0.0))
        step_btn_row.addWidget(btn_step_pos)
        step_btn_row.addWidget(btn_step_neg)
        step_btn_row.addWidget(btn_step_zero)
        step_layout.addLayout(step_btn_row)
        left.addWidget(step_group)

        # ---- Sweep test ----
        sweep_group = QGroupBox("SWEEP TEST")
        sweep_layout = QVBoxLayout(sweep_group)
        sweep_form = QFormLayout()

        self._sweep_max_spin = QDoubleSpinBox()
        self._sweep_max_spin.setRange(10, 270)
        self._sweep_max_spin.setValue(90.0)
        self._sweep_max_spin.setSuffix("°")

        self._sweep_speed_spin = QDoubleSpinBox()
        self._sweep_speed_spin.setRange(1, 50)
        self._sweep_speed_spin.setValue(5.0)
        self._sweep_speed_spin.setSuffix("°/step")

        sweep_form.addRow("Sweep Range:", self._sweep_max_spin)
        sweep_form.addRow("Speed:", self._sweep_speed_spin)
        sweep_layout.addLayout(sweep_form)

        sweep_btn_row = QHBoxLayout()
        self._btn_sweep_start = QPushButton("Start Sweep")
        self._btn_sweep_start.setObjectName("btn_primary")
        self._btn_sweep_start.clicked.connect(self._start_sweep)
        btn_sweep_stop = QPushButton("Stop Sweep")
        btn_sweep_stop.clicked.connect(self._stop_sweep)
        sweep_btn_row.addWidget(self._btn_sweep_start)
        sweep_btn_row.addWidget(btn_sweep_stop)
        sweep_layout.addLayout(sweep_btn_row)

        self._sweep_bar = QProgressBar()
        self._sweep_bar.setRange(-100, 100)
        self._sweep_bar.setValue(0)
        self._sweep_bar.setTextVisible(True)
        sweep_layout.addWidget(self._sweep_bar)
        left.addWidget(sweep_group)
        left.addStretch()

        # ---- Encoder sanity test ----
        enc_group = QGroupBox("ENCODER SANITY TEST")
        enc_layout = QVBoxLayout(enc_group)
        enc_layout.addWidget(QLabel("Turn the wheel manually. Encoder counts should change."))

        enc_form = QFormLayout()
        self._enc_count_lbl = QLabel("0")
        self._enc_count_lbl.setStyleSheet(f"color: {COLORS['accent_blue']}; font-family: Consolas; font-size: 16px;")
        self._enc_angle_lbl = QLabel("0.0°")
        self._enc_angle_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas; font-size: 16px;")
        enc_form.addRow("Encoder Counts:", self._enc_count_lbl)
        enc_form.addRow("Calculated Angle:", self._enc_angle_lbl)
        enc_layout.addLayout(enc_form)
        right.addWidget(enc_group)

        # ---- Fault viewer ----
        fault_group = QGroupBox("FAULT VIEWER")
        fault_layout = QVBoxLayout(fault_group)
        self._fault_lbl = QLabel("No faults")
        self._fault_lbl.setStyleSheet(f"color: {COLORS['accent_green']};")
        fault_layout.addWidget(self._fault_lbl)

        btn_clear_faults = QPushButton("Clear Faults")
        btn_clear_faults.clicked.connect(self._clear_faults)
        fault_layout.addWidget(btn_clear_faults)
        right.addWidget(fault_group)

        # ---- Output log ----
        log_group = QGroupBox("DIAGNOSTIC OUTPUT")
        log_layout = QVBoxLayout(log_group)
        self._diag_log = QTextEdit()
        self._diag_log.setReadOnly(True)
        self._diag_log.setMinimumHeight(160)
        self._diag_log.setStyleSheet(
            f"font-family: Consolas; font-size: 11px; "
            f"background: {COLORS['bg_dark']}; border: none;"
        )

        btn_log_row = QHBoxLayout()
        btn_export = QPushButton("Export Diagnostic Report")
        btn_export.clicked.connect(self._export_report)
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self._diag_log.clear)
        btn_log_row.addWidget(btn_export)
        btn_log_row.addWidget(btn_clear_log)

        log_layout.addWidget(self._diag_log)
        log_layout.addLayout(btn_log_row)
        right.addWidget(log_group)
        right.addStretch()

        # Connect raw serial output to log
        if self._serial:
            self._serial.raw_line.connect(self._on_raw_line)

    def _log(self, msg: str):
        self._diag_log.append(f"  {msg}")

    def _on_raw_line(self, line: str):
        self._log(f"<< {line}")

    def _test_ping(self):
        if self._serial and self._serial.is_connected:
            self._serial.ping()
            self._serial_status_lbl.setText("Ping sent — watch output below")
            self._serial_status_lbl.setStyleSheet(f"color: {COLORS['accent_blue']};")
        else:
            self._serial_status_lbl.setText("Not connected")
            self._serial_status_lbl.setStyleSheet(f"color: {COLORS['accent_red']};")

    def _test_version(self):
        if self._serial and self._serial.is_connected:
            self._serial.get_version()

    def _test_telem(self):
        if self._serial and self._serial.is_connected:
            self._serial.send_command({"cmd": "get_telemetry"})

    def _step_test(self, direction: int):
        angle = self._step_angle_spin.value() * direction
        self._send_target(angle)

    def _send_target(self, angle: float):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode("ANGLE_TRACK")
            self._serial.set_target(angle)
            self._log(f">> Target: {angle:.1f}°")

    def _start_sweep(self):
        self._sweep_max = self._sweep_max_spin.value()
        self._sweep_step = self._sweep_speed_spin.value()
        self._sweep_angle = 0.0
        self._sweep_dir = 1
        if self._serial and self._serial.is_connected:
            self._serial.set_mode("ANGLE_TRACK")
            self._sweep_timer.start(100)
            self._log("Sweep test started")

    def _stop_sweep(self):
        self._sweep_timer.stop()
        if self._serial and self._serial.is_connected:
            self._serial.set_target(0.0)
        self._sweep_bar.setValue(0)
        self._log("Sweep test stopped")

    def _sweep_tick(self):
        self._sweep_angle += self._sweep_step * self._sweep_dir
        if self._sweep_angle >= self._sweep_max:
            self._sweep_angle = self._sweep_max
            self._sweep_dir = -1
        elif self._sweep_angle <= -self._sweep_max:
            self._sweep_angle = -self._sweep_max
            self._sweep_dir = 1

        if self._serial and self._serial.is_connected:
            self._serial.set_target(self._sweep_angle)

        pct = int((self._sweep_angle / self._sweep_max) * 100)
        self._sweep_bar.setValue(pct)

    def _clear_faults(self):
        if self._serial and self._serial.is_connected:
            self._serial.clear_faults()
            self._log("Faults cleared")

    def _export_report(self):
        import os
        telem = self._telemetry.latest if self._telemetry else None
        report_lines = [
            "=== SelfDriveBeamNGTech Diagnostic Report ===",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Serial connected: {self._serial.is_connected if self._serial else False}",
            f"Firmware version: {self._serial.fw_version if self._serial else 'N/A'}",
        ]
        if telem:
            report_lines += [
                f"Angle: {telem.angle:.2f}°",
                f"Target: {telem.target:.2f}°",
                f"Motor: {telem.motor}",
                f"Mode: {telem.mode}",
                f"Faults: {telem.fault} ({telem.fault_names()})",
            ]

        report_txt = "\n".join(report_lines)
        report_path = os.path.join("output", "logs", f"diag_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(report_txt)
        self._log(f"Report exported: {report_path}")

    def refresh(self):
        telem = self._telemetry.latest if self._telemetry else None
        if telem:
            self._enc_count_lbl.setText(str(telem.enc))
            self._enc_angle_lbl.setText(f"{telem.angle:.2f}°")
            if telem.has_fault():
                names = ", ".join(telem.fault_names())
                self._fault_lbl.setText(f"FAULT: {names}")
                self._fault_lbl.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: 700;")
            else:
                self._fault_lbl.setText("No faults")
                self._fault_lbl.setStyleSheet(f"color: {COLORS['accent_green']};")
