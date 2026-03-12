"""
desktop_app/pages/beamng_ai_page.py — BeamNG.tech AI Mode page.
Section A of the product: AI coach, self-driving, shared control.
"""
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QDoubleSpinBox, QComboBox, QFormLayout, QSlider, QFrame,
    QScrollArea, QWidget, QCheckBox, QFileDialog
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
        super().__init__(
            title="BeamNG.tech AI Mode",
            subtitle="Section A — AI coach, self-driving, and shared control with BeamNG.tech",
            **kwargs
        )
        # Sub-components
        self._bridge = BeamNGBridge(self._serial, self._safety, self._config)
        self._ai = AIController(self._bridge, self._safety, self._log)
        self._shared = SharedControl(self._serial, self._safety, self._log)
        self._replay = ReplayController(self._serial, self._log,
                                        output_dir="output/logs")

        self._build_content()
        self._connect_signals()

    def _build_content(self):
        # Top banner: BeamNG AI mode section header
        banner = QLabel("  ▶  BEAMNG.TECH AI MODE — Section A: Self-Driving & AI Coach")
        banner.setFixedHeight(36)
        banner.setStyleSheet(
            f"background-color: #1a2e3a; color: {COLORS['accent_blue']}; "
            f"font-weight: 600; font-size: 13px; "
            f"border: 1px solid {COLORS['accent_blue']}; border-radius: 3px;"
        )
        self.content_layout.addWidget(banner)

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

        # ---- BeamNG Connection ----
        conn_group = QGroupBox("BEAMNG.TECH CONNECTION")
        conn_layout = QFormLayout(conn_group)

        self._bng_host = QLabel("localhost")
        self._bng_port = QLabel("64256")
        conn_layout.addRow("Host:", self._bng_host)
        conn_layout.addRow("Port:", self._bng_port)

        conn_btn_row = QHBoxLayout()
        self._btn_bng_connect = QPushButton("Connect to BeamNG")
        self._btn_bng_connect.setObjectName("btn_primary")
        self._btn_bng_connect.clicked.connect(self._on_bng_connect)
        btn_bng_disconnect = QPushButton("Disconnect")
        btn_bng_disconnect.clicked.connect(self._on_bng_disconnect)
        conn_btn_row.addWidget(self._btn_bng_connect)
        conn_btn_row.addWidget(btn_bng_disconnect)
        conn_layout.addRow("", conn_btn_row)

        self._bng_status_lbl = QLabel("Not connected")
        self._bng_status_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        conn_layout.addRow("Status:", self._bng_status_lbl)
        left.addWidget(conn_group)

        # ---- Vehicle state ----
        veh_group = QGroupBox("VEHICLE STATE")
        veh_layout = QFormLayout(veh_group)

        self._veh_steer_lbl = QLabel("—")
        self._veh_speed_lbl = QLabel("—")
        self._veh_rpm_lbl   = QLabel("—")
        self._veh_gear_lbl  = QLabel("—")
        for lbl in [self._veh_steer_lbl, self._veh_speed_lbl,
                    self._veh_rpm_lbl, self._veh_gear_lbl]:
            lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas;")

        veh_layout.addRow("Steering Input:", self._veh_steer_lbl)
        veh_layout.addRow("Speed:", self._veh_speed_lbl)
        veh_layout.addRow("RPM:", self._veh_rpm_lbl)
        veh_layout.addRow("Gear:", self._veh_gear_lbl)
        left.addWidget(veh_group)

        # ---- AI Control mode ----
        ai_group = QGroupBox("AI CONTROL MODE")
        ai_layout = QVBoxLayout(ai_group)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Target Source:"))
        self._source_combo = QComboBox()
        self._source_combo.addItems([s.value for s in TargetSource])
        self._source_combo.setCurrentText(TargetSource.MANUAL_TEST.value)
        source_row.addWidget(self._source_combo)
        ai_layout.addLayout(source_row)

        # Manual test target
        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Manual Target:"))
        self._manual_spin = QDoubleSpinBox()
        self._manual_spin.setRange(-540, 540)
        self._manual_spin.setSuffix("°")
        self._manual_spin.valueChanged.connect(self._on_manual_target_changed)
        manual_row.addWidget(self._manual_spin)
        ai_layout.addLayout(manual_row)

        # Replay controls
        replay_row = QHBoxLayout()
        self._btn_load_replay = QPushButton("Load Replay File")
        self._btn_load_replay.clicked.connect(self._load_replay)
        self._btn_play_replay = QPushButton("Play Replay")
        self._btn_play_replay.clicked.connect(self._play_replay)
        self._btn_stop_replay = QPushButton("Stop Replay")
        self._btn_stop_replay.clicked.connect(self._stop_replay)
        replay_row.addWidget(self._btn_load_replay)
        replay_row.addWidget(self._btn_play_replay)
        replay_row.addWidget(self._btn_stop_replay)
        ai_layout.addLayout(replay_row)

        # Start/Stop AI
        ai_ctrl_row = QHBoxLayout()
        self._btn_start_ai = QPushButton("▶ Start AI Control")
        self._btn_start_ai.setObjectName("btn_success")
        self._btn_start_ai.clicked.connect(self._start_ai)

        self._btn_stop_ai = QPushButton("■ Stop AI Control")
        self._btn_stop_ai.setObjectName("btn_warning")
        self._btn_stop_ai.clicked.connect(self._stop_ai)

        btn_estop_ai = QPushButton("⚠ EMERGENCY DISENGAGE")
        btn_estop_ai.setObjectName("btn_danger")
        btn_estop_ai.clicked.connect(self._emergency_disengage)

        ai_ctrl_row.addWidget(self._btn_start_ai)
        ai_ctrl_row.addWidget(self._btn_stop_ai)
        ai_ctrl_row.addWidget(btn_estop_ai)
        ai_layout.addLayout(ai_ctrl_row)

        self._ai_status_lbl = QLabel("AI Status: Stopped")
        self._ai_status_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        ai_layout.addWidget(self._ai_status_lbl)
        left.addWidget(ai_group)
        left.addStretch()

        # ---- Shared control ----
        shared_group = QGroupBox("SHARED CONTROL MODE")
        shared_layout = QVBoxLayout(shared_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._shared_mode_combo = QComboBox()
        self._shared_mode_combo.addItems([
            SharedControlMode.HUMAN_ONLY,
            SharedControlMode.ASSIST,
            SharedControlMode.BLEND,
            SharedControlMode.AI_ONLY,
        ])
        mode_row.addWidget(self._shared_mode_combo)
        shared_layout.addLayout(mode_row)

        auth_row = QHBoxLayout()
        auth_row.addWidget(QLabel("AI Authority:"))
        self._authority_slider = QSlider(Qt.Orientation.Horizontal)
        self._authority_slider.setRange(0, 100)
        self._authority_slider.setValue(50)
        self._authority_lbl = QLabel("50%")
        self._authority_slider.valueChanged.connect(
            lambda v: self._authority_lbl.setText(f"{v}%")
        )
        auth_row.addWidget(self._authority_slider)
        auth_row.addWidget(self._authority_lbl)
        shared_layout.addLayout(auth_row)

        btn_shared_row = QHBoxLayout()
        btn_activate_shared = QPushButton("Activate Shared Control")
        btn_activate_shared.setObjectName("btn_primary")
        btn_activate_shared.clicked.connect(self._activate_shared)
        btn_deactivate_shared = QPushButton("Deactivate")
        btn_deactivate_shared.clicked.connect(self._shared.deactivate)
        btn_shared_row.addWidget(btn_activate_shared)
        btn_shared_row.addWidget(btn_deactivate_shared)
        shared_layout.addLayout(btn_shared_row)
        right.addWidget(shared_group)

        # ---- Bridge settings ----
        bridge_group = QGroupBox("STEER → ANGLE MAPPING")
        bridge_layout = QFormLayout(bridge_group)

        self._steer_scale_spin = QDoubleSpinBox()
        self._steer_scale_spin.setRange(0.1, 5.0)
        self._steer_scale_spin.setValue(1.0)
        self._steer_scale_spin.setDecimals(2)
        self._steer_scale_spin.setToolTip(
            "Multiplier: BeamNG ±1 maps to ± (angle_range/2 × scale)"
        )

        self._safety_max_spin = QDoubleSpinBox()
        self._safety_max_spin.setRange(10, 540)
        self._safety_max_spin.setValue(400.0)
        self._safety_max_spin.setSuffix("°")
        self._safety_max_spin.setToolTip("Max angle allowed from AI commands")

        bridge_layout.addRow("Steer Scale:", self._steer_scale_spin)
        bridge_layout.addRow("Safety Max Angle:", self._safety_max_spin)

        btn_apply_bridge = QPushButton("Apply Mapping")
        btn_apply_bridge.clicked.connect(self._apply_bridge)
        bridge_layout.addRow("", btn_apply_bridge)
        right.addWidget(bridge_group)

        # ---- Live AI telemetry ----
        ai_telem_group = QGroupBox("LIVE AI TELEMETRY")
        ai_telem_layout = QFormLayout(ai_telem_group)

        self._ai_target_lbl  = QLabel("—")
        self._ai_current_lbl = QLabel("—")
        self._ai_error_lbl   = QLabel("—")
        self._ai_mode_lbl    = QLabel("STOPPED")

        for lbl in [self._ai_target_lbl, self._ai_current_lbl,
                    self._ai_error_lbl, self._ai_mode_lbl]:
            lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-family: Consolas;")

        ai_telem_layout.addRow("AI Target:", self._ai_target_lbl)
        ai_telem_layout.addRow("Current Angle:", self._ai_current_lbl)
        ai_telem_layout.addRow("Error:", self._ai_error_lbl)
        ai_telem_layout.addRow("AI Mode:", self._ai_mode_lbl)
        right.addWidget(ai_telem_group)
        right.addStretch()

    def _connect_signals(self):
        if self._beamng_manager:
            self._beamng_manager.connected.connect(self._on_bng_connected)
            self._beamng_manager.disconnected.connect(self._on_bng_disconnected)
            self._beamng_manager.vehicle_state.connect(self._on_vehicle_state)

        self._ai.target_computed.connect(self._on_ai_target)
        self._ai.mode_changed.connect(self._on_ai_mode_changed)

        self._replay.recording_stopped.connect(lambda p: self._log.info(f"Recording: {p}"))
        self._replay.playback_stopped.connect(lambda: self._ai_status_lbl.setText("Replay: stopped"))

    def _on_bng_connect(self):
        if self._beamng_manager:
            host = "localhost"
            port = self._config.get("beamng.port", 64256) if self._config else 64256
            self._beamng_manager.connect(host, port)

    def _on_bng_disconnect(self):
        if self._beamng_manager:
            self._beamng_manager.disconnect()

    def _on_bng_connected(self):
        self._bng_status_lbl.setText("Connected")
        self._bng_status_lbl.setStyleSheet(f"color: {COLORS['accent_green']};")

    def _on_bng_disconnected(self):
        self._bng_status_lbl.setText("Disconnected")
        self._bng_status_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")

    def _on_vehicle_state(self, state: dict):
        self._veh_steer_lbl.setText(f"{state.get('steering_input', 0):.3f}")
        self._veh_speed_lbl.setText(f"{state.get('speed', 0):.1f} m/s")
        self._veh_rpm_lbl.setText(f"{state.get('rpm', 0):.0f}")
        self._veh_gear_lbl.setText(str(state.get('gear', 1)))

        # If AI is in BEAMNG source mode, feed the bridge
        if self._ai.is_active:
            self._bridge.process_vehicle_state(state)

    def _on_manual_target_changed(self, val: float):
        self._ai.set_manual_target(val)

    def _start_ai(self):
        src = TargetSource(self._source_combo.currentText())
        self._ai.set_source(src)
        self._ai.start()
        self._ai_status_lbl.setText(f"AI Status: Active ({src.value})")
        self._ai_status_lbl.setStyleSheet(f"color: {COLORS['accent_green']};")

    def _stop_ai(self):
        self._ai.stop()
        self._ai_status_lbl.setText("AI Status: Stopped")
        self._ai_status_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")

    def _emergency_disengage(self):
        self._ai.stop()
        if self._safety:
            self._safety.trigger_estop("AI emergency disengage")
        self._ai_status_lbl.setText("⚠ EMERGENCY DISENGAGE")
        self._ai_status_lbl.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: 700;")

    def _on_ai_target(self, angle: float):
        self._ai_target_lbl.setText(f"{angle:.1f}°")
        telem = self._telemetry.latest if self._telemetry else None
        if telem:
            error = angle - telem.angle
            self._ai_error_lbl.setText(f"{error:.1f}°")
            self._ai_current_lbl.setText(f"{telem.angle:.1f}°")

    def _on_ai_mode_changed(self, mode: str):
        self._ai_mode_lbl.setText(mode)

    def _load_replay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Replay", "output/logs", "CSV (*.csv)")
        if path:
            self._replay.load(path)
            self._ai_status_lbl.setText(f"Replay loaded: {path}")

    def _play_replay(self):
        self._replay.start_playback()

    def _stop_replay(self):
        self._replay.stop_playback()

    def _activate_shared(self):
        mode = self._shared_mode_combo.currentText()
        authority = self._authority_slider.value() / 100.0
        self._shared.activate(mode=mode, authority=authority)

    def _apply_bridge(self):
        if self._config:
            self._config.set("beamng.steer_scale", self._steer_scale_spin.value())
            self._config.set("beamng.safety_max_angle", self._safety_max_spin.value())
        self._bridge.configure_from_config()

    def refresh(self):
        telem = self._telemetry.latest if self._telemetry else None
        if telem and self._ai.is_active:
            self._ai_current_lbl.setText(f"{telem.angle:.1f}°")
