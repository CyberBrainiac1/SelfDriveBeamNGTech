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
UP         = 0xC8   # throttle (arrow-up)
LEFT       = 0xCB   # steer left (arrow-left)
DOWN       = 0xD0   # brake (arrow-down)
RIGHT      = 0xCD   # steer right (arrow-right)
SHIFT_L    = 0x2A   # gear up (if AC is mapped this way)
CTRL_L     = 0x1D   # gear down
SPACE      = 0x39   # handbrake

_ALL_KEYS = (W, A, S, D, UP, LEFT, DOWN, RIGHT, SHIFT_L, CTRL_L, SPACE)

# ── Windows ctypes structures ─────────────────────────────────────
SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
EnumWindows = ctypes.windll.user32.EnumWindows
GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
GetWindowTextW = ctypes.windll.user32.GetWindowTextW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
ShowWindow = ctypes.windll.user32.ShowWindow
SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow

SW_RESTORE = 9


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


def _key_id(scan: int, extended: bool) -> int:
    return scan | (0x10000 if extended else 0)


def _send(scan: int, release: bool, extended: bool = False) -> None:
    extra = ctypes.c_ulong(0)
    ii = _Input_I()
    flags = 0x0008 | (0x0002 if release else 0) | (0x0001 if extended else 0)
    ii.ki = _KbdInput(0, scan, flags, 0, ctypes.pointer(extra))
    x = _Input(ctypes.c_ulong(1), ii)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


def press(scan: int, extended: bool = False) -> None:
    key = _key_id(scan, extended)
    if key not in _pressed:
        _send(scan, release=False, extended=extended)
        _pressed.add(key)


def release(scan: int, extended: bool = False) -> None:
    key = _key_id(scan, extended)
    if key in _pressed:
        _send(scan, release=True, extended=extended)
        _pressed.discard(key)


def release_all() -> None:
    """Release every held key — call on emergency stop or exit."""
    for k in list(_pressed):
        release(k)


def tap(scan: int, duration: float = 0.05) -> None:
    """Press and release a key after `duration` seconds."""
    press(scan)
    time.sleep(duration)
    release(scan)


def press_arrow(scan: int) -> None:
    """Press an arrow key (extended scan code)."""
    press(scan, extended=True)


def release_arrow(scan: int) -> None:
    """Release an arrow key (extended scan code)."""
    release(scan, extended=True)


def focus_assetto_window() -> bool:
    """Try to bring the Assetto Corsa window to foreground for key input."""
    matches = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_cb(hwnd, _lparam):
        try:
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if "assetto corsa" in title.lower():
                matches.append(hwnd)
        except Exception:
            return True
        return True

    try:
        EnumWindows(_enum_cb, 0)
        if not matches:
            return False
        hwnd = matches[0]
        ShowWindow(hwnd, SW_RESTORE)
        return bool(SetForegroundWindow(hwnd))
    except Exception:
        return False
