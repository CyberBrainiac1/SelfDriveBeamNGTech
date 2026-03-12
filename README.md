# SelfDriveBeamNGTech

Main project: autonomous driving for Assetto Corsa (this repository root).

The older BeamNG project is still available in [autonomy_project/README.md](autonomy_project/README.md),
but Assetto Corsa is now the default and primary stack.

## First-Time Setup (No Assetto Corsa Installed Yet)

1. Install Steam
2. Buy/install Assetto Corsa
3. Install Git for Windows: https://git-scm.com/download/win
4. Launch Assetto Corsa once so this folder exists:

```text
%USERPROFILE%\Documents\Assetto Corsa\
```

Python can now be installed automatically by bootstrap/setup scripts (via winget).

## Fresh Machine (No Repo Cloned Yet)

Default install (works from any folder, no hardcoded path):

```powershell
irm https://raw.githubusercontent.com/CyberBrainiac1/SelfDriveBeamNGTech/main/scripts/clone_and_setup.ps1 -OutFile "$env:TEMP\clone_and_setup.ps1"
& "$env:TEMP\clone_and_setup.ps1" -InstallRoot "$env:USERPROFILE\SelfDrive" -InstallAcApp
```

Admin install to Program Files:

```powershell
irm https://raw.githubusercontent.com/CyberBrainiac1/SelfDriveBeamNGTech/main/scripts/clone_and_setup.ps1 -OutFile "$env:TEMP\clone_and_setup.ps1"
& "$env:TEMP\clone_and_setup.ps1" -InstallRoot "$env:ProgramFiles\SelfDrive" -InstallAcApp
```

After bootstrap finishes:

1. Open a new PowerShell window
2. Run `autoac status`
3. Start Assetto Corsa and enable ACDriverApp in UI Modules
4. Run `autoac run -Debug`

If Python is missing, bootstrap auto-installs it for the current user.

The bootstrap/setup scripts auto-detect the current Windows user via environment variables
(`$env:USERNAME`, `$env:USERPROFILE`) so paths are user-specific automatically.

## Even Easier: One-Command PowerShell Scripts

If you are already inside a local clone, setup is:

```powershell
.\scripts\setup_windows.ps1
```

If Python is missing, setup will auto-install it first.

This also registers a global `autoac` command in your PowerShell profile.
Open a new terminal after setup, then use these simple commands:

```powershell
autoac help
autoac install-app
autoac run -Debug
autoac drive -Debug
autoac run-neural -Debug
autoac neural -Debug
autoac collect
autoac train -Epochs 30 -BatchSize 32
autoac status
autoac doctor
autoac config-show
autoac mode -Value keys
autoac mode -Value vjoy
autoac speed -TargetSpeed 70
autoac logs
autoac tail-state -Lines 40
autoac update
```

If `autoac` is not recognized, run this once from your clone folder:

```powershell
.\scripts\register_autoac_command.ps1
```

Then open a new terminal (or run `. $PROFILE`) and retry `autoac help`.

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
