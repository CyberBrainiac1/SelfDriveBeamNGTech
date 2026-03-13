# -*- coding: utf-8 -*-
"""
ACDriverApp.py
==============
Assetto Corsa Python app — runs INSIDE the game's sandboxed Python 3.3
environment.  Reads telemetry every frame and writes it to a JSON file
that the external ACDriver reads.

INSTALLATION
------------
Copy the entire  ac_app/ACDriverApp/  folder to:
    %USERPROFILE%\Documents\Assetto Corsa\apps\python\

Then in AC:  Options → General → UI Modules → enable ACDriverApp.
A small status widget will appear in-game.  Drag it wherever you like.

DATA FORMAT (JSON written each frame)
--------------------------------------
{
  "speed_kph":     65.3,
  "steer_deg":    -23.1,      # raw steering wheel degrees (± steer lock)
  "steer_norm":   -0.051,     # steer_deg / 450  →  -1 … +1
  "gear":          3,
  "rpm":           4200.0,
  "gas":           0.8,
  "brake":         0.0,
  "clutch":        0.0,
  "lap":           1,
  "lap_progress":  0.45       # 0–1 around the lap
}

NOTES
-----
• acsys.CS constants confirmed against AC SDK docs (v1.5+).
• steer_lock_deg = 450 is safe for most road cars; race cars may differ.
• File I/O is the only cross-process comms available inside the AC sandbox.
"""

import ac
import acsys
import os
import json

# ── State file path ────────────────────────────────────────────────
_STATE_FILE = os.path.join(
    os.path.expanduser("~"),
    "Documents", "Assetto Corsa", "logs", "acdriver_state.json"
)
_STEER_LOCK_DEG = 450.0    # ← adjust per car if needed

# ── Module globals ────────────────────────────────────────────────
_app_id = None
_lbl_status = None
_lbl_speed = None
_lbl_steer = None


def acMain(ac_version):
    """Called once by AC when the app is loaded."""
    global _app_id, _lbl_status, _lbl_speed, _lbl_steer

    _app_id = ac.newApp("ACDriverApp")
    ac.setSize(_app_id, 240, 90)
    ac.setTitle(_app_id, "ACDriver")

    _lbl_status = ac.addLabel(_app_id, "Waiting...")
    ac.setPosition(_lbl_status, 5, 25)

    _lbl_speed = ac.addLabel(_app_id, "Speed: — kph")
    ac.setPosition(_lbl_speed, 5, 45)

    _lbl_steer = ac.addLabel(_app_id, "Steer: -- deg")
    ac.setPosition(_lbl_steer, 5, 65)

    # Make sure the logs folder exists
    try:
        log_dir = os.path.dirname(_STATE_FILE)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    except Exception:
        pass

    ac.log("ACDriverApp: started, writing to " + _STATE_FILE)
    return "ACDriverApp"


def acUpdate(delta_t):
    """Called every frame by AC.  Read vehicle state, write JSON."""
    try:
        spd  = float(ac.getCarState(0, acsys.CS.SpeedKMH))
        strd = float(ac.getCarState(0, acsys.CS.Steer))
        gear = int(ac.getCarState(0, acsys.CS.Gear))
        rpm  = float(ac.getCarState(0, acsys.CS.RPM))
        gas  = float(ac.getCarState(0, acsys.CS.Gas))
        brk  = float(ac.getCarState(0, acsys.CS.Brake))
        clt  = float(ac.getCarState(0, acsys.CS.Clutch))
        lap  = int(ac.getCarState(0, acsys.CS.LapCount))
        prog = float(ac.getCarState(0, acsys.CS.NormalizedSplinePosition))

        state = {
            "speed_kph":    spd,
            "steer_deg":    strd,
            "steer_norm":   max(-1.0, min(1.0, strd / _STEER_LOCK_DEG)),
            "gear":         gear,
            "rpm":          rpm,
            "gas":          gas,
            "brake":        brk,
            "clutch":       clt,
            "lap":          lap,
            "lap_progress": prog,
        }

        with open(_STATE_FILE, "w") as f:
            json.dump(state, f)

        # Update HUD labels (not every frame to save CPU)
        ac.setText(_lbl_status, "Logging OK")
        ac.setText(_lbl_speed,  "Speed: {:.0f} kph".format(spd))
        ac.setText(_lbl_steer,  "Steer: {:.1f} deg".format(strd))

    except Exception as e:
        try:
            ac.setText(_lbl_status, "ERR: " + str(e)[:30])
            ac.log("ACDriverApp error: " + str(e))
        except Exception:
            pass


def acShutdown():
    """Called when AC exits or the app is disabled."""
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump({"speed_kph": 0, "steer_norm": 0, "gas": 0, "brake": 0}, f)
    except Exception:
        pass
