# SelfDriveBeamNGTech

Custom autonomous driving system built on BeamNG.tech.

A modular, DIY self-driving stack using BeamNG.tech sensor data with its own
perception, planning, and control pipeline. Not a wrapper around BeamNG's
built-in AI.

## Quick start

```powershell
# Run these from ANY location (including C:\WINDOWS\system32)
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"

# Create venv in the repo root
python -m venv .venv

# Activate it in PowerShell
.\.venv\Scripts\Activate.ps1

# Install deps
pip install -r .\autonomy_project\requirements.txt

# Edit autonomy_project/config.py to set your BeamNG.tech install path
cd .\autonomy_project
python .\main.py
```

If PowerShell blocks activation, run this once and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

See [`autonomy_project/README.md`](autonomy_project/README.md) for full documentation.
