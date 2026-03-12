"""
desktop_app/pages/normal_wheel_page.py — Normal Wheel Mode.
Simple: mode buttons, range, 4 FFB sliders, live angle.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSlider, QDoubleSpinBox, QFrame
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS


def _slider_row(label, min_v, max_v, default, unit="", tip=""):
    """Returns (row_widget, spinbox)."""
    w = QFrame()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)

    lbl = QLabel(label)
    lbl.setFixedWidth(160)
    lbl.setStyleSheet(f"color:{COLORS['text_secondary']};")
    if tip:
        lbl.setToolTip(tip)

    scale = 10 if max_v <= 10 else 1
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(int(min_v * scale), int(max_v * scale))
    sl.setValue(int(default * scale))

    sb = QDoubleSpinBox()
    sb.setRange(min_v, max_v)
    sb.setValue(default)
    sb.setDecimals(1 if scale == 10 else 0)
    sb.setSuffix(f" {unit}" if unit else "")
    sb.setFixedWidth(78)

    sl.valueChanged.connect(lambda v: (sb.blockSignals(True), sb.setValue(v / scale), sb.blockSignals(False)))
    sb.valueChanged.connect(lambda v: (sl.blockSignals(True), sl.setValue(int(v * scale)), sl.blockSignals(False)))

    h.addWidget(lbl)
    h.addWidget(sl, 1)
    h.addWidget(sb)
    return w, sb


class NormalWheelPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Normal Wheel Mode", **kwargs)
        self._build()

    def _build(self):
        # ── Mode buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, mode in [("Idle", "IDLE"), ("HID Mode", "NORMAL_HID"),
                             ("Assist", "ASSIST"), ("Angle Track", "ANGLE_TRACK")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _, m=mode: self._set_mode(m))
            btn_row.addWidget(b)
        btn_row.addStretch()
        self.content_layout.addLayout(btn_row)
        self.content_layout.addWidget(self._sep())

        # ── Steering range ───────────────────────────────────────────
        range_row, self._range_sb = _slider_row(
            "Steering Range", 90, 1080, 540, "°",
            "Total rotation in degrees (540 = ±270°)"
        )
        self.content_layout.addWidget(range_row)
        self.content_layout.addWidget(self._sep())

        # ── FFB sliders ───────────────────────────────────────────────
        ffb = [
            ("Max Motor Output", 0, 255, 200, "", "PWM ceiling 0–255"),
            ("Centering Strength", 0, 3.0, 1.0, "", "Spring-center force"),
            ("Damping", 0, 1.0, 0.12, "", "Resistance to rotation"),
            ("Friction", 0, 1.0, 0.05, "", "Constant resistance"),
        ]
        self._ffb = {}
        for lbl, mn, mx, dflt, unit, tip in ffb:
            w, sb = _slider_row(lbl, mn, mx, dflt, unit, tip)
            self.content_layout.addWidget(w)
            self._ffb[lbl] = sb
        self.content_layout.addWidget(self._sep())

        # ── Live angle display ────────────────────────────────────────
        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("Current Angle:"))
        self._angle_lbl = QLabel("0.0°")
        self._angle_lbl.setStyleSheet(
            f"color:{COLORS['accent_blue']};font-size:26px;"
            f"font-weight:700;font-family:Consolas;"
        )
        angle_row.addWidget(self._angle_lbl)
        angle_row.addStretch()
        self.content_layout.addLayout(angle_row)
        self.content_layout.addStretch()

        # ── Action buttons ────────────────────────────────────────────
        act_row = QHBoxLayout()
        btn_write = QPushButton("Write Settings to Device")
        btn_write.setObjectName("btn_primary")
        btn_write.clicked.connect(self._write)
        btn_def = QPushButton("Restore Defaults")
        btn_def.clicked.connect(self._defaults)
        act_row.addWidget(btn_write)
        act_row.addWidget(btn_def)
        act_row.addStretch()
        self.content_layout.addLayout(act_row)

    def _set_mode(self, mode):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode(mode)

    def _write(self):
        if not self._serial or not self._serial.is_connected:
            return
        self._serial.set_config("angle_range", self._range_sb.value())
        if self._config:
            self._config.set("wheel.angle_range", self._range_sb.value())
            self._config.set("wheel.max_motor_output", int(self._ffb["Max Motor Output"].value()))
            self._config.set("wheel.centering_strength", self._ffb["Centering Strength"].value())
            self._config.set("wheel.damping", self._ffb["Damping"].value())
            self._config.set("wheel.friction", self._ffb["Friction"].value())

    def _defaults(self):
        self._range_sb.setValue(540)
        self._ffb["Max Motor Output"].setValue(200)
        self._ffb["Centering Strength"].setValue(1.0)
        self._ffb["Damping"].setValue(0.12)
        self._ffb["Friction"].setValue(0.05)

    def refresh(self):
        t = self._telemetry.latest if self._telemetry else None
        if t:
            self._angle_lbl.setText(f"{t.angle:.1f}°")
