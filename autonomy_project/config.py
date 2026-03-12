"""
Centralized configuration for the autonomous driving system.
All tunable parameters live here — no magic numbers in the codebase.
"""

from dataclasses import dataclass, field
from typing import Tuple


# ── BeamNG Connection ──────────────────────────────────────────────
@dataclass
class BeamNGConfig:
    host: str = "localhost"
    port: int = 64256
    home: str = r"C:\BeamNG.tech"          # ← adjust to your install path
    user_folder: str = ""                   # leave empty to use default


# ── Scenario ───────────────────────────────────────────────────────
@dataclass
class ScenarioConfig:
    level: str = "west_coast_usa"           # map name
    name: str = "autonomy_test"             # scenario display name
    vehicle_model: str = "etk800"           # vehicle to spawn
    vehicle_name: str = "ego"               # internal name
    # Spawn position  (west_coast_usa, a straight stretch of road)
    spawn_pos: Tuple[float, float, float] = (-717.121, 101.0, 118.675)
    spawn_rot_quat: Tuple[float, float, float, float] = (0, 0, 0.3826834, 0.9238795)


# ── Camera Sensor ──────────────────────────────────────────────────
@dataclass
class CameraConfig:
    name: str = "front_cam"
    resolution: Tuple[int, int] = (640, 480)   # width, height
    fov: int = 70
    # Position relative to vehicle center (x=forward, y=left, z=up)
    pos: Tuple[float, float, float] = (0.0, 0.9, 1.5)
    direction: Tuple[float, float, float] = (0, -1, 0)
    near_far_planes: Tuple[float, float] = (0.01, 300)
    colour: bool = True
    depth: bool = True
    annotation: bool = False


# ── Perception ─────────────────────────────────────────────────────
@dataclass
class PerceptionConfig:
    # HSV thresholds for road mask (tuned for grey asphalt)
    road_hsv_lower: Tuple[int, int, int] = (0, 0, 50)
    road_hsv_upper: Tuple[int, int, int] = (180, 80, 180)
    # Canny edge thresholds
    canny_low: int = 50
    canny_high: int = 150
    # Region of interest — fraction of image height for bottom crop
    roi_top_frac: float = 0.50
    # Minimum lane‑line pixel count to accept a detection
    min_lane_pixels: int = 50
    # Gaussian blur kernel size (must be odd)
    blur_kernel: int = 5
    # Hough transform parameters
    hough_threshold: int = 30
    hough_min_line_len: int = 40
    hough_max_line_gap: int = 100


# ── Steering PID ───────────────────────────────────────────────────
@dataclass
class SteeringPIDConfig:
    kp: float = 0.8
    ki: float = 0.0
    kd: float = 0.15
    output_min: float = -1.0
    output_max: float = 1.0
    deadband: float = 0.01           # ignore errors smaller than this
    max_rate: float = 0.15           # max change per tick (smoothing)


# ── Speed Controller ───────────────────────────────────────────────
@dataclass
class SpeedControlConfig:
    target_speed_kph: float = 40.0    # desired cruise speed
    kp: float = 0.15
    ki: float = 0.01
    kd: float = 0.05
    throttle_max: float = 0.6
    brake_max: float = 1.0
    coast_band_kph: float = 2.0       # no throttle/brake inside this band


# ── Safety / Failsafe ─────────────────────────────────────────────
@dataclass
class SafetyConfig:
    max_speed_kph: float = 60.0
    perception_fail_frames: int = 10   # emergency stop after N frames w/o road
    emergency_brake_force: float = 1.0
    collision_decel_threshold: float = 15.0   # m/s² — likely crash


# ── Debug & Logging ────────────────────────────────────────────────
@dataclass
class DebugConfig:
    show_overlay: bool = True          # live OpenCV debug window
    print_telemetry: bool = True       # console telemetry every tick
    telemetry_interval: int = 10       # print every N ticks
    save_frames: bool = False          # dump camera frames to disk
    frame_save_dir: str = "logs/frames"
    log_csv: bool = True               # log telemetry to CSV
    csv_path: str = "logs/telemetry.csv"


# ── Loop Timing ────────────────────────────────────────────────────
@dataclass
class LoopConfig:
    target_hz: float = 20.0           # main‑loop frequency
    beamng_steps: int = 10            # simulation steps per tick


# ── Aggregate Config ───────────────────────────────────────────────
@dataclass
class Config:
    beamng: BeamNGConfig = field(default_factory=BeamNGConfig)
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    steering: SteeringPIDConfig = field(default_factory=SteeringPIDConfig)
    speed: SpeedControlConfig = field(default_factory=SpeedControlConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)


# Default singleton — import this everywhere
CFG = Config()
