"""
tests/test_telemetry.py — Unit tests for TelemetryBuffer and TelemetryFrame.
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop_app"))

from core.telemetry import TelemetryBuffer, TelemetryFrame


def make_frame(angle=0.0, target=0.0, motor=0, mode="IDLE", enc=0, fault=0):
    return TelemetryFrame.from_dict({
        "angle": angle,
        "target": target,
        "motor": motor,
        "mode": mode,
        "enc": enc,
        "fault": fault,
        "ts": 12345,
    })


def test_frame_from_dict():
    f = make_frame(angle=90.5, mode="ANGLE_TRACK", motor=150, enc=1200)
    assert f.angle == pytest.approx(90.5)
    assert f.mode == "ANGLE_TRACK"
    assert f.motor == 150
    assert f.enc == 1200


def test_no_fault():
    f = make_frame(fault=0)
    assert not f.has_fault()
    assert f.fault_names() == []


def test_fault_flags():
    f = make_frame(fault=0x03)  # SERIAL_TIMEOUT + ANGLE_CLAMP
    assert f.has_fault()
    names = f.fault_names()
    assert "SERIAL_TIMEOUT" in names
    assert "ANGLE_CLAMP" in names


def test_buffer_push_and_latest():
    buf = TelemetryBuffer()
    assert buf.latest is None
    f = make_frame(angle=45.0)
    buf.push(f)
    assert buf.latest is f
    assert buf.latest.angle == pytest.approx(45.0)


def test_buffer_history():
    buf = TelemetryBuffer()
    for i in range(5):
        buf.push(make_frame(angle=float(i)))
    history = buf.get_history()
    assert len(history) == 5
    assert history[-1].angle == pytest.approx(4.0)


def test_buffer_max_size():
    buf = TelemetryBuffer(max_history=3)
    for i in range(10):
        buf.push(make_frame(angle=float(i)))
    assert len(buf.get_history()) == 3


def test_buffer_angle_history():
    buf = TelemetryBuffer()
    for i in range(3):
        buf.push(make_frame(angle=float(i * 10)))
    ts, angles = buf.get_angle_history()
    assert len(ts) == 3
    assert angles == pytest.approx([0.0, 10.0, 20.0])
    assert ts[0] == pytest.approx(0.0)


def test_buffer_stale():
    buf = TelemetryBuffer()
    assert buf.is_stale(threshold=1.0)  # no data → stale
    buf.push(make_frame())
    assert not buf.is_stale(threshold=5.0)  # just pushed → not stale


def test_buffer_clear():
    buf = TelemetryBuffer()
    buf.push(make_frame())
    buf.clear()
    assert buf.latest is None
    assert buf.get_history() == []
    assert buf.is_stale(threshold=0.0)


def test_buffer_push_dict():
    buf = TelemetryBuffer()
    buf.push_dict({"angle": 30.0, "target": 0.0, "motor": 100,
                   "mode": "ANGLE_TRACK", "enc": 400, "fault": 0, "ts": 0})
    assert buf.latest.angle == pytest.approx(30.0)
