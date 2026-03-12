# SelfDriveBeamNGTech

Primary project: autonomous driving for Assetto Corsa in `ac_driver/`.

This repo includes:
- `ac_driver/` (active): Assetto Corsa autonomy stack
- `autonomy_project/` (legacy): BeamNG.tech stack kept for reference

## Assetto Corsa Quick Start (recommended)

Run from any location (including `C:\WINDOWS\system32`):

```powershell
cd "C:\Users\emmad\Downloads\CodeP\SelfDriveBeamNGTech"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\ac_driver\requirements.txt
python .\ac_driver\main.py --mode classical --debug
```

If PowerShell blocks activation, run once and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Full first-time guide (including "I don't have Assetto Corsa installed yet"):
[ac_driver/README.md](ac_driver/README.md)

## BeamNG.tech (legacy)

BeamNG docs are still available in:
[autonomy_project/README.md](autonomy_project/README.md)
