"""
desktop_app/pages/tuning_page.py — Motor and control tuning page.
Grouped sliders with safe ranges, tooltips, and save-to-profile.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QSlider, QDoubleSpinBox, QSpinBox, QScrollArea, QWidget, QFormLayout
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS


class TuningPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(
            title="Tuning",
            subtitle="Motor, PD controller, and effect strength tuning",
            **kwargs
        )
        self._spinboxes = {}
        self._build_content()

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

        # ---- PD Controller Gains ----
        pd_group = QGroupBox("PD CONTROLLER GAINS")
        pd_form = QFormLayout(pd_group)
        pd_form.setHorizontalSpacing(16)
        pd_form.setVerticalSpacing(8)

        self._add_param(pd_form, "KP (Proportional)", "kp", 0.0, 10.0, 1.8,
                        tooltip="Proportional gain. Higher = more aggressive correction.")
        self._add_param(pd_form, "KD (Derivative)", "kd", 0.0, 2.0, 0.12,
                        tooltip="Derivative gain. Reduces overshoot and oscillation.")
        self._add_param(pd_form, "KI (Integral)", "ki", 0.0, 1.0, 0.0,
                        tooltip="Integral gain. Use small values only if needed for steady-state error.")
        left.addWidget(pd_group)

        # ---- Motor Output Limits ----
        motor_group = QGroupBox("MOTOR OUTPUT LIMITS")
        motor_form = QFormLayout(motor_group)
        motor_form.setHorizontalSpacing(16)
        motor_form.setVerticalSpacing(8)

        self._add_param(motor_form, "Max Output (PWM)", "max_motor", 0, 255, 200, decimals=0,
                        tooltip="Absolute PWM ceiling. 255 = full power. Start low.")
        self._add_param(motor_form, "Slew Rate Limit (°/s)", "slew_rate", 0, 1000, 500, decimals=0,
                        tooltip="Max rate of change for target angle. Prevents violent movement.")
        self._add_param(motor_form, "Dead Zone (°)", "dead_zone", 0, 20, 1.5,
                        tooltip="Angle dead zone. Motor off when error < dead zone.")
        left.addWidget(motor_group)

        # ---- Angle Range ----
        range_group = QGroupBox("ANGLE RANGE & CLAMPS")
        range_form = QFormLayout(range_group)
        range_form.setHorizontalSpacing(16)
        range_form.setVerticalSpacing(8)

        self._add_param(range_form, "Steering Range (°)", "angle_range", 90, 1080, 540, decimals=0,
                        tooltip="Total rotation range. 540 = ±270°.")
        self._add_param(range_form, "Soft Limit (°)", "soft_limit", 90, 1080, 500, decimals=0,
                        tooltip="Software angle clamp. Motor output reduces near this limit.")
        left.addWidget(range_group)
        left.addStretch()

        # ---- FFB Effects ----
        ffb_group = QGroupBox("FORCE FEEDBACK EFFECTS")
        ffb_form = QFormLayout(ffb_group)
        ffb_form.setHorizontalSpacing(16)
        ffb_form.setVerticalSpacing(8)

        self._add_param(ffb_form, "Centering Strength", "centering", 0.0, 3.0, 1.0,
                        tooltip="Spring-center strength in ASSIST mode.")
        self._add_param(ffb_form, "Damping", "damping", 0.0, 1.0, 0.12,
                        tooltip="Velocity-proportional resistance.")
        self._add_param(ffb_form, "Friction", "friction", 0.0, 1.0, 0.05,
                        tooltip="Constant rotational resistance.")
        self._add_param(ffb_form, "Inertia", "inertia", 0.0, 1.0, 0.05,
                        tooltip="Acceleration-proportional resistance.")
        self._add_param(ffb_form, "Output Smoothing", "smoothing", 0.0, 1.0, 0.10,
                        tooltip="Low-pass filter on output (0 = off, 1 = max smooth).")
        right.addWidget(ffb_group)

        # ---- Apply / Revert ----
        btn_group = QGroupBox("APPLY")
        btn_layout = QHBoxLayout(btn_group)
        btn_apply = QPushButton("Apply to Device")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self._apply)

        btn_revert = QPushButton("Revert Changes")
        btn_revert.clicked.connect(self._revert)

        btn_save = QPushButton("Save to Profile")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self._save_profile)

        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_revert)
        btn_layout.addWidget(btn_save)
        right.addWidget(btn_group)

        # Tuning notes
        notes = QLabel(
            "💡  Recommended starting values: KP=1.8, KD=0.12, Max=200.\n"
            "    Increase KP for faster response. Increase KD to reduce bouncing.\n"
            "    Keep KI at 0 unless you see persistent steady-state angle error."
        )
        notes.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            f"background: {COLORS['bg_panel']}; padding: 10px; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        notes.setWordWrap(True)
        right.addWidget(notes)
        right.addStretch()

    def _add_param(self, form_layout, label: str, key: str,
                   min_v: float, max_v: float, default: float,
                   decimals: int = 2, tooltip: str = ""):
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        if tooltip:
            lbl.setToolTip(tooltip)

        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(default)
        sb.setDecimals(decimals)
        sb.setFixedWidth(100)
        if tooltip:
            sb.setToolTip(tooltip)

        form_layout.addRow(lbl, sb)
        self._spinboxes[key] = sb

    def _apply(self):
        if not self._serial or not self._serial.is_connected:
            return
        # Send applicable config values to device
        self._serial.set_config("angle_range", self._spinboxes["angle_range"].value())

    def _revert(self):
        """Reload values from config."""
        if self._config:
            self._spinboxes["angle_range"].setValue(self._config.get("wheel.angle_range", 540))
            self._spinboxes["max_motor"].setValue(self._config.get("wheel.max_motor_output", 200))
            self._spinboxes["centering"].setValue(self._config.get("wheel.centering_strength", 1.0))
            self._spinboxes["damping"].setValue(self._config.get("wheel.damping", 0.12))
            self._spinboxes["friction"].setValue(self._config.get("wheel.friction", 0.05))

    def _save_profile(self):
        if self._config:
            self._config.set("wheel.angle_range", self._spinboxes["angle_range"].value())
            self._config.set("wheel.max_motor_output", int(self._spinboxes["max_motor"].value()))
            self._config.set("wheel.centering_strength", self._spinboxes["centering"].value())
            self._config.set("wheel.damping", self._spinboxes["damping"].value())
            self._config.set("wheel.friction", self._spinboxes["friction"].value())
            self._config.set("wheel.inertia", self._spinboxes["inertia"].value())
            self._config.set("wheel.smoothing", self._spinboxes["smoothing"].value())
            if self._log:
                self._log.info("Tuning settings saved to config")
