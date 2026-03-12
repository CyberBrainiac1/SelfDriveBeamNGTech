# AC Driver (Assetto Corsa Autonomy)

This is a full autonomous driving stack for Assetto Corsa with:

- Classical mode: OpenCV lane detection + PID
- Neural mode: NVIDIA-style CNN steering model
- Control output: vJoy analog (recommended) or keyboard fallback

## Start Here If You Do Not Have Assetto Corsa Installed

If this is your first time, do these first:

1. Install Steam
2. Buy/install Assetto Corsa (Ultimate Edition recommended so you have more tracks/cars)
3. Launch the game once from Steam so it creates:

```text
%USERPROFILE%\Documents\Assetto Corsa\
```

4. In video settings, run in a fixed resolution (for easier capture-region setup)

After that, continue with Fast Start below.

## Fast Start (Exact Steps)

Follow these in order with no skips.

### 1. Open terminal in repo root

```powershell
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 2. Install Python dependencies

```powershell
pip install -r ac_driver\requirements.txt
```

### 3. Install the AC in-game telemetry app

Copy this folder:

```text
ac_driver\ac_app\ACDriverApp\
```

Into this folder:

```text
%USERPROFILE%\Documents\Assetto Corsa\apps\python\ACDriverApp\
```

Result should be:

```text
%USERPROFILE%\Documents\Assetto Corsa\apps\python\ACDriverApp\ACDriverApp.py
%USERPROFILE%\Documents\Assetto Corsa\apps\python\ACDriverApp\ui\ACDriverApp.ini
```

Quick verification command:

```powershell
Test-Path "$env:USERPROFILE\Documents\Assetto Corsa\apps\python\ACDriverApp\ACDriverApp.py"
```

It should print `True`.

### 4. Enable ACDriverApp in Assetto Corsa

In game:

1. Open Assetto Corsa
2. Go to Options -> General -> UI Modules
3. Enable ACDriverApp
4. Start a practice session and drive once to confirm telemetry updates

After driving for a few seconds, verify telemetry file exists:

```powershell
Test-Path "$env:USERPROFILE\Documents\Assetto Corsa\logs\acdriver_state.json"
```

### 5. Choose control mode (important)

Edit [ac_driver/config.py](ac_driver/config.py):

- For easiest first run, keep:

```python
mode = "keys"
```

- For smooth steering (recommended), install vJoy and set:

```python
mode = "vjoy"
```

If using vJoy:

1. Install vJoy from https://github.com/jshafer817/vJoy/releases
2. Open vJoyConf and enable axes X, Y, Z on device 1
3. In AC Controls, bind steering/throttle/brake to vJoy axes

### 6. Set your capture region

In [ac_driver/config.py](ac_driver/config.py), set `monitor_region` to your AC window.

Examples:

- 1920x1080 fullscreen: `(0, 40, 1920, 1080)`
- 800x600 windowed: `(0, 40, 800, 600)`

### 7. Run first autonomous drive (no training required)

```powershell
python ac_driver\main.py --mode classical --debug
```

What success looks like:

- Terminal prints FPS/speed/steer/reward
- Debug window opens
- Car starts steering and throttle/brake control automatically

Stop with `Ctrl+C` or press `q` in debug window.

## First-Day Checklist

- Assetto Corsa installed and launched once
- ACDriverApp copied into `Documents\Assetto Corsa\apps\python\`
- ACDriverApp enabled in UI Modules
- `acdriver_state.json` file appears while driving
- `mode` in [ac_driver/config.py](ac_driver/config.py) is set correctly (`keys` first run is easiest)
- `monitor_region` matches your actual game window

## Neural Mode (Train Your Own Model)

### 1. Collect data (you drive manually)

```powershell
python ac_driver\scripts\collect_data.py
```

Press `q` when done. Data shards are saved under `ac_driver\data\`.

### 2. Train model

```powershell
python ac_driver\scripts\train.py --epochs 30 --batch-size 32
```

Model is saved to:

```text
ac_driver\models\acdriver_model.keras
```

### 3. Run neural driving

```powershell
python ac_driver\main.py --mode neural --debug
```

## Daily Use (Short Commands)

Classical:

```powershell
python ac_driver\scripts\run_classical.py --debug
```

Neural:

```powershell
python ac_driver\scripts\run_neural.py --debug
```

## Logs and Metrics

- Tick CSV and lap CSV are written to `ac_driver\logs\`
- Lap summary includes:
  - lap time
  - average speed
  - infractions
  - smoothness (log-dimensionless jerk)

## Troubleshooting

### No telemetry / timed out waiting for AC

Check:

1. ACDriverApp is enabled in UI Modules
2. You are in an active track session (not only menu)
3. File exists and updates:

```text
%USERPROFILE%\Documents\Assetto Corsa\logs\acdriver_state.json
```

### Car does not steer correctly

Check:

1. `monitor_region` matches your game window
2. Correct control mode (`keys` or `vjoy`) in [ac_driver/config.py](ac_driver/config.py)
3. For vJoy, axis mappings are done in AC Controls

### Neural mode says model not found

Run training first:

```powershell
python ac_driver\scripts\train.py
```

## Optional: Run tests

```powershell
cd ac_driver
pytest tests -v
```

## Project Layout

- [ac_driver/main.py](ac_driver/main.py): runtime loop
- [ac_driver/config.py](ac_driver/config.py): all settings
- [ac_driver/agents/base_agent.py](ac_driver/agents/base_agent.py): abstract agent interface
- [ac_driver/track/lap_tracker.py](ac_driver/track/lap_tracker.py): l2r-inspired progress/lap tracking
- [ac_driver/utils/metrics_logger.py](ac_driver/utils/metrics_logger.py): CSV metrics
