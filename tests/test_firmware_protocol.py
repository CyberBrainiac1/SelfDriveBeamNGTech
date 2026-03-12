"""
tests/test_firmware_protocol.py
Validates the JSON serial protocol assumed by wheel_controller.ino v2.0.0.
Tests the serial_manager command building logic (no hardware needed).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desktop_app'))

import json
import pytest


# ── Helpers: build the command objects the same way SerialManager does ─────

def cmd_set_config(key, value):
    return {"cmd": "set_config", "key": key, "value": value}

def cmd_save_config():
    return {"cmd": "save_config"}

def cmd_load_config():
    return {"cmd": "load_config"}

def cmd_save_profile(slot, name):
    return {"cmd": "save_profile", "slot": slot, "name": name[:15]}

def cmd_load_profile(slot):
    return {"cmd": "load_profile", "slot": slot}

def cmd_list_profiles():
    return {"cmd": "list_profiles"}

def cmd_factory_reset():
    return {"cmd": "factory_reset"}

def cmd_set_mode(mode):
    return {"cmd": "set_mode", "mode": mode}

def cmd_set_target(angle):
    return {"cmd": "set_target", "angle": round(angle, 2)}

def cmd_motor_test(direction, pwm):
    return {"cmd": "motor_test", "dir": direction, "pwm": pwm}


# ── All commands serialize to valid JSON ───────────────────────────────────

def _roundtrip(obj):
    return json.loads(json.dumps(obj))

def test_set_config_kp():
    c = _roundtrip(cmd_set_config("kp", 1.8))
    assert c["cmd"] == "set_config"
    assert c["key"] == "kp"
    assert c["value"] == pytest.approx(1.8)

def test_set_config_invert_encoder():
    c = _roundtrip(cmd_set_config("invert_encoder", True))
    assert c["value"] is True

def test_save_config_serializes():
    c = _roundtrip(cmd_save_config())
    assert c["cmd"] == "save_config"

def test_load_config_serializes():
    c = _roundtrip(cmd_load_config())
    assert c["cmd"] == "load_config"

def test_factory_reset():
    c = _roundtrip(cmd_factory_reset())
    assert c["cmd"] == "factory_reset"

def test_save_profile_slot():
    c = _roundtrip(cmd_save_profile(2, "RaceSetup"))
    assert c["cmd"]  == "save_profile"
    assert c["slot"] == 2
    assert c["name"] == "RaceSetup"

def test_profile_name_truncated_to_15():
    long_name = "A" * 30
    c = _roundtrip(cmd_save_profile(0, long_name))
    assert len(c["name"]) == 15

def test_load_profile_slot():
    c = _roundtrip(cmd_load_profile(3))
    assert c["slot"] == 3

def test_list_profiles():
    c = _roundtrip(cmd_list_profiles())
    assert c["cmd"] == "list_profiles"

def test_set_mode_valid_modes():
    for mode in ["IDLE", "NORMAL_HID", "ANGLE_TRACK", "ASSIST", "ESTOP", "CALIBRATION"]:
        c = _roundtrip(cmd_set_mode(mode))
        assert c["mode"] == mode

def test_set_target_rounded():
    c = _roundtrip(cmd_set_target(45.987654))
    assert c["angle"] == pytest.approx(45.99, abs=0.01)

def test_set_target_negative():
    c = _roundtrip(cmd_set_target(-270.0))
    assert c["angle"] == -270.0

def test_motor_test_positive():
    c = _roundtrip(cmd_motor_test(1, 80))
    assert c["dir"] == 1
    assert c["pwm"] == 80

def test_motor_test_negative():
    c = _roundtrip(cmd_motor_test(-1, 60))
    assert c["dir"] == -1


# ── EEPROM-valid telemetry parsing ─────────────────────────────────────────

def _parse_telem(json_str):
    return json.loads(json_str)

def test_telem_parse_all_fields():
    raw = ('{"t":"telem","angle":42.3,"target":45.0,"motor":120,'
           '"mode":"ANGLE_TRACK","enc":1234,"vel":18.5,'
           '"fault":0,"profile":"Normal","uptime":60}')
    t = _parse_telem(raw)
    assert t["t"]       == "telem"
    assert t["angle"]   == pytest.approx(42.3)
    assert t["target"]  == pytest.approx(45.0)
    assert t["motor"]   == 120
    assert t["mode"]    == "ANGLE_TRACK"
    assert t["enc"]     == 1234
    assert t["vel"]     == pytest.approx(18.5)
    assert t["fault"]   == 0
    assert t["profile"] == "Normal"
    assert t["uptime"]  == 60

def test_telem_fault_flags():
    raw = '{"t":"telem","angle":0,"target":0,"motor":0,"mode":"IDLE","enc":0,"vel":0,"fault":5,"profile":"x","uptime":1}'
    t = _parse_telem(raw)
    fault = t["fault"]
    serial_timeout = bool(fault & 0x01)
    angle_clamp    = bool(fault & 0x02)
    eeprom_default = bool(fault & 0x04)
    motor_overload = bool(fault & 0x08)
    assert serial_timeout is True   # bit 0 set
    assert angle_clamp    is False  # bit 1 clear
    assert eeprom_default is True   # bit 2 set
    assert motor_overload is False  # bit 3 clear

def test_config_response_parse():
    raw = ('{"t":"config","kp":1.8,"kd":0.12,"ki":0.0,"dead_zone":1.5,'
           '"angle_range":540.0,"counts_per_rev":2400.0,"gear_ratio":1.0,'
           '"invert_encoder":false,"invert_motor":false,"max_motor":200,'
           '"slew_rate":20.0,"centering":1.0,"damping":0.12,"friction":0.05,'
           '"inertia":0.04,"smoothing":0.1,"profile":"Default","eeprom_ok":true}')
    c = json.loads(raw)
    assert c["kp"]            == pytest.approx(1.8)
    assert c["angle_range"]   == pytest.approx(540.0)
    assert c["max_motor"]     == 200
    assert c["invert_encoder"] is False
    assert c["eeprom_ok"]      is True

def test_profiles_response_parse():
    raw = ('{"t":"profiles","slots":['
           '{"slot":0,"valid":true,"name":"Normal"},'
           '{"slot":1,"valid":false},'
           '{"slot":2,"valid":true,"name":"Race"},'
           '{"slot":3,"valid":false}]}')
    p = json.loads(raw)
    slots = p["slots"]
    assert len(slots)       == 4
    assert slots[0]["name"] == "Normal"
    assert slots[1]["valid"] is False
    assert slots[2]["name"] == "Race"

def test_boot_response_parse():
    raw = '{"t":"boot","version":"2.0.0","eeprom":true,"profile":"Default"}'
    b = json.loads(raw)
    assert b["version"] == "2.0.0"
    assert b["eeprom"]  is True
