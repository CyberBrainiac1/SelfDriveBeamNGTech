# AC Driver

An autonomous driving system for **Assetto Corsa** built from scratch in Python.

Inspired by [denfed/ACDriver](https://github.com/denfed/ACDriver) and the architecture of [learn-to-race/l2r](https://github.com/learn-to-race/l2r). All bugs from the original ACDriver have been fixed; the codebase is entirely original.

---

## How it works

```
Screen capture ──► Agent ──► ControlArbiter ──► Game input
                    ↑              ↓
             AC telemetry    vJoy / WASD
                    ↓
              LapTracker  →  MetricsLogger
```

Two driving modes:

| Mode | How it steers | Needs model? |
|------|--------------|-------------|
| `classical` | OpenCV lane detection → PID | No |
| `neural` | NVIDIA CNN end-to-end | Yes (train first) |

Both modes use a **PID speed controller** and the same **LapTracker / MetricsLogger** pipeline.

---

## Architecture

```
ac_driver/
├── config.py                  # all tunables in one place
├── main.py                    # main loop
│
├── ac_app/ACDriverApp/        # in-game Python app (runs inside AC)
│   └── ACDriverApp.py         # writes JSON telemetry
│
├── agents/                    # l2r-style abstract agent interface
│   ├── base_agent.py          # AbstractAgent + Observation dataclass
│   ├── classical_agent.py     # lane detection + PID
│   └── neural_agent.py        # NVIDIA CNN steering
│
├── capture/
│   ├── screen_capture.py      # mss screen grabber
│   └── ac_state_reader.py     # reads telemetry JSON
│
├── perception/
│   └── lane_detection.py      # HSV mask → Canny → Hough → offset
│
├── control/
│   ├── direct_keys.py         # DirectInput WASD fallback
│   ├── vjoy_output.py         # vJoy analog axes (preferred)
│   ├── steering_controller.py # PID steering
│   ├── speed_controller.py    # PID speed → throttle/brake
│   └── control_arbiter.py     # merges outputs, picks vJoy or keys
│
├── training/
│   ├── data_collector.py      # record frames + AC steering labels
│   ├── model.py               # NVIDIA CNN (TF2/Keras)
│   ├── train_model.py         # train with augmentation + callbacks
│   └── infer.py               # SteeringPredictor class
│
├── track/
│   └── lap_tracker.py         # lap times, stuck/wrong-way, reward signal
│                              # (l2r GranTurismo reward + log-jerk metric)
│
├── utils/
│   ├── debug_overlay.py       # HUD overlay
│   ├── metrics_logger.py      # CSV logging, lap summaries
│   ├── timers.py              # RateLimiter, FPSCounter
│   └── image_utils.py         # image helpers
│
├── scripts/
│   ├── collect_data.py        # record training data
│   ├── train.py               # train the CNN
│   ├── run_classical.py       # drive (classical mode)
│   └── run_neural.py          # drive (neural mode)
│
└── tests/
    ├── test_lane_detection.py
    └── test_controllers.py
```

---

## Setup

### 1 — Install Python dependencies

```bash
cd ac_driver
pip install -r requirements.txt
```

For smooth **analog steering** (recommended), also install vJoy:
- Download from https://github.com/jshafer817/vJoy/releases
- Run `vJoyConf.exe` → device 1 → enable axes X, Y, Z
- Then in `config.py` set `control_out.mode = "vjoy"`

### 2 — Install the in-game app

Copy the app folder into Assetto Corsa:

```
ac_app\ACDriverApp\  →  Documents\Assetto Corsa\apps\python\ACDriverApp\
```

Launch AC, go to **Options → General → UI Modules** and enable **ACDriverApp**.

### 3 — Configure AC inputs

If using **vJoy**: go to AC Controls → map Steering/Gas/Brake from the vJoy device axes.

If using **WASD keys**: AC's keyboard bindings should already handle W/A/S/D.

### 4 — Adjust `config.py`

Key settings to check before running:

```python
# Screen region to capture (left, top, width, height)
monitor_region: (0, 40, 1920, 1080)   # adjust for your resolution/windowed mode

# Target cruise speed
target_kph: 60.0

# Control mode
mode: "keys"   # or "vjoy" if you installed the driver
```

---

## Running

### Classical mode (no training needed)

```bash
python ac_driver/main.py --mode classical --debug
# or via shortcut:
python ac_driver/scripts/run_classical.py --debug
```

### Neural mode

First collect training data (drive a few laps manually with AC open):

```bash
python ac_driver/scripts/collect_data.py
```

Then train the model:

```bash
python ac_driver/scripts/train.py --epochs 30
```

Then run:

```bash
python ac_driver/main.py --mode neural --debug
# or:
python ac_driver/scripts/run_neural.py
```

---

## Metrics (l2r-inspired)

After each lap the terminal prints a summary:

```
────────────────────────────────────────────────
  LAP 1 COMPLETE
────────────────────────────────────────────────
  Time        : 87.43 s
  Avg speed   : 62.1 kph
  Infractions : 0
  Smoothness  : -4.2312   (more negative = smoother)
  Avg |steer| : 0.0841
────────────────────────────────────────────────
```

Full per-tick and per-lap CSV logs are saved to `logs/`.

The **movement smoothness** metric is the log-dimensionless jerk score from Balasubramanian (2012), using the same formula as `learn-to-race/l2r`'s `ProgressTracker`.
The **progress reward** per tick is `Δspline_position × 100`, matching l2r's GranTurismo reward structure.

---

## Fixes vs original ACDriver

| Bug in original | Fix |
|---|---|
| `keras.optimizers.adam()` (broken TF2) | `keras.optimizers.Adam()` |
| `categorical_crossentropy` on regression | `mse` loss |
| `Dense(3, tanh)` for 3-class output | `Dense(1, tanh)` single steering value |
| Hardcoded `C:\Users\denni\...` paths | `os.path.expanduser("~")` + config |
| PIL.ImageGrab (slow) | mss |
| Object-array `.npy` files | Structured `.npz` shards |
| Steering `(deg+450)/900` → 0…1 | `deg/450` → -1…+1 |
| Incomplete AC app (5 lines) | Full `acMain/acUpdate/acShutdown` |
| WASD only (digital) | vJoy primary + WASD fallback |
| No lap tracking / metrics | `LapTracker` + `MetricsLogger` |

---

## Tests

```bash
cd ac_driver
pytest tests/ -v
```

Tests run without Assetto Corsa open — they use synthetic frames.
