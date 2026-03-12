"""
desktop_app/pages/calibration_page.py — Wheel calibration wizard.
Guides user through encoder zeroing, center set, and range detection.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit, QFormLayout
)
from PySide6.QtCore import Qt, QTimer
from pages.base_page import BasePage
from ui.styles import COLORS


class CalibrationPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Calibration",
            subtitle="Encoder zeroing, center set, range setup, and motor direction",
            **kwargs
        )
        self._build_content()

    def _build_content(self):
        main_h = QHBoxLayout()
        main_h.setSpacing(16)
        self.content_layout.addLayout(main_h)
        self.content_layout.addStretch()

        left = QVBoxLayout()
        right = QVBoxLayout()
        main_h.addLayout(left, 1)
        main_h.addLayout(right, 1)

        # ---- Live readout ----
        live_group = QGroupBox("LIVE READOUT")
        live_layout = QFormLayout(live_group)

        self._cal_angle_lbl = QLabel("0.0°")
        self._cal_angle_lbl.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 24px; "
            f"font-weight: 700; font-family: Consolas;"
        )
        self._cal_enc_lbl = QLabel("0")
        self._cal_enc_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas;")
        self._cal_mode_lbl = QLabel("IDLE")
        self._cal_mode_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-family: Consolas;")

        live_layout.addRow("Current Angle:", self._cal_angle_lbl)
        live_layout.addRow("Encoder Counts:", self._cal_enc_lbl)
        live_layout.addRow("Device Mode:", self._cal_mode_lbl)
        left.addWidget(live_group)

        # ---- Step 1: Enter calibration mode ----
        step1_group = QGroupBox("STEP 1 — Enter Calibration Mode")
        step1_layout = QVBoxLayout(step1_group)
        btn_cal_mode = QPushButton("Enter Calibration Mode")
        btn_cal_mode.setObjectName("btn_primary")
        btn_cal_mode.clicked.connect(lambda: self._send_cmd("CALIBRATION"))
        step1_layout.addWidget(btn_cal_mode)
        step1_layout.addWidget(QLabel(
            "Puts the device into CALIBRATION mode — motors off, safe to turn the wheel."
        ))
        left.addWidget(step1_group)

        # ---- Step 2: Encoder zero ----
        step2_group = QGroupBox("STEP 2 — Zero Encoder")
        step2_layout = QVBoxLayout(step2_group)
        btn_zero = QPushButton("Zero Encoder (current = 0)")
        btn_zero.clicked.connect(self._zero_encoder)
        step2_layout.addWidget(btn_zero)
        step2_layout.addWidget(QLabel("Turn wheel to desired zero position, then click."))
        left.addWidget(step2_group)

        # ---- Step 3: Set center ----
        step3_group = QGroupBox("STEP 3 — Set Center Position")
        step3_layout = QVBoxLayout(step3_group)
        btn_center = QPushButton("Set This Position as Center (0°)")
        btn_center.clicked.connect(self._set_center)
        step3_layout.addWidget(btn_center)
        step3_layout.addWidget(QLabel("Hold wheel straight, then click."))
        left.addWidget(step3_group)
        left.addStretch()

        # ---- Step 4: Range setup ----
        step4_group = QGroupBox("STEP 4 — Range & Counts-per-Rev Setup")
        step4_form = QFormLayout(step4_group)

        self._cpr_spin = QSpinBox()
        self._cpr_spin.setRange(100, 100000)
        self._cpr_spin.setValue(2400)
        self._cpr_spin.setToolTip("Encoder counts per full revolution (4× quadrature CPR)")

        self._gear_spin = QDoubleSpinBox()
        self._gear_spin.setRange(0.1, 20.0)
        self._gear_spin.setValue(1.0)
        self._gear_spin.setDecimals(2)
        self._gear_spin.setToolTip("Motor-to-steering-shaft gear ratio")

        self._range_spin = QDoubleSpinBox()
        self._range_spin.setRange(90, 1080)
        self._range_spin.setValue(540)
        self._range_spin.setSuffix("°")
        self._range_spin.setToolTip("Physical rotation limit of the wheel")

        step4_form.addRow("Counts per Revolution:", self._cpr_spin)
        step4_form.addRow("Gear Ratio:", self._gear_spin)
        step4_form.addRow("Steering Range:", self._range_spin)

        btn_apply_range = QPushButton("Apply Range Settings")
        btn_apply_range.setObjectName("btn_success")
        btn_apply_range.clicked.connect(self._apply_range)
        step4_form.addRow("", btn_apply_range)
        right.addWidget(step4_group)

        # ---- Step 5: Motor direction check ----
        step5_group = QGroupBox("STEP 5 — Motor Direction Test")
        step5_layout = QVBoxLayout(step5_group)
        step5_layout.addWidget(QLabel(
            "Set IDLE mode, then manually set a small target angle to test motor direction."
        ))

        dir_row = QHBoxLayout()
        btn_test_left = QPushButton("Test Left (-15°)")
        btn_test_left.clicked.connect(lambda: self._test_angle(-15))
        btn_test_right = QPushButton("Test Right (+15°)")
        btn_test_right.clicked.connect(lambda: self._test_angle(15))
        btn_center_w = QPushButton("Return to 0°")
        btn_center_w.clicked.connect(lambda: self._test_angle(0))

        dir_row.addWidget(btn_test_left)
        dir_row.addWidget(btn_test_right)
        dir_row.addWidget(btn_center_w)
        step5_layout.addLayout(dir_row)

        self._invert_motor_cb = QCheckBox("Invert motor direction if rotation is backwards")
        step5_layout.addWidget(self._invert_motor_cb)
        right.addWidget(step5_group)

        # ---- Calibration log ----
        log_group = QGroupBox("CALIBRATION LOG")
        log_layout = QVBoxLayout(log_group)
        self._cal_log = QTextEdit()
        self._cal_log.setReadOnly(True)
        self._cal_log.setMaximumHeight(140)
        self._cal_log.setStyleSheet(
            f"font-family: Consolas; font-size: 11px; "
            f"background: {COLORS['bg_dark']}; border: none;"
        )
        log_layout.addWidget(self._cal_log)

        btn_row = QHBoxLayout()
        btn_save_cal = QPushButton("Save Calibration")
        btn_save_cal.setObjectName("btn_primary")
        btn_save_cal.clicked.connect(self._save_calibration)
        btn_row.addWidget(btn_save_cal)
        btn_row.addStretch()
        log_layout.addLayout(btn_row)
        right.addWidget(log_group)
        right.addStretch()

    def _send_cmd(self, mode: str):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode(mode)
            self._log_cal(f"Mode set to {mode}")

    def _zero_encoder(self):
        if self._serial and self._serial.is_connected:
            self._serial.zero_encoder()
            self._log_cal("Encoder zeroed")

    def _set_center(self):
        if self._serial and self._serial.is_connected:
            self._serial.set_center()
            self._log_cal("Center position set")

    def _test_angle(self, angle: float):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode("ANGLE_TRACK")
            self._serial.set_target(angle)
            self._log_cal(f"Test target: {angle}°")

    def _apply_range(self):
        if self._config:
            self._config.set("wheel.counts_per_rev", self._cpr_spin.value())
            self._config.set("wheel.gear_ratio", self._gear_spin.value())
            self._config.set("wheel.angle_range", self._range_spin.value())
        if self._serial and self._serial.is_connected:
            self._serial.set_config("angle_range", self._range_spin.value())
        self._log_cal(
            f"Range applied: CPR={self._cpr_spin.value()}, "
            f"Gear={self._gear_spin.value():.2f}, "
            f"Range={self._range_spin.value()}°"
        )

    def _save_calibration(self):
        if self._config:
            self._config.save()
        self._log_cal("Calibration saved to config")

    def _log_cal(self, msg: str):
        self._cal_log.append(f"  > {msg}")

    def refresh(self):
        telem = self._telemetry.latest if self._telemetry else None
        if telem:
            self._cal_angle_lbl.setText(f"{telem.angle:.2f}°")
            self._cal_enc_lbl.setText(str(telem.enc))
            self._cal_mode_lbl.setText(telem.mode)
