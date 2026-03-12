"""
desktop_app/pages/tests_diagnostics_page.py — Tests & Diagnostics.
Simple: ping/version row, sweep controls, fault display, raw log.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QProgressBar, QTextEdit, QFrame
)
from PySide6.QtCore import QTimer
from pages.base_page import BasePage
from ui.styles import COLORS
import time


class TestsDiagnosticsPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="Tests & Diagnostics", **kwargs)
        self._sweep_timer = QTimer()
        self._sweep_timer.timeout.connect(self._sweep_tick)
        self._sweep_angle = 0.0
        self._sweep_dir = 1
        self._build()

    def _build(self):
        # ── Quick serial tests ────────────────────────────────────────
        row1 = QHBoxLayout()
        for label, fn in [("Ping", self._ping), ("Get Version", self._version),
                          ("Request Telemetry", self._telem), ("Clear Faults", self._clear_faults)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            row1.addWidget(b)
        row1.addStretch()
        self.content_layout.addLayout(row1)
        self.content_layout.addWidget(self._sep())

        # ── Sweep test ────────────────────────────────────────────────
        sweep_row = QHBoxLayout()
        sweep_row.addWidget(QLabel("Sweep ±"))
        self._sweep_max_sb = QDoubleSpinBox()
        self._sweep_max_sb.setRange(10, 270)
        self._sweep_max_sb.setValue(90)
        self._sweep_max_sb.setSuffix("°")
        self._sweep_max_sb.setFixedWidth(80)
        sweep_row.addWidget(self._sweep_max_sb)

        btn_start = QPushButton("Start Sweep")
        btn_start.setObjectName("btn_primary")
        btn_start.clicked.connect(self._start_sweep)
        btn_stop = QPushButton("Stop")
        btn_stop.clicked.connect(self._stop_sweep)
        sweep_row.addWidget(btn_start)
        sweep_row.addWidget(btn_stop)

        self._sweep_bar = QProgressBar()
        self._sweep_bar.setRange(-100, 100)
        self._sweep_bar.setValue(0)
        self._sweep_bar.setFixedHeight(18)
        sweep_row.addWidget(self._sweep_bar, 1)
        self.content_layout.addLayout(sweep_row)
        self.content_layout.addWidget(self._sep())

        # ── Fault + angle display ─────────────────────────────────────
        info_row = QHBoxLayout()
        info_row.addWidget(QLabel("Encoder:"))
        self._enc_lbl = QLabel("—")
        self._enc_lbl.setStyleSheet(f"color:{COLORS['text_primary']};font-family:Consolas;")
        info_row.addWidget(self._enc_lbl)
        info_row.addSpacing(20)
        info_row.addWidget(QLabel("Faults:"))
        self._fault_lbl = QLabel("None")
        self._fault_lbl.setStyleSheet(f"color:{COLORS['accent_green']};font-family:Consolas;")
        info_row.addWidget(self._fault_lbl)
        info_row.addStretch()

        btn_export = QPushButton("Export Report")
        btn_export.clicked.connect(self._export)
        info_row.addWidget(btn_export)
        self.content_layout.addLayout(info_row)
        self.content_layout.addWidget(self._sep())

        # ── Serial output log ─────────────────────────────────────────
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setStyleSheet(
            f"font-family:Consolas;font-size:11px;"
            f"background:{COLORS['bg_panel']};border:none;"
        )
        self.content_layout.addWidget(self._log_box, 1)

        btn_clear = QPushButton("Clear Log")
        btn_clear.setFixedWidth(90)
        btn_clear.clicked.connect(self._log_box.clear)
        self.content_layout.addWidget(btn_clear)

        if self._serial:
            self._serial.raw_line.connect(lambda l: self._log_box.append(f"  {l}"))

    def _ping(self):
        if self._serial and self._serial.is_connected:
            self._serial.ping()

    def _version(self):
        if self._serial and self._serial.is_connected:
            self._serial.get_version()

    def _telem(self):
        if self._serial and self._serial.is_connected:
            self._serial.send_command({"cmd": "get_telemetry"})

    def _clear_faults(self):
        if self._serial and self._serial.is_connected:
            self._serial.clear_faults()

    def _start_sweep(self):
        if not (self._serial and self._serial.is_connected):
            return
        self._sweep_angle = 0.0
        self._sweep_dir = 1
        self._serial.set_mode("ANGLE_TRACK")
        self._sweep_timer.start(100)

    def _stop_sweep(self):
        self._sweep_timer.stop()
        if self._serial and self._serial.is_connected:
            self._serial.set_target(0.0)
        self._sweep_bar.setValue(0)

    def _sweep_tick(self):
        mx = self._sweep_max_sb.value()
        self._sweep_angle += 5 * self._sweep_dir
        if self._sweep_angle >= mx:
            self._sweep_angle = mx
            self._sweep_dir = -1
        elif self._sweep_angle <= -mx:
            self._sweep_angle = -mx
            self._sweep_dir = 1
        if self._serial and self._serial.is_connected:
            self._serial.set_target(self._sweep_angle)
        self._sweep_bar.setValue(int(self._sweep_angle / mx * 100))

    def _export(self):
        import os
        t = self._telemetry.latest if self._telemetry else None
        lines = [
            "SelfDriveBeamNGTech Diagnostic Report",
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Serial: {self._serial.is_connected if self._serial else False}",
            f"FW: {self._serial.fw_version if self._serial else 'N/A'}",
        ]
        if t:
            lines += [f"Angle: {t.angle:.2f}", f"Mode: {t.mode}",
                      f"Faults: {t.fault_names()}"]
        path = f"output/logs/diag_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs("output/logs", exist_ok=True)
        open(path, "w").write("\n".join(lines))
        self._log_box.append(f"Report saved: {path}")

    def refresh(self):
        t = self._telemetry.latest if self._telemetry else None
        if t:
            self._enc_lbl.setText(str(t.enc))
            faults = t.fault_names()
            self._fault_lbl.setText(", ".join(faults) if faults else "None")
            self._fault_lbl.setStyleSheet(
                f"color:{COLORS['accent_red'] if faults else COLORS['accent_green']};"
                f"font-family:Consolas;"
            )
