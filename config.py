"""
Centralized config for the Assetto Corsa autonomous driver.
Edit this file — no magic numbers anywhere else.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Tuple

from training.paths import AC_TRAINING_DATA_DIR

# ── Assetto Corsa paths ───────────────────────────────────────────
_AC_DOCS = os.path.join(os.path.expanduser("~"), "Documents", "Assetto Corsa")


@dataclass
class ACPathsConfig:
    # Where the in-game Python app writes telemetry JSON
    state_file: str = os.path.join(_AC_DOCS, "logs", "acdriver_state.json")
    # Where to install the app (copy ac_app/ACDriverApp/ here)
    apps_folder: str = os.path.join(_AC_DOCS, "apps", "python")


# ── Screen Capture ─────────────────────────────────────────────────
@dataclass
class CaptureConfig:
    # Screen region to capture — adjust for your resolution / window mode
    # (left, top, width, height)  format expected by mss
    # AC windowed 800×600:    (0, 40, 800, 600)
    # AC fullscreen 1920×1080: (0, 40, 1920, 1080)
    monitor_region: Tuple[int, int, int, int] = (0, 40, 1920, 1080)
    # Size to resize the captured frame to before perception / ML
    proc_width: int = 200
    proc_height: int = 66
    # Main loop target rate
    loop_hz: float = 30.0


# ── Perception ─────────────────────────────────────────────────────
@dataclass
class PerceptionConfig:
    # Bottom fraction of the image to use as ROI
    roi_top_frac: float = 0.60
    # Canny edge thresholds
    canny_low: int = 150
    canny_high: int = 250
    # HSV road mask (grey asphalt)
    road_hsv_lower: Tuple[int, int, int] = (0, 0, 50)
    road_hsv_upper: Tuple[int, int, int] = (180, 80, 200)
    blur_kernel: int = 5
    # Hough
    hough_threshold: int = 20
    hough_min_line_len: int = 30
    hough_max_line_gap: int = 80
    min_lane_pixels: int = 30


# ── Steering PID ───────────────────────────────────────────────────
@dataclass
class SteeringPIDConfig:
    kp: float = 0.7
    ki: float = 0.0
    kd: float = 0.12
    output_min: float = -1.0
    output_max: float = 1.0
    deadband: float = 0.02
    max_rate: float = 0.12


# ── Speed Controller ───────────────────────────────────────────────
@dataclass
class SpeedConfig:
    target_kph: float = 60.0
    kp: float = 0.15
    ki: float = 0.01
    kd: float = 0.04
    coast_band_kph: float = 3.0


# ── Training ───────────────────────────────────────────────────────
@dataclass
class TrainingConfig:
    # Image fed to CNN
    img_width: int = 200
    img_height: int = 66
    img_channels: int = 3            # keep colour for training (NVIDIA style)
    # Training data
    data_dir: str = str(AC_TRAINING_DATA_DIR)
    # Model
    model_path: str = "models/acdriver_model.keras"
    batch_size: int = 32
    epochs: int = 30
    learning_rate: float = 1e-4
    val_split: float = 0.15
    # Steering lock assumed for normalisation (most AC road cars ≈ ±450 °)
    steer_lock_deg: float = 450.0


# ── Control Output ─────────────────────────────────────────────────
@dataclass
class ControlOutputConfig:
    # "vjoy" (smooth analog, needs vJoy driver) or "keys" (WASD fallback)
    mode: str = "keys"       # change to "vjoy" if you have vJoy installed
    vjoy_device_id: int = 1
    # Key-press pulse duration (seconds) for WASD mode
    key_pulse_s: float = 0.05
    # Steering threshold for left/right key in WASD mode
    steer_key_threshold: float = 0.15
    # Throttle threshold for gas key
    gas_key_threshold: float = 0.1


# ── Safety ─────────────────────────────────────────────────────────
@dataclass
class SafetyConfig:
    max_speed_kph: float = 120.0
    perception_fail_frames: int = 15


# ── Debug / Logging ────────────────────────────────────────────────
@dataclass
class DebugConfig:
    show_overlay: bool = True
    print_telemetry: bool = True
    telemetry_interval: int = 15
    log_csv: bool = True
    csv_path: str = "logs/ac_telemetry.csv"
    save_frames: bool = False
    frame_dir: str = "logs/frames"


# ── Aggregate ──────────────────────────────────────────────────────
@dataclass
class Config:
    paths: ACPathsConfig = field(default_factory=ACPathsConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    steering: SteeringPIDConfig = field(default_factory=SteeringPIDConfig)
    speed: SpeedConfig = field(default_factory=SpeedConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    control_out: ControlOutputConfig = field(default_factory=ControlOutputConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)


CFG = Config()
