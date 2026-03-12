# SelfDriveBeamNGTech

A complete hardware + software system for a **self-driving / AI-assist steering wheel controller** built around **BeamNG.tech** (a realistic vehicle simulation game/research platform).

The project has two main parts that work together:

1. **Arduino Firmware** — runs on an Arduino Leonardo and physically controls a steering wheel through a brushed DC motor.
2. **Desktop App** — a Windows Python GUI that connects to both the Arduino (over USB serial) and BeamNG.tech (over TCP) and provides full configuration, telemetry, AI driving, and safety management.

---

## Table of Contents

- [What this project does](#what-this-project-does)
- [Hardware overview](#hardware-overview)
- [Repository layout](#repository-layout)
- [Firmware (Arduino)](#firmware-arduino)
  - [Operating modes](#operating-modes)
  - [PD controller](#pd-controller)
  - [Force Feedback (FFB) effects](#force-feedback-ffb-effects)
  - [Serial protocol](#serial-protocol)
  - [EEPROM / profiles](#eeprom--profiles)
  - [Safety](#safety)
- [Desktop App (Python / PySide6)](#desktop-app-python--pyside6)
  - [Core services](#core-services)
  - [Pages / UI](#pages--ui)
  - [BeamNG AI pipeline](#beamng-ai-pipeline)
  - [Auto Drive tab (Normal Wheel Mode)](#auto-drive-tab-normal-wheel-mode)
- [Getting started (Windows)](#getting-started-windows)
  - [1. One-time setup](#1-one-time-setup)
  - [2. Build the firmware hex](#2-build-the-firmware-hex)
  - [3. Flash to the Arduino](#3-flash-to-the-arduino)
  - [4. Launch the desktop app](#4-launch-the-desktop-app)
- [Folder reference](#folder-reference)
- [Configuration reference](#configuration-reference)
- [Tests](#tests)

---

## What this project does

```
BeamNG.tech  ←→  Desktop App (Python)  ←→  Arduino Leonardo  ←→  Steering Wheel + Motor
```

1. **BeamNG.tech** sends real-time vehicle telemetry (steering angle, speed, RPM, gear …) over a local TCP connection using the `beamngpy` library.
2. The **Desktop App** reads that telemetry, runs an AI control loop (or a replay, or a path-follower), and converts the chosen target steering angle into a serial JSON command.
3. The **Arduino firmware** receives the target angle over USB serial, runs a PD controller to drive the wheel motor to that position, and simultaneously sends back live telemetry at ~50 Hz.
4. The result: the **physical steering wheel turns by itself** to mirror whatever BeamNG is doing (AI drive), or to follow any other programmed trajectory — while the human driver can still override at any time (shared-control mode).

You can also run it as a **pure wheel controller** (no BeamNG): the wheel acts as a force-feedback USB joystick for any racing game.

---

## Hardware overview

| Component | Part |
|-----------|------|
| Microcontroller | **Arduino Leonardo** (ATmega32U4, USB-HID capable) |
| Motor driver | **BTS7960** dual H-bridge (high-current brushed DC) |
| Position sensor | **Quadrature encoder** on the steering shaft (default 2400 CPR) |
| Motor | Brushed DC motor driving the steering column via gearbox |
| PC interface | USB-CDC serial at 115 200 baud |

**Pin assignments:**

| Signal | Arduino Pin |
|--------|-------------|
| Encoder A | 2 (INT0 — hardware interrupt) |
| Encoder B | 3 (INT1 — hardware interrupt) |
| BTS7960 RPWM | 9 (PWM — clockwise / right) |
| BTS7960 LPWM | 10 (PWM — counter-clockwise / left) |
| BTS7960 R\_EN | 7 |
| BTS7960 L\_EN | 8 |
| Status LED | 13 (built-in) |

---

## Repository layout

```
SelfDriveBeamNGTech/
│
├── firmware/
│   └── normal_mode/
│       └── wheel_controller/
│           └── wheel_controller.ino   ← Arduino sketch (the firmware)
│
├── desktop_app/
│   ├── main.py          ← entry point (python main.py)
│   ├── app.py           ← wires all services together
│   ├── core/            ← serial, config, logger, safety, telemetry
│   ├── beamng/          ← BeamNG bridge, AI controller, shared control, replay
│   ├── pages/           ← one Python file per UI page
│   ├── profiles/        ← profile manager
│   ├── ui/              ← main window, stylesheet
│   └── widgets/         ← reusable UI widgets
│
├── docs/
│   └── FIRMWARE_ARCHITECTURE.md   ← detailed firmware reference
│
├── tests/               ← pytest unit tests
│
├── output/              ← generated files (hex, logs, profiles) — git-ignored
│
├── build_hex.ps1        ← compile firmware → output\firmware\wheel_controller.hex
├── flash_hex.ps1        ← flash hex to connected Arduino
├── run_app.ps1          ← launch the desktop app
├── diagnose.ps1         ← detect COM ports / board info
├── setup_windows.ps1    ← one-time Windows setup (Python venv + arduino-cli)
│
└── requirements.txt
```

---

## Firmware (Arduino)

**File:** `firmware/normal_mode/wheel_controller/wheel_controller.ino`
**Target:** Arduino Leonardo (ATmega32U4)
**Version:** 2.0.0

The firmware is a tight real-time control loop that:

- Counts encoder pulses using hardware interrupts to get precise steering angle.
- Runs a **PD controller** to track a target angle (for AI / ANGLE\_TRACK mode).
- Applies **Force Feedback effects** (spring centering, damping, friction, inertia) in FFB modes.
- Exposes a **USB HID joystick axis** so the wheel appears as a game controller.
- Persists settings to **EEPROM** across power cycles.
- Sends **JSON telemetry** back to the PC at ~50 Hz.
- Receives **JSON commands** from the PC.

### Operating modes

| Mode | Motor behaviour | When used |
|------|----------------|-----------|
| `IDLE` | Off | Safe default on boot |
| `NORMAL_HID` | FFB effects (spring + damper + friction + inertia) | Normal driving / game play |
| `ANGLE_TRACK` | PD controller follows target angle | AI driving, replay playback |
| `ASSIST` | FFB effects (same as NORMAL\_HID) | Shared control — human feels resistance from AI |
| `CALIBRATION` | Manual motor test pulses only | Setting up hardware |
| `ESTOP` | Off, driver disabled | Emergency stop — latched until explicit `set_mode` |

### PD controller

Used in `ANGLE_TRACK` mode:

```
error    = target_angle − current_angle
integral += error × dt            (±20° anti-windup)
output   = kp×error − kd×velocity + ki×integral
```

If `|error| < dead_zone` → output = 0, integrator reset (prevents buzz around centre).

### Force Feedback (FFB) effects

Used in `NORMAL_HID` and `ASSIST` modes:

```
spring   = −centering × current_angle
damper   = −damping   × velocity
friction = −sign(velocity) × friction × max_motor   (if |vel| > 0.5 °/s)
inertia  = −inertia   × acceleration
output   = (spring + damper + inertia) × max_motor + friction
smoothed = smoothed × smoothing + output × (1 − smoothing)
```

All gains are stored in EEPROM and tunable from the desktop app in real time.

### Serial protocol

All messages are **single-line JSON terminated with `\n`** at 115 200 baud.

**Commands (PC → Arduino):**

| Command | Key fields | Description |
|---------|-----------|-------------|
| `ping` | — | Returns `{"t":"pong"}` |
| `get_version` | — | Returns firmware version |
| `set_mode` | `mode` | Switch operating mode (IDLE, NORMAL\_HID, ANGLE\_TRACK, …) |
| `set_target` | `angle` | Set target steering angle in degrees |
| `set_config` | `key`, `value` | Change one config parameter (kp, kd, centering, …) |
| `get_config` | — | Dump full config as JSON |
| `save_config` | — | Write current config to EEPROM |
| `load_config` | — | Reload config from EEPROM |
| `save_profile` | `slot` (0–3), `name` | Save current config as a named profile |
| `load_profile` | `slot` (0–3) | Load a saved profile |
| `list_profiles` | — | List all profile slot names |
| `factory_reset` | — | Erase EEPROM and reload safe defaults |
| `zero_encoder` | — | Set encoder position to zero here |
| `set_center` | — | Set wheel centre position here |
| `motor_test` | `dir`, `pwm` | Brief motor pulse for hardware testing (CAL mode only) |
| `clear_faults` | — | Clear fault flags |
| `estop` | — | Immediate motor cutoff |

**Telemetry (Arduino → PC, ~50 Hz):**

```json
{"t":"telem","angle":42.3,"target":45.0,"motor":120,
 "mode":"ANGLE_TRACK","enc":1234,"vel":18.5,
 "fault":0,"profile":"Normal","uptime":60}
```

| Field | Meaning |
|-------|---------|
| `angle` | Current steering angle (degrees from centre) |
| `target` | Current target angle the PD controller is tracking |
| `motor` | PWM output to motor (−255 to +255) |
| `mode` | Current operating mode |
| `enc` | Raw encoder tick count |
| `vel` | Angular velocity (°/s) |
| `fault` | Bit-field of active faults (see below) |
| `profile` | Active profile name |
| `uptime` | Seconds since boot |

**Fault flags:**

| Bit | Value | Meaning |
|-----|-------|---------|
| 0 | 0x01 | Serial timeout — motor killed because PC went quiet |
| 1 | 0x02 | Angle clamped to configured range limit |
| 2 | 0x04 | EEPROM invalid — using safe defaults |
| 3 | 0x08 | Motor overload (reserved for future use) |

### EEPROM / profiles

Settings survive power-off in a compact binary layout:

```
Address 0x000  uint32_t magic     (0xABCD1234 = data is valid)
Address 0x004  WheelConfig        active config (~56 bytes)
Address 0x040  ProfileSlot[4]     4 named presets (~76 bytes each)
─────────────────────────────────────────────────────────────────
Total used: ~352 of 1024 bytes
```

On boot, if the magic number is missing (blank board or after `factory_reset`), the firmware loads safe defaults and sets the `FAULT_EEPROM_DEFAULTS` flag.

### Safety

- Motor is **off at boot** until explicitly commanded.
- **Serial watchdog**: if no command arrives for 500 ms in ANGLE\_TRACK or ASSIST mode, the motor is cut and `FAULT_SERIAL_TIMEOUT` is set.
- **Angle clamp**: output is always bounded by `angle_range / 2`.
- **Max PWM ceiling** enforced in every code path via `max_motor`.
- **ESTOP** disables both H-bridge enable pins (motor driver physically off) and is latched until a new `set_mode` command arrives.

---

## Desktop App (Python / PySide6)

**Entry point:** `desktop_app/main.py`
**Framework:** PySide6 (Qt 6 for Python)
**Launch:** `.\run_app.ps1` or `python desktop_app/main.py`

The app is structured as a classic MVC-style application: core service singletons are created in `app.py` and passed by dependency-injection to every page.

### Core services

Located in `desktop_app/core/`:

| Module | Class | What it does |
|--------|-------|--------------|
| `serial_manager.py` | `SerialManager` | Opens the serial port, sends JSON commands, parses incoming JSON telemetry, emits Qt signals for each message type |
| `config_manager.py` | `ConfigManager` | Loads/saves `config.toml` — persists user preferences (last COM port, baud, BeamNG host/port, safety limits, …) |
| `safety_manager.py` | `SafetyManager` | Software angle clamp, ESTOP coordination, AI-mode safety gate, watchdog timer that triggers ESTOP if the AI control loop hangs |
| `telemetry.py` | `TelemetryBuffer` | Ring buffer of the last N telemetry frames; provides history arrays for the live charts |
| `logger.py` | `AppLogger` | Loguru-backed logger; emits Qt signals so log lines appear in the Logs page |

### Pages / UI

The main window is a **sidebar + stacked pages** layout. Navigation is a list on the left; clicking any item swaps the central panel.

| Page | File | What you can do |
|------|------|-----------------|
| **Dashboard** | `dashboard.py` | At-a-glance status: serial connected/disconnected badge, BeamNG badge, live angle + speed + RPM readout, quick action buttons (Zero encoder, E-stop, Go to calibration) |
| **Normal Wheel Mode** | `normal_wheel_page.py` | Full EMC-style control panel — serial connect/disconnect, wheel setup (angle range, encoder CPR, gear ratio, invert), PD gains, FFB gains, profile management, live angle + motor chart, diagnostics log, motor test, firmware build/flash, and the **Auto Drive tab** |
| **Tuning** | `tuning_page.py` | Fine-tune PD and FFB parameters with real-time effect; sliders push `set_config` commands live |
| **Calibration** | `calibration_page.py` | Step-by-step guided calibration: set wheel centre, measure encoder counts, test motor direction, verify range |
| **Tests & Diagnostics** | `tests_diagnostics_page.py` | Ping test, motor test pulses, read raw telemetry, trigger fault clearing |
| **BeamNG.tech AI Mode** | `beamng_ai_page.py` | Connect to a running BeamNG.tech instance, choose AI source (BEAMNG / MANUAL\_TEST / REPLAY / PATH\_FOLLOW / LANE\_CENTER), set manual target, load replay file, shared-control authority slider, start/stop AI, emergency disengage |
| **Profiles** | `profiles_page.py` | Save / load / rename the 4 EEPROM profile slots; import/export profile JSON files |
| **Settings** | `settings_page.py` | BeamNG host + port, safety limits, UI preferences |
| **Logs** | `logs_page.py` | Scrolling live log viewer with copy and clear buttons |

### BeamNG AI pipeline

```
BeamNG.tech
   │  beamngpy TCP
   ▼
BeamNGManager          polls vehicle sensors at ~20 Hz, emits vehicle_state(dict)
   │
   ▼
BeamNGBridge           converts normalised steering (−1…+1) → wheel degrees,
   │                   applies safety clamp, calls serial.set_target(angle)
   │
   ▼
AIController           50 Hz control loop; chooses target from one of:
   │                     • BEAMNG      — live BeamNG steering_input
   │                     • MANUAL_TEST — slider value from UI
   │                     • REPLAY      — frame from a recorded CSV
   │                     • PATH_FOLLOW — simple proportional path follower
   │                     • LANE_CENTER — stub for future vision pipeline
   │
   ▼
SerialManager          sends {"cmd":"set_target","angle":X} to Arduino

SharedControl          blends human input + AI target (authority 0.0→1.0)
ReplayController       records live steering to CSV / plays back CSV files
```

**`AIController`** runs in a background thread at 50 Hz.
- Calls `safety.heartbeat()` every tick to keep the watchdog alive.
- Only sends serial commands for non-BEAMNG sources (BEAMNG is handled by `BeamNGBridge.process_vehicle_state`).
- Calls `safety.enter_ai_mode()` on start — if ESTOP is active or serial is disconnected the start is blocked.

**`SafetyManager`** is the authority on what the motor is allowed to do:
- `clamp_target()` — hard angle limit.
- `enter_ai_mode()` — gated on serial connected + no active ESTOP.
- `trigger_estop()` — sends `estop` command to Arduino AND emits a Qt signal for the UI.
- `watchdog` — background thread that fires ESTOP if the AI loop stops calling `heartbeat()`.

### Auto Drive tab (Normal Wheel Mode)

The **Normal Wheel Mode** page has a built-in **"Auto Drive"** tab (4th tab in the right panel) so you can start the AI without navigating away from the main wheel control page:

```
┌─ BEAMNG CONNECTION ─────────────────────────────────────────────┐
│  [● badge]   [Connect BeamNG / Disconnect BeamNG]               │
└─────────────────────────────────────────────────────────────────┘
┌─ AUTO DRIVE CONTROL ────────────────────────────────────────────┐
│  Source: [BEAMNG ▼]   (BEAMNG / MANUAL_TEST / PATH_FOLLOW / …) │
│  [▶ Start Auto Drive]    [■ Stop]                               │
│  Status: Stopped                                                │
└─────────────────────────────────────────────────────────────────┘
┌─ AI TELEMETRY ──────────────────────────────────────────────────┐
│  AI TARGET     AI MODE                                          │
│    42.5°         BEAMNG                                         │
└─────────────────────────────────────────────────────────────────┘
[⚠  EMERGENCY DISENGAGE]   ← always pinned at the bottom
```

- **Connect BeamNG** — connects/disconnects to the running BeamNG.tech instance.
- **Source selector** — pick which AI source drives the wheel.
- **Start / Stop** — start or stop the 50 Hz AI control loop.
- **Emergency Disengage** — immediately stops the AI loop AND sends a system-wide ESTOP to the Arduino.
- If BeamNG disconnects mid-session the AI stops automatically.
- Vehicle state is only forwarded to the bridge while the AI is running.

---

## Getting started (Windows)

### 1. One-time setup

```powershell
# Run as Administrator for best results
.\setup_windows.ps1
```

This script:
1. Checks Python 3.10+ is installed.
2. Creates a virtual environment at `.\venv\`.
3. Installs all Python dependencies from `requirements.txt` (`PySide6`, `pyserial`, `beamngpy`, `numpy`, `scipy`, `pydantic`, `toml`, `loguru`).
4. Downloads `arduino-cli` to `.\tools\` if not already present.
5. Installs the **Arduino AVR core** (needed to compile for Leonardo).
6. Creates `output\firmware`, `output\logs`, `output\profiles` directories.

### 2. Build the firmware hex

```powershell
.\build_hex.ps1
# Compiles wheel_controller.ino → output\firmware\wheel_controller.hex
```

### 3. Flash to the Arduino

Connect the Arduino Leonardo via USB, then:

```powershell
.\flash_hex.ps1                # auto-detect port
.\flash_hex.ps1 -Port COM3    # explicit port
```

Run `.\diagnose.ps1` first if you are not sure which COM port the Leonardo is on.

### 4. Launch the desktop app

```powershell
.\run_app.ps1
# or directly:
cd desktop_app && python main.py
# Launch straight into BeamNG AI mode:
python main.py --beamng-mode
```

---

## Folder reference

| Path | Contents |
|------|----------|
| `firmware/normal_mode/wheel_controller/` | Arduino sketch source |
| `output/firmware/` | Compiled `.hex` file (generated, not committed) |
| `output/logs/` | Steering replay CSV recordings |
| `output/profiles/` | Exported profile JSON files |
| `desktop_app/core/` | Serial, config, safety, telemetry, logging |
| `desktop_app/beamng/` | BeamNGManager, BeamNGBridge, AIController, SharedControl, ReplayController |
| `desktop_app/pages/` | One file per UI page |
| `desktop_app/ui/` | MainWindow and global dark stylesheet |
| `desktop_app/widgets/` | CollapsibleSection, MiniChart, StatusBadge |
| `desktop_app/profiles/` | ProfileManager |
| `tests/` | pytest unit tests (run with `pytest tests/`) |
| `docs/` | Detailed firmware architecture reference |

---

## Configuration reference

Key EEPROM / WheelConfig fields (all tunable live from the app):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kp` | 1.8 | PD proportional gain |
| `kd` | 0.12 | PD derivative gain |
| `ki` | 0.0 | PD integral gain |
| `dead_zone` | 1.5° | Error band with no motor output |
| `angle_range` | 540° | Total steering rotation range |
| `counts_per_rev` | 2400 | Encoder CPR (×4 quadrature) |
| `gear_ratio` | 1.0 | Motor-to-shaft gearbox ratio |
| `max_motor` | 200 | Absolute PWM ceiling (0–255) |
| `slew_rate` | 20 | Max PWM change per loop (0 = off) |
| `centering` | 1.0 | Spring-centre strength |
| `damping` | 0.12 | Velocity-proportional resistance |
| `friction` | 0.05 | Constant rotational resistance |
| `inertia` | 0.04 | Acceleration-proportional resistance |
| `smoothing` | 0.10 | LP filter on motor output (0–0.95) |

---

## Tests

```powershell
cd /path/to/repo
pip install pytest
pytest tests/
```

Tests cover:

| File | What is tested |
|------|---------------|
| `test_firmware_protocol.py` | Every JSON command the serial manager can send; telemetry parsing; config response parsing; profile import/export round-trip |
| `test_telemetry.py` | `TelemetryFrame` parsing, fault flags, `TelemetryBuffer` push/history/stale detection |
| `test_beamng_bridge.py` | `BeamNGBridge` angle↔normalised conversion, vehicle state processing, inactive bridge does not send |
| `test_config_manager.py` | TOML load/save, default values, missing keys |
| `test_safety_manager.py` | ESTOP trigger/clear, angle clamp, AI mode gate |
| `test_autodrive_panel.py` | All Auto Drive tab handler methods: BeamNG connect/disconnect, vehicle state forwarding, start/stop/estop, live readout labels |
