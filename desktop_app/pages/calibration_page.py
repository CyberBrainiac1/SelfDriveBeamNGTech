"""
desktop_app/pages/calibration_page.py — Calibration.
5 sequential steps, live angle readout.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QSpinBox, QFormLayout, QFrame
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS

class CalibrationPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Calibration", **kwargs)
        self._build()

    def _build(self):
        # ── Live readout ─────────────────────────────────────────────
        live = QHBoxLayout()
        live.addWidget(QLabel("Angle:"))
        self._angle_lbl = QLabel("0.00°")
        self._angle_lbl.setStyleSheet(
            f"color:{COLORS['accent_blue']};font-size:22px;"
            f"font-weight:700;font-family:Consolas;"
        )
        live.addWidget(self._angle_lbl)
        live.addSpacing(20)
        live.addWidget(QLabel("Encoder:"))
        self._enc_lbl = QLabel("0")
        self._enc_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};font-family:Consolas;")
        live.addWidget(self._enc_lbl)
        live.addSpacing(20)
        live.addWidget(QLabel("Mode:"))
        self._mode_lbl = QLabel("—")
        self._mode_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};font-family:Consolas;")
        live.addWidget(self._mode_lbl)
        live.addStretch()
        self.content_layout.addLayout(live)
        self.content_layout.addWidget(self._sep())

        # ── Steps ────────────────────────────────────────────────────
        steps = [
            ("1  Enter Calibration Mode",
             "Motors off — safe to turn wheel.",
             [("Enter Cal Mode", lambda: self._mode("CALIBRATION"))]),
            ("2  Zero Encoder",
             "Turn wheel to desired zero position, then click.",
             [("Zero Encoder", self._zero)]),
            ("3  Set Center",
             "Hold wheel straight, then click.",
             [("Set Center (0°)", self._center)]),
            ("4  Test Motor Direction",
             "Switch to ANGLE_TRACK and check rotation.",
             [("Left −15°", lambda: self._target(-15)),
              ("Right +15°", lambda: self._target(15)),
              ("Return 0°",  lambda: self._target(0))]),
            ("5  Save Calibration",
             "Write current settings to config file.",
             [("Save", self._save)]),
        ]

        for title, desc, buttons in steps:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{title}</b>  <span style='color:{COLORS['text_dim']};font-size:11px;'>{desc}</span>")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            row.addWidget(lbl, 1)
            for btn_lbl, fn in buttons:
                b = QPushButton(btn_lbl)
                b.setFixedWidth(110)
                b.clicked.connect(fn)
                row.addWidget(b)
            self.content_layout.addLayout(row)

        self.content_layout.addWidget(self._sep())

        # ── Range settings ───────────────────────────────────────────
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(6)

        self._cpr_sb = QSpinBox()
        self._cpr_sb.setRange(100, 100000)
        self._cpr_sb.setValue(2400)
        self._cpr_sb.setToolTip("Encoder counts per revolution (4× quadrature)")

        self._range_sb = QDoubleSpinBox()
        self._range_sb.setRange(90, 1080)
        self._range_sb.setValue(540)
        self._range_sb.setSuffix("°")

        form.addRow(QLabel("Counts/Rev:"), self._cpr_sb)
        form.addRow(QLabel("Steering Range:"), self._range_sb)

        btn_apply = QPushButton("Apply Range")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self._apply_range)
        form.addRow("", btn_apply)

        self.content_layout.addLayout(form)
        self.content_layout.addStretch()

    def _mode(self, m):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode(m)

    def _zero(self):
        if self._serial and self._serial.is_connected:
            self._serial.zero_encoder()

    def _center(self):
        if self._serial and self._serial.is_connected:
            self._serial.set_center()

    def _target(self, angle):
        if self._serial and self._serial.is_connected:
            self._serial.set_mode("ANGLE_TRACK")
            self._serial.set_target(float(angle))

    def _apply_range(self):
        if self._config:
            self._config.set("wheel.counts_per_rev", self._cpr_sb.value())
            self._config.set("wheel.angle_range", self._range_sb.value())
        if self._serial and self._serial.is_connected:
            self._serial.set_config("angle_range", self._range_sb.value())

    def _save(self):
        if self._config:
            self._config.save()

    def refresh(self):
        t = self._telemetry.latest if self._telemetry else None
        if t:
            self._angle_lbl.setText(f"{t.angle:.2f}°")
            self._enc_lbl.setText(str(t.enc))
            self._mode_lbl.setText(t.mode)

