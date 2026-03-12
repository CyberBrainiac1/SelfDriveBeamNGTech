# SelfDriveBeamNGTech — Auto Drive Quickstart

Connects **BeamNG.tech** to a physical steering wheel over USB serial.
The AI reads live vehicle steering data from BeamNG and drives the wheel motor in real time.

---

## 1 — Install dependencies

```bash
cd _archive
pip install -r requirements.txt
```

> Requires **Python 3.11+** and a running copy of **BeamNG.tech**.

---

## 2 — Run the app

### Normal launch (full GUI)

```bash
cd _archive/desktop_app
python main.py
```

### Launch straight into BeamNG AI Mode

```bash
cd _archive/desktop_app
python main.py --beamng-mode
```

The `--beamng-mode` flag skips the wheel-settings screen and opens the
**BeamNG.tech AI Mode** page directly.

---

## 3 — Start auto drive (inside the app)

1. **Connect** — click *Connect BeamNG* and enter your BeamNG host/port
   (default `localhost:64256`).
2. **Source** — leave the source dropdown on `BEAMNG` to mirror live
   in-game steering, or pick another source:
   | Source | What it does |
   |--------|-------------|
   | `BEAMNG` | Mirrors live BeamNG steering angle to the wheel |
   | `MANUAL_TEST` | Use the manual angle slider (no BeamNG needed) |
   | `PATH_FOLLOW` | Simple PD path-follower |
   | `LANE_CENTER` | Lane-centering stub (requires vision data) |
   | `REPLAY` | Play back a recorded steering CSV |
3. **Start** — click *▶ Start AI*. The wheel will begin turning.
4. **Stop** — click *■ Stop AI* or *⚠ EMERGENCY DISENGAGE* at any time.

---

## 4 — Archived code

Everything else (firmware, hex build scripts, wheel-settings UI, tests) is
kept under `_archive/` and is **not initialised** by default.

```
_archive/
  desktop_app/   ← full PySide6 GUI source
  firmware/      ← Arduino .ino source
  scripts/       ← PowerShell build/flash/run helpers
  tests/         ← Python unit tests
  output/        ← compiled hex drop zone
  docs/          ← architecture notes
  requirements.txt
```
