"""
desktop_app/pages/tuning_page.py — Tuning: KP/KD/KI + motor limits + apply.
Simple form layout — no nested groups.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QSpinBox, QFormLayout, QFrame
)
from pages.base_page import BasePage
from ui.styles import COLORS


class TuningPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Tuning", **kwargs)
        self._sb = {}
        self._build()

    def _build(self):
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)
        self.content_layout.addLayout(form)

        from PySide6.QtCore import Qt
        form.setLabelAlignment(Qt.AlignRight)

        def row(key, label, mn, mx, default, decimals=2, suffix="", tip=""):
            sb = QDoubleSpinBox()
            sb.setRange(mn, mx)
            sb.setValue(default)
            sb.setDecimals(decimals)
            sb.setFixedWidth(100)
            if suffix:
                sb.setSuffix(f" {suffix}")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{COLORS['text_secondary']};")
            if tip:
                lbl.setToolTip(tip)
                sb.setToolTip(tip)
            form.addRow(lbl, sb)
            self._sb[key] = sb

        # PD gains
        sep_lbl = QLabel("─── PD Controller ───")
        sep_lbl.setStyleSheet(f"color:{COLORS['text_dim']};font-size:11px;")
        form.addRow(sep_lbl)

        row("kp", "KP  (Proportional)", 0, 10, 1.8, tip="Higher = faster correction, more aggressive")
        row("kd", "KD  (Derivative)",   0, 2,  0.12, tip="Higher = less overshoot")
        row("ki", "KI  (Integral)",     0, 1,  0.0,  tip="Use only to fix steady-state error")

        form.addRow(self._sep())

        # Motor
        sep_lbl2 = QLabel("─── Motor ───")
        sep_lbl2.setStyleSheet(f"color:{COLORS['text_dim']};font-size:11px;")
        form.addRow(sep_lbl2)

        row("max_motor",  "Max PWM Output",   0, 255, 200, decimals=0, tip="Absolute PWM ceiling (255 = full power)")
        row("dead_zone",  "Dead Zone",        0, 20,  1.5, tip="No output when error is smaller than this")
        row("angle_range","Steering Range",   90, 1080, 540, decimals=0, suffix="°", tip="Total rotation range")

        form.addRow(self._sep())

        # FFB
        sep_lbl3 = QLabel("─── FFB Effects ───")
        sep_lbl3.setStyleSheet(f"color:{COLORS['text_dim']};font-size:11px;")
        form.addRow(sep_lbl3)

        row("centering",  "Centering",        0, 3.0, 1.0,  tip="Spring-center strength")
        row("damping",    "Damping",          0, 1.0, 0.12, tip="Velocity-proportional resistance")
        row("friction",   "Friction",         0, 1.0, 0.05, tip="Constant rotational resistance")
        row("smoothing",  "Smoothing",        0, 1.0, 0.10, tip="Output low-pass filter (0 = off)")

        self.content_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply to Device")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self._apply)
        btn_save = QPushButton("Save to Config")
        btn_save.clicked.connect(self._save)
        btn_revert = QPushButton("Revert")
        btn_revert.clicked.connect(self._revert)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_revert)
        btn_row.addStretch()
        self.content_layout.addLayout(btn_row)

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"background:{COLORS['border']};max-height:1px;")
        return f

    def _apply(self):
        if self._serial and self._serial.is_connected:
            self._serial.set_config("angle_range", self._sb["angle_range"].value())

    def _save(self):
        if not self._config:
            return
        for k, conf_key in [
            ("kp", None), ("kd", None), ("ki", None),
            ("angle_range", "wheel.angle_range"),
            ("max_motor", "wheel.max_motor_output"),
            ("centering", "wheel.centering_strength"),
            ("damping", "wheel.damping"),
            ("friction", "wheel.friction"),
            ("smoothing", "wheel.smoothing"),
        ]:
            if conf_key:
                self._config.set(conf_key, self._sb[k].value())
        if self._log:
            self._log.info("Tuning saved")

    def _revert(self):
        if not self._config:
            return
        self._sb["angle_range"].setValue(self._config.get("wheel.angle_range", 540))
        self._sb["max_motor"].setValue(self._config.get("wheel.max_motor_output", 200))
        self._sb["centering"].setValue(self._config.get("wheel.centering_strength", 1.0))
        self._sb["damping"].setValue(self._config.get("wheel.damping", 0.12))
