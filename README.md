# SelfDriveBeamNGTech

Autonomous self-driving system — **default: BeamNG.tech**.

The project now ships a single Python script (`beamng_driver.py`) that runs
directly inside **BeamNG.tech** using the BeamNGpy API.
A legacy Assetto Corsa stack is still available via the `--ac` flag (see below).

---

## Quick Start (BeamNG.tech — default)

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Set your BeamNG install path

Open `beamng_driver.py` and edit the top-level constant:

```python
BEAMNG_HOME: str = r"C:\BeamNG.tech"   # ← set your install path here
```

Or pass it on the command line:

```powershell
python beamng_driver.py --beamng-home "C:\BeamNG.tech"
```

### 3. Run

```powershell
# Use the main entry point (defaults to BeamNG.tech with built-in AI self-driving)
python main.py

# Or run the single script directly
python beamng_driver.py

# Incremental bring-up stages
python main.py --stage idle
python main.py --stage cruise --speed 15
python main.py --stage ai --speed 20
python main.py --stage custom --speed 8
python main.py --stage custom --speed 8 --steering-log logs/steering_output.csv

# Change target speed
python beamng_driver.py --speed 60

# Disable the live debug window
python beamng_driver.py --no-overlay

# All options
python beamng_driver.py --help
```

**Keyboard shortcuts (debug window):**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `e` | Toggle manual emergency stop |

---

## Legacy Assetto Corsa Mode

If you want to run the original Assetto Corsa driver, add the `--ac` flag:

```powershell
# Classical CV (no model needed)
python main.py --ac --mode classical

# Neural mode (train first)
python main.py --ac --mode neural --debug
```

Assetto Corsa must be running with the ACDriverApp Python app enabled.

### One-Time Setup (Assetto Corsa)

1. Install Steam and Assetto Corsa
2. Install Git for Windows: https://git-scm.com/download/win
3. Launch Assetto Corsa once so this folder exists:

```text
%USERPROFILE%\Documents\Assetto Corsa\
```

```powershell
# Setup
.\scripts\setup_windows.ps1

# Install telemetry app
.\scripts\install_ac_app.ps1

# Run classical mode
.\scripts\run_classical.ps1 -DebugView

# Collect training data
.\scripts\collect_data.ps1

# Train model
.\scripts\train_model.ps1 -Epochs 30 -BatchSize 32
```

See the full AC setup details in [autonomy_project/README.md](autonomy_project/README.md).

---

## Control Modes (AC legacy)

Edit [config.py](config.py):

- `mode = "keys"` for easiest first run
- `mode = "vjoy"` for smoother analog control (recommended after first run)
