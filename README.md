# SelfDriveBeamNGTech

Main project: autonomous driving for Assetto Corsa (this repository root).

The older BeamNG project is still available in [autonomy_project/README.md](autonomy_project/README.md),
but Assetto Corsa is now the default and primary stack.

## First-Time Setup (No Assetto Corsa Installed Yet)

1. Install Steam
2. Buy/install Assetto Corsa
3. Install Python 3.9+ and check "Add Python to PATH"
4. Launch Assetto Corsa once so this folder exists:

```text
%USERPROFILE%\Documents\Assetto Corsa\
```

5. Install Git for Windows: https://git-scm.com/download/win

## Fresh Machine (No Repo Cloned Yet)

If the user does not have this repository yet, run one of these from PowerShell.

Option A (recommended for most users, no admin): clone under user profile

```powershell
irm https://raw.githubusercontent.com/CyberBrainiac1/SelfDriveBeamNGTech/main/scripts/clone_and_setup.ps1 -OutFile "$env:TEMP\clone_and_setup.ps1"
& "$env:TEMP\clone_and_setup.ps1" -InstallRoot "$env:USERPROFILE\SelfDrive" -InstallAcApp
```

Option B (admin): clone under Program Files

```powershell
irm https://raw.githubusercontent.com/CyberBrainiac1/SelfDriveBeamNGTech/main/scripts/clone_and_setup.ps1 -OutFile "$env:TEMP\clone_and_setup.ps1"
& "$env:TEMP\clone_and_setup.ps1" -InstallRoot "$env:ProgramFiles\SelfDrive" -InstallAcApp
```

After bootstrap finishes, launch Assetto Corsa and enable ACDriverApp in UI Modules.

The bootstrap/setup scripts auto-detect the current Windows user via environment variables
(`$env:USERNAME`, `$env:USERPROFILE`) so paths are user-specific automatically.

## Quick Start (Copy/Paste)

Run these commands exactly, from any location (even `C:\WINDOWS\system32`):

```powershell
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt

# Copy telemetry app into Assetto Corsa
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\Assetto Corsa\apps\python" | Out-Null
Copy-Item -Recurse -Force .\ac_app\ACDriverApp "$env:USERPROFILE\Documents\Assetto Corsa\apps\python\"

# Start autonomous drive (classical mode)
python .\main.py --mode classical --debug
```

## Even Easier: One-Command PowerShell Scripts

From repository root:

```powershell
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"
```

Setup Python environment and dependencies:

```powershell
.\scripts\setup_windows.ps1
```

This also registers a global `autoac` command in your PowerShell profile.
Open a new terminal after setup, then use these simple commands:

```powershell
autoac help
autoac install-app
autoac run -Debug
autoac run-neural -Debug
autoac collect
autoac train -Epochs 30 -BatchSize 32
autoac status
```

Install AC telemetry app files:

```powershell
.\scripts\install_ac_app.ps1
```

Run classical mode:

```powershell
.\scripts\run_classical.ps1 -DebugView
```

Run neural mode:

```powershell
.\scripts\run_neural.ps1 -DebugView
```

Collect training data:

```powershell
.\scripts\collect_data.ps1
```

Train model:

```powershell
.\scripts\train_model.ps1 -Epochs 30 -BatchSize 32
```

If PowerShell blocks activation, run this once then retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## In-Game Setup (Required)

1. Open Assetto Corsa
2. Go to Options -> General -> UI Modules
3. Enable ACDriverApp
4. Start a practice session

Verify telemetry file is updating while driving:

```powershell
Test-Path "$env:USERPROFILE\Documents\Assetto Corsa\logs\acdriver_state.json"
```

## Control Modes

Edit [config.py](config.py):

- `mode = "keys"` for easiest first run
- `mode = "vjoy"` for smoother analog control (recommended after first run)

vJoy optional setup:

1. Install from https://github.com/jshafer817/vJoy/releases
2. Enable X, Y, Z axes in vJoyConf
3. Bind those axes in Assetto Corsa controls

## Neural Mode

Collect data:

```powershell
python .\scripts\collect_data.py
```

Train model:

```powershell
python .\scripts\train.py --epochs 30 --batch-size 32
```

Run neural driver:

```powershell
python .\main.py --mode neural --debug
```
