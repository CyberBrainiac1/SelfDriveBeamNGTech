# Custom Autonomous Driving System — BeamNG.tech

A modular, DIY autonomous driving stack built on top of **BeamNG.tech** and **BeamNGpy**.  
This is **not** a wrapper around BeamNG's built-in AI driver — it is a custom perception → planning → control pipeline that reads simulator sensor data and computes its own steering, throttle, and brake commands.

---

## Architecture

```
BeamNG.tech / BeamNGpy
  └── beamng_interface/     sensor acquisition, vehicle control
        └── perception/     lane detection, obstacle detection, state estimation
              └── planning/ path planner, behavior state machine, target generation
                    └── control/  PID steering, speed controller, arbiter
                          └── vehicle actuation (BeamNG) + future: physical wheel
```

### Pipeline each tick

1. **Sim step** — advance BeamNG physics
2. **Sensors** — read front camera (colour + depth), electrics, damage, g-forces
3. **Perception** — OpenCV lane detection, depth-based obstacle check, state estimation
4. **Planning** — behavior mode (DRIVE / EMERGENCY / STOPPED), path target, speed target
5. **Control** — PID steering, PID speed → throttle/brake, safety arbiter
6. **Actuation** — send commands to BeamNG vehicle
7. **Debug** — live overlay window, CSV logging, optional frame saves

---

## Folder Structure

```
autonomy_project/
├── main.py                   # entry point — runs the full loop
├── config.py                 # all tunables in one place
├── requirements.txt
├── beamng_interface/
│   ├── connection.py         # BeamNG launch / connect / disconnect
│   ├── scenario_manager.py   # create map, spawn vehicle
│   ├── sensors.py            # camera, electrics, damage, g-forces
│   ├── vehicle_control.py    # send steering/throttle/brake
│   └── data_logger.py        # CSV telemetry + frame saver
├── perception/
│   ├── lane_detection.py     # OpenCV road/lane centre detection
│   ├── obstacle_detection.py # depth-buffer obstacle check
│   ├── road_analysis.py      # road-visibility helpers
│   └── state_estimation.py   # aggregate vehicle state
├── planning/
│   ├── path_planner.py       # lane-offset → steering target
│   ├── behavior_planner.py   # DRIVE / EMERGENCY / STOPPED mode
│   └── target_generator.py   # produce speed + steering targets
├── control/
│   ├── steering_controller.py # PID with deadband + rate limiting
│   ├── speed_controller.py    # PID throttle / brake with coast band
│   └── control_arbiter.py     # merge + safety override
├── utils/
│   ├── image_utils.py
│   ├── math_utils.py
│   ├── debug_overlay.py      # live OpenCV debug HUD
│   ├── steering_output.py    # serial hook for DIY steering wheel
│   └── timers.py
├── scripts/
│   ├── run_demo.py           # CLI launcher with overrides
│   ├── calibrate_sensors.py  # tune HSV thresholds interactively
│   └── replay_log.py         # replay CSV + saved frames
├── logs/                     # telemetry CSV and frames (git-ignored)
└── tests/                    # offline unit tests (no BeamNG needed)
```

---

## Prerequisites

| Requirement      | Notes                                                                     |
| ---------------- | ------------------------------------------------------------------------- |
| **BeamNG.tech**  | Licensed research/educational version. Install and note the install path. |
| **Python 3.10+** | 3.11 or 3.12 recommended.                                                 |
| **pip**          | For installing dependencies.                                              |

---

## Setup

```powershell
# 1. Open terminal in repo root (important)
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"

# 2. Create a virtual environment (recommended)
python -m venv .venv

# 3. Activate venv (PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r .\autonomy_project\requirements.txt

# 5. Edit config
#    Open .\autonomy_project\config.py and set:
#      - BeamNGConfig.home  -> your BeamNG.tech install folder
#      - ScenarioConfig.spawn_pos / spawn_rot_quat -> a good road spot
#      - Any PID gains, speed targets, etc. you want to tweak
```

If PowerShell blocks activation, run once then retry step 3:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Running

### Quick start

```powershell
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech\autonomy_project"
python .\main.py
```

A debug window will open showing the camera feed with lane-detection overlays, telemetry HUD, and control outputs.

**Keyboard shortcuts (debug window focused):**
| Key | Action |
|-----|--------|
| `q` | Quit |
| `e` | Toggle manual emergency stop |

### With CLI overrides

```powershell
python .\scripts\run_demo.py --speed 60 --no-overlay --save-frames
```

### Calibrate perception thresholds

```powershell
python .\scripts\calibrate_sensors.py
```

This shows the raw camera ROI, HSV mask, and edge detection side-by-side so you can tune the thresholds in `config.py`.

### Replay a logged session

```powershell
python .\scripts\replay_log.py --csv .\logs\telemetry.csv --frames .\logs\frames\
```

### Run tests (no BeamNG needed)

```powershell
pip install pytest
python -m pytest .\tests\ -v
```

---

## What is confirmed vs assumed

### Confirmed (based on BeamNGpy docs)

- `BeamNGpy` connection, `Scenario`, `Vehicle` creation
- `Camera` sensor with colour + depth
- `Electrics`, `Damage`, `GForces` sensors
- `vehicle.control(steering=, throttle=, brake=)` for actuation
- Paused stepping with `bng.control.step(n)`

### Assumed / may need adjustment

- **Camera sensor API**: The exact constructor args (especially `pos`, `dir`, `near_far_planes`) may vary between BeamNGpy versions. If the camera doesn't render, check the BeamNGpy changelog and adjust `sensors.py`.
- **Spawn coordinates**: The default spawn position is for `west_coast_usa`. You may need to adjust for your BeamNG.tech version or preferred map.
- **HSV thresholds**: The road-colour mask is tuned for typical grey asphalt with default BeamNG lighting. Run `calibrate_sensors.py` to retune.
- **Sensor data format**: `cam.poll()` return structure may differ across versions; the code handles the most common formats.
- **Depth image units**: Assumed to be metres. If the values look wrong, check BeamNGpy docs.

---

## DIY Steering Wheel Integration

The codebase includes `utils/steering_output.py` — a hook for sending steering commands to an external microcontroller (Arduino, ESP32, etc.) over serial USB.

### How it works

1. The control arbiter produces a `ControlCommand` with `steering` in [-1.0, +1.0].
2. `SteeringOutput.send(steering)` writes the value to a serial port as `S+0.3250\n`.
3. Your microcontroller reads this and drives the force-feedback motor.

### To enable it

1. Install pyserial: `pip install pyserial`
2. In `main.py` or `control_arbiter.py`, add:
   ```python
   from utils.steering_output import SteeringOutput
   wheel = SteeringOutput(port="COM3", baudrate=115200, enabled=True)
   # In the main loop after computing cmd:
   wheel.send(cmd.steering)
   ```
3. Adjust the serial protocol in `steering_output.py` to match your firmware.

### Future modes

- **AI drives, wheel follows**: wheel reflects the autonomous steering target.
- **Human drives, AI coaches**: read wheel input via serial, compare to AI target, give feedback.
- **Shared control**: blend human input with AI output in `control_arbiter.py`.

---

## Next Upgrades (after v1 works)

1. **Waypoint following** — use BeamNG road network data or manual waypoints in `path_planner.py`.
2. **Neural lane detection** — train or use a pre-trained model; swap into `lane_detection.py`.
3. **LIDAR integration** — add BeamNGpy LIDAR sensor in `sensors.py`.
4. **Physical steering wheel output** — send `cmd.steering` over serial (USB) to your microcontroller.
5. **Shared control mode** — blend human wheel input with AI steering in `control_arbiter.py`.
6. **Traffic / other vehicles** — spawn traffic in `scenario_manager.py` and detect them.
7. **Model Predictive Control (MPC)** — replace PID with an MPC for smoother cornering.
8. **Dashboard GUI** — PyQt or web-based dashboard replacing the OpenCV debug window.
9. **Recording / imitation learning** — record human driving sessions and train a policy.

---

## Design Decisions

| Decision                   | Rationale                                                                                                       |
| -------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Classical CV first, not ML | Faster to debug, no training data needed, easy to understand for a student project. ML can be layered on later. |
| PID controllers            | Simple, well-understood, tunable. Good enough for lane following; upgrade to MPC when needed.                   |
| Dataclass configs          | Centralized, type-hinted, easy to override from CLI. No YAML/JSON parsing needed for v1.                        |
| Paused stepping            | Guarantees deterministic ticks — perception always gets fresh data before control runs.                         |
| Separate arbiter           | Single point for safety overrides, manual e-stop, and future shared control.                                    |
| CSV + frame logging        | Lightweight, no extra dependencies. Enables offline replay and debugging.                                       |

---

## License

This project is for educational / personal use with BeamNG.tech (research license).  
See BeamNG's terms for simulator usage.
