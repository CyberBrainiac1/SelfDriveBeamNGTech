# SelfDriveBeamNGTech

Custom autonomous driving system built on BeamNG.tech.

A modular, DIY self-driving stack using BeamNG.tech sensor data with its own
perception, planning, and control pipeline. Not a wrapper around BeamNG's
built-in AI.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r autonomy_project/requirements.txt
# Edit autonomy_project/config.py to set your BeamNG.tech install path
cd autonomy_project
python main.py
```

See [`autonomy_project/README.md`](autonomy_project/README.md) for full documentation.
