"""
desktop_app/pages/beamng_ai_page.py — BeamNG.tech AI Mode (Section A).
Simple: connect, pick source, start/stop, see live target. Emergency stop.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QSlider, QFrame, QFileDialog
)
from PySide6.QtCore import Qt
from pages.base_page import BasePage
from ui.styles import COLORS
from beamng.ai_controller import AIController, TargetSource
from beamng.beamng_bridge import BeamNGBridge
from beamng.shared_control import SharedControl, SharedControlMode
from beamng.replay_controller import ReplayController


class BeamNGAIPage(BasePage):
    def __init__(self, **kwargs):
        self._beamng_manager = kwargs.pop("beamng_manager", None)
        super().__init__(title="BeamNG.tech AI Mode", **kwargs)
        self._bridge = BeamNGBridge(self._serial, self._safety, self._config)
        self._ai = AIController(self._bridge, self._safety, self._log)
        self._shared = SharedControl(self._serial, self._safety, self._log)
        self._replay = ReplayController(self._serial, self._log, output_dir="output/logs")
        self._build()
        self._wire()

    def _build(self):
        # ── Section banner ────────────────────────────────────────────
        banner = QLabel("  ▶  Section A — Self-Driving / AI Coach")
        banner.setFixedHeight(30)
        banner.setStyleSheet(
            f"background:#0d2233;color:{COLORS['accent_blue']};"
            f"font-weight:600;border:1px solid {COLORS['accent_blue']};"
            f"border-radius:3px;padding-left:6px;"
        )
        self.content_layout.addWidget(banner)

        # ── Row 1: BeamNG connection ──────────────────────────────────
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("BeamNG:"))
        self._btn_bng = QPushButton("Connect")
        self._btn_bng.setObjectName("btn_primary")
        self._btn_bng.clicked.connect(self._toggle_bng)
        self._bng_status = QLabel("Not connected")
        self._bng_status.setStyleSheet(f"color:{COLORS['text_dim']};")
        row1.addWidget(self._btn_bng)
        row1.addWidget(self._bng_status)
        row1.addStretch()
        self.content_layout.addLayout(row1)
        self.content_layout.addWidget(self._sep())

        # ── Row 2: Target source + AI start/stop ─────────────────────
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Source:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems([s.value for s in TargetSource])
        self._src_combo.setFixedWidth(140)
        row2.addWidget(self._src_combo)

        row2.addSpacing(12)
        row2.addWidget(QLabel("Manual target:"))
        self._manual_sb = QDoubleSpinBox()
        self._manual_sb.setRange(-540, 540)
        self._manual_sb.setSuffix("°")
        self._manual_sb.setFixedWidth(90)
        self._manual_sb.valueChanged.connect(self._ai.set_manual_target)
        row2.addWidget(self._manual_sb)
        row2.addStretch()

        self._btn_start = QPushButton("▶ Start AI")
        self._btn_start.setObjectName("btn_success")
        self._btn_start.clicked.connect(self._start_ai)
        self._btn_stop = QPushButton("■ Stop AI")
        self._btn_stop.setObjectName("btn_warning")
        self._btn_stop.clicked.connect(self._stop_ai)
        row2.addWidget(self._btn_start)
        row2.addWidget(self._btn_stop)
        self.content_layout.addLayout(row2)

        # ── Row 3: Replay controls ────────────────────────────────────
        row3 = QHBoxLayout()
        btn_load = QPushButton("Load Replay")
        btn_load.clicked.connect(self._load_replay)
        btn_play = QPushButton("Play")
        btn_play.clicked.connect(self._replay.start_playback)
        btn_stop_r = QPushButton("Stop")
        btn_stop_r.clicked.connect(self._replay.stop_playback)
        row3.addWidget(btn_load)
        row3.addWidget(btn_play)
        row3.addWidget(btn_stop_r)
        row3.addStretch()
        self.content_layout.addLayout(row3)
        self.content_layout.addWidget(self._sep())

        # ── Shared control authority slider ───────────────────────────
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Shared control:"))
        self._sc_combo = QComboBox()
        self._sc_combo.addItems([
            SharedControlMode.HUMAN_ONLY, SharedControlMode.ASSIST,
            SharedControlMode.BLEND, SharedControlMode.AI_ONLY
        ])
        self._sc_combo.setFixedWidth(120)
        row4.addWidget(self._sc_combo)
        row4.addWidget(QLabel("AI authority:"))
        self._auth_sl = QSlider(Qt.Orientation.Horizontal)
        self._auth_sl.setRange(0, 100)
        self._auth_sl.setValue(50)
        self._auth_sl.setFixedWidth(120)
        self._auth_lbl = QLabel("50%")
        self._auth_sl.valueChanged.connect(lambda v: self._auth_lbl.setText(f"{v}%"))
        row4.addWidget(self._auth_sl)
        row4.addWidget(self._auth_lbl)

        btn_sc = QPushButton("Activate")
        btn_sc.clicked.connect(self._activate_shared)
        row4.addWidget(btn_sc)
        row4.addStretch()
        self.content_layout.addLayout(row4)
        self.content_layout.addWidget(self._sep())

        # ── Live AI telemetry ─────────────────────────────────────────
        telem_row = QHBoxLayout()
        for label, attr in [("AI Target", "_t_target"), ("Current", "_t_current"),
                             ("Error", "_t_error"), ("AI Mode", "_t_mode")]:
            telem_row.addWidget(QLabel(label + ":"))
            lbl = QLabel("—")
            lbl.setStyleSheet(f"color:{COLORS['accent_blue']};font-family:Consolas;font-weight:600;")
            telem_row.addWidget(lbl)
            telem_row.addSpacing(12)
            setattr(self, attr, lbl)
        telem_row.addStretch()
        self.content_layout.addLayout(telem_row)

        self._ai_status = QLabel("AI Status: Stopped")
        self._ai_status.setStyleSheet(f"color:{COLORS['text_secondary']};")
        self.content_layout.addWidget(self._ai_status)
        self.content_layout.addStretch()

        # ── Emergency disengage ───────────────────────────────────────
        btn_estop = QPushButton("⚠  EMERGENCY DISENGAGE")
        btn_estop.setObjectName("btn_danger")
        btn_estop.setFixedHeight(40)
        btn_estop.clicked.connect(self._estop)
        self.content_layout.addWidget(btn_estop)

    def _wire(self):
        if self._beamng_manager:
            self._beamng_manager.connected.connect(self._on_bng_connected)
            self._beamng_manager.disconnected.connect(self._on_bng_disconnected)
            self._beamng_manager.vehicle_state.connect(self._on_vehicle_state)
        self._ai.target_computed.connect(self._on_target)
        self._ai.mode_changed.connect(lambda m: self._t_mode.setText(m))

    def _toggle_bng(self):
        if not self._beamng_manager:
            return
        if self._beamng_manager.is_connected:
            self._beamng_manager.disconnect()
        else:
            host = self._config.get("beamng.host", "localhost") if self._config else "localhost"
            port = self._config.get("beamng.port", 64256) if self._config else 64256
            self._beamng_manager.connect(host, port)

    def _on_bng_connected(self):
        self._btn_bng.setText("Disconnect")
        self._bng_status.setText("Connected")
        self._bng_status.setStyleSheet(f"color:{COLORS['accent_green']};")

    def _on_bng_disconnected(self):
        self._btn_bng.setText("Connect")
        self._bng_status.setText("Not connected")
        self._bng_status.setStyleSheet(f"color:{COLORS['text_dim']};")
        # Stop the AI loop if it was running so the wheel is not left tracking a stale target
        if self._ai.is_active:
            self._ai.stop()
            self._ai_status.setText("AI Status: Stopped  (BeamNG disconnected)")
            self._ai_status.setStyleSheet(f"color:{COLORS['accent_yellow']};font-weight:600;")

    def _on_vehicle_state(self, state):
        if self._ai.is_active:
            self._bridge.process_vehicle_state(state)

    def _start_ai(self):
        src = TargetSource(self._src_combo.currentText())
        self._ai.set_source(src)
        self._ai.start()
        self._ai_status.setText(f"AI Status: Active  ({src.value})")
        self._ai_status.setStyleSheet(f"color:{COLORS['accent_green']};font-weight:600;")

    def _stop_ai(self):
        self._ai.stop()
        self._ai_status.setText("AI Status: Stopped")
        self._ai_status.setStyleSheet(f"color:{COLORS['text_secondary']};")

    def _estop(self):
        self._ai.stop()
        if self._safety:
            self._safety.trigger_estop("AI emergency disengage")
        self._ai_status.setText("⚠ DISENGAGED")
        self._ai_status.setStyleSheet(f"color:{COLORS['accent_red']};font-weight:700;")

    def _on_target(self, angle):
        self._t_target.setText(f"{angle:.1f}°")
        t = self._telemetry.latest if self._telemetry else None
        if t:
            self._t_current.setText(f"{t.angle:.1f}°")
            self._t_error.setText(f"{angle - t.angle:.1f}°")

    def _load_replay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Replay", "output/logs", "CSV (*.csv)")
        if path:
            self._replay.load(path)

    def _activate_shared(self):
        mode = self._sc_combo.currentText()
        authority = self._auth_sl.value() / 100.0
        self._shared.activate(mode=mode, authority=authority)

    def refresh(self):
        t = self._telemetry.latest if self._telemetry else None
        if t and self._ai.is_active:
            self._t_current.setText(f"{t.angle:.1f}°")
