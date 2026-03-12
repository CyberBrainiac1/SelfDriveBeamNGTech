"""
direct_keys.py
==============
DirectInput keyboard simulation for Assetto Corsa.
Adapted from ACDriver v2/directkeys.py — now includes:
  • Gear-shift keys (Shift + Ctrl)
  • Handbrake key
  • Proper press/release tracking to avoid stuck keys
  • Emergency release-all function

ORIGINAL SOURCE
---------------
Original ACDriver by denfed / awstone (MIT License).
Scan codes from https://www.gamespp.com/directx/directInputKeyboardScanCodes.html
"""

from __future__ import annotations
import ctypes
import time

# ── DirectInput scan codes ────────────────────────────────────────
W          = 0x11   # throttle
A          = 0x1E   # steer left
S          = 0x1F   # brake / reverse
D          = 0x20   # steer right
SHIFT_L    = 0x2A   # gear up (if AC is mapped this way)
CTRL_L     = 0x1D   # gear down
SPACE      = 0x39   # handbrake

_ALL_KEYS = (W, A, S, D, SHIFT_L, CTRL_L, SPACE)

# ── Windows ctypes structures ─────────────────────────────────────
SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)


class _KbdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class _HwInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]


class _Input_I(ctypes.Union):
    _fields_ = [("ki", _KbdInput), ("mi", _MouseInput), ("hi", _HwInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", _Input_I)]

# Track which keys are currently held so we can release them
_pressed: set = set()


def _send(scan: int, release: bool) -> None:
    extra = ctypes.c_ulong(0)
    ii = _Input_I()
    flags = 0x0008 | (0x0002 if release else 0)
    ii.ki = _KbdInput(0, scan, flags, 0, ctypes.pointer(extra))
    x = _Input(ctypes.c_ulong(1), ii)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


def press(scan: int) -> None:
    if scan not in _pressed:
        _send(scan, release=False)
        _pressed.add(scan)


def release(scan: int) -> None:
    if scan in _pressed:
        _send(scan, release=True)
        _pressed.discard(scan)


def release_all() -> None:
    """Release every held key — call on emergency stop or exit."""
    for k in list(_pressed):
        release(k)


def tap(scan: int, duration: float = 0.05) -> None:
    """Press and release a key after `duration` seconds."""
    press(scan)
    time.sleep(duration)
    release(scan)
