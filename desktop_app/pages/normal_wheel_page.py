"""
desktop_app/pages/normal_wheel_page.py — Normal Wheel Mode page.
Controls for standard wheel operation: range, centering, FFB tuning, HID status.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QGridLayout, QSlider, QDoubleSpinBox, QCheckBox, QFrame,
    QScrollArea, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS


def _labeled_slider(label: str, min_val: float, max_val: float,
                    default: float, unit: str = "",
                    tooltip: str = "") -> tuple:
    """Returns (container_widget, slider, spinbox)."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    lbl = QLabel(label)
    lbl.setFixedWidth(170)
    lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
    if tooltip:
        lbl.setToolTip(tooltip)

    slider = QSlider(Qt.Orientation.Horizontal)
    scale = 10 if max_val <= 10 else 1
    slider.setRange(int(min_val * scale), int(max_val * scale))
    slider.setValue(int(default * scale))

    spinbox = QDoubleSpinBox()
    spinbox.setRange(min_val, max_val)
    spinbox.setValue(default)
    spinbox.setSuffix(f" {unit}" if unit else "")
    spinbox.setDecimals(1 if scale == 10 else 0)
    spinbox.setFixedWidth(80)

    # Sync slider ↔ spinbox
    def slider_changed(v):
        spinbox.blockSignals(True)
        spinbox.setValue(v / scale)
        spinbox.blockSignals(False)

    def spin_changed(v):
        slider.blockSignals(True)
        slider.setValue(int(v * scale))
        slider.blockSignals(False)

    slider.valueChanged.connect(slider_changed)
    spinbox.valueChanged.connect(spin_changed)

    layout.addWidget(lbl)
    layout.addWidget(slider, 1)
    layout.addWidget(spinbox)

    return container, slider, spinbox


class NormalWheelPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Normal Wheel Mode",
            subtitle="Section B — Standard wheel operation and FFB settings",
            **kwargs
        )
        self._build_content()

    def _build_content(self):
        # Scroll area for the whole page
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: transparent; }}"
        )
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QHBoxLayout(inner)
        inner_layout.setSpacing(16)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(inner)
        self.content_layout.addWidget(scroll)

        left = QVBoxLayout()
        right = QVBoxLayout()
        inner_layout.addLayout(left, 1)
        inner_layout.addLayout(right, 1)

        # ---- Wheel enable / mode ----
        mode_group = QGroupBox("WHEEL CONTROL")
        mode_layout = QVBoxLayout(mode_group)

        mode_btn_row = QHBoxLayout()
        self._btn_enable = QPushButton("Enable Wheel")
        self._btn_enable.setObjectName("btn_success")
        self._btn_enable.clicked.connect(self._on_enable)

        self._btn_idle = QPushButton("Set Idle")
        self._btn_idle.clicked.connect(lambda: self._set_mode("IDLE"))

        self._btn_hid = QPushButton("HID Mode")
        self._btn_hid.clicked.connect(lambda: self._set_mode("NORMAL_HID"))

        self._btn_assist = QPushButton("Assist Mode")
        self._btn_assist.clicked.connect(lambda: self._set_mode("ASSIST"))

        mode_btn_row.addWidget(self._btn_enable)
        mode_btn_row.addWidget(self._btn_idle)
        mode_btn_row.addWidget(self._btn_hid)
        mode_btn_row.addWidget(self._btn_assist)
        mode_layout.addLayout(mode_btn_row)

        # Status indicators
        status_row = QHBoxLayout()
        self._hid_status_lbl = QLabel("HID: Unknown")
        self._hid_status_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        self._mode_status_lbl = QLabel("Mode: IDLE")
        self._mode_status_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        status_row.addWidget(self._hid_status_lbl)
        status_row.addStretch()
        status_row.addWidget(self._mode_status_lbl)
        mode_layout.addLayout(status_row)
        left.addWidget(mode_group)

        # ---- Steering range ----
        range_group = QGroupBox("STEERING RANGE")
        range_layout = QVBoxLayout(range_group)

        range_w, self._range_slider, self._range_spin = _labeled_slider(
            "Steering Range (total)", 90, 1080, 540, "°",
            "Total steering range in degrees (e.g., 540 = ±270°)"
        )
        range_layout.addWidget(range_w)

        self._invert_motor_cb = QCheckBox("Invert Motor Direction")
        self._invert_enc_cb   = QCheckBox("Invert Encoder Direction")
        range_layout.addWidget(self._invert_motor_cb)
        range_layout.addWidget(self._invert_enc_cb)
        left.addWidget(range_group)

        # ---- FFB / Force tuning ----
        ffb_group = QGroupBox("FORCE FEEDBACK / MOTOR TUNING")
        ffb_layout = QVBoxLayout(ffb_group)

        ffb_params = [
            ("Max Motor Output",  0, 255, 200, "", "Maximum PWM output (0-255). Lower = softer."),
            ("Centering Strength", 0, 3.0, 1.0, "", "How strongly the wheel returns to center."),
            ("Damping",           0, 1.0, 0.12, "", "Resistance to rotation. Reduces oscillation."),
            ("Friction",          0, 1.0, 0.05, "", "Constant resistance. Simulates steering feel."),
            ("Inertia",           0, 1.0, 0.05, "", "Resistance to speed changes."),
            ("Smoothing",         0, 1.0, 0.10, "", "Steering output smoothing filter (0=off)."),
        ]

        self._ffb_spinboxes = {}
        for label, min_v, max_v, default, unit, tip in ffb_params:
            w, sl, sb = _labeled_slider(label, min_v, max_v, default, unit, tip)
            ffb_layout.addWidget(w)
            self._ffb_spinboxes[label] = sb

        left.addWidget(ffb_group)
        left.addStretch()

        # ---- Live angle display ----
        live_group = QGroupBox("LIVE WHEEL INPUT")
        live_layout = QVBoxLayout(live_group)

        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("Current Angle:"))
        self._live_angle = QLabel("0.0°")
        self._live_angle.setObjectName("value_large")
        self._live_angle.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 28px; "
            f"font-weight: 700; font-family: Consolas;"
        )
        angle_row.addWidget(self._live_angle)
        angle_row.addStretch()
        live_layout.addLayout(angle_row)

        # Simple ASCII-style angle bar
        self._angle_bar = QLabel("CENTER")
        self._angle_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._angle_bar.setFixedHeight(30)
        self._angle_bar.setStyleSheet(
            f"background-color: {COLORS['bg_widget']}; "
            f"color: {COLORS['accent_blue']}; "
            f"font-family: Consolas; font-size: 13px; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        live_layout.addWidget(self._angle_bar)
        right.addWidget(live_group)

        # ---- Write / restore ----
        apply_group = QGroupBox("APPLY SETTINGS")
        apply_layout = QHBoxLayout(apply_group)

        btn_write = QPushButton("Write Settings to Device")
        btn_write.setObjectName("btn_primary")
        btn_write.clicked.connect(self._write_settings)

        btn_defaults = QPushButton("Restore Safe Defaults")
        btn_defaults.clicked.connect(self._restore_defaults)

        apply_layout.addWidget(btn_write)
        apply_layout.addWidget(btn_defaults)
        apply_layout.addStretch()
        right.addWidget(apply_group)

        # ---- Encoder health ----
        enc_group = QGroupBox("ENCODER HEALTH")
        enc_layout = QGridLayout(enc_group)
        enc_layout.setHorizontalSpacing(16)

        for row_i, (lbl_txt, attr) in enumerate([
            ("Encoder Counts", "_enc_counts"),
            ("Serial Health",  "_serial_health"),
            ("Telemetry Age",  "_telem_age"),
        ]):
            lbl = QLabel(lbl_txt + ":")
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
            val = QLabel("—")
            val.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas;")
            enc_layout.addWidget(lbl, row_i, 0)
            enc_layout.addWidget(val, row_i, 1)
            setattr(self, attr, val)

        right.addWidget(enc_group)
        right.addStretch()

    def _set_mode(self, mode: str):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode(mode)

    def _on_enable(self):
        self._set_mode("NORMAL_HID")

    def _write_settings(self):
        if not self._serial or not self._serial.is_connected:
            return
        angle_range = self._range_spin.value()
        self._serial.set_config("angle_range", angle_range)
        if self._config:
            self._config.set("wheel.angle_range", angle_range)
            self._config.set("wheel.max_motor_output",
                             int(self._ffb_spinboxes["Max Motor Output"].value()))

    def _restore_defaults(self):
        self._range_spin.setValue(540.0)
        self._ffb_spinboxes["Max Motor Output"].setValue(200)
        self._ffb_spinboxes["Centering Strength"].setValue(1.0)
        self._ffb_spinboxes["Damping"].setValue(0.12)
        self._ffb_spinboxes["Friction"].setValue(0.05)
        self._ffb_spinboxes["Inertia"].setValue(0.05)
        self._ffb_spinboxes["Smoothing"].setValue(0.10)

    def refresh(self):
        telem = self._telemetry.latest if self._telemetry else None
        if telem:
            self._live_angle.setText(f"{telem.angle:.1f}°")
            self._mode_status_lbl.setText(f"Mode: {telem.mode}")
            self._enc_counts.setText(str(telem.enc))

            # Simple angle bar: map ±540° to progress text
            half = 540.0
            pct = max(-1.0, min(1.0, telem.angle / half))
            bar_len = 30
            center = bar_len // 2
            pos = center + int(pct * center)
            bar = ["-"] * bar_len
            bar[center] = "|"
            pos = max(0, min(bar_len - 1, pos))
            bar[pos] = "●"
            self._angle_bar.setText("".join(bar))

        if self._serial:
            if self._serial.is_connected:
                self._serial_health.setText("Connected")
                self._serial_health.setStyleSheet(f"color: {COLORS['accent_green']}; font-family: Consolas;")
            else:
                self._serial_health.setText("Disconnected")
                self._serial_health.setStyleSheet(f"color: {COLORS['text_dim']}; font-family: Consolas;")

        if self._telemetry:
            age = self._telemetry.age_seconds
            if age == float("inf"):
                self._telem_age.setText("No data")
            else:
                self._telem_age.setText(f"{age:.1f}s ago")
