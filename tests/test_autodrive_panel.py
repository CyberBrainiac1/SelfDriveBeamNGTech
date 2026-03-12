"""
tests/test_autodrive_panel.py — Unit tests for the Auto Drive panel logic
added to NormalWheelPage.

Tests the handler methods using lightweight mocks so they run without PySide6.
"""
import os
import sys
import types
import pytest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub PySide6 with proper class objects so Qt base-class inheritance works.
# ---------------------------------------------------------------------------

class _AnyWidget:
    def __init__(self, *args, **kwargs): pass
    def __getattr__(self, name): return lambda *a, **kw: None

class _Signal:
    def __init__(self, *types_): pass
    def connect(self, slot): pass
    def emit(self, *args): pass

def _signal_factory(*args, **kwargs):
    return _Signal()

class _QObject:
    def __init__(self, *args, **kwargs): pass
    def __getattr__(self, name): return lambda *a, **kw: None

def _make_qt_module(name, **extra):
    mod = types.ModuleType(name)
    mod.__dict__.update(extra)
    return mod

_qt_mock = MagicMock()

_pyside6_core = _make_qt_module(
    "PySide6.QtCore",
    QObject=_QObject, Signal=_signal_factory,
    Qt=_qt_mock, QTimer=_AnyWidget, QSize=_AnyWidget,
    QRect=_AnyWidget, QPoint=_AnyWidget,
    QPropertyAnimation=_AnyWidget, QEasingCurve=_AnyWidget,
)
_pyside6_widgets = _make_qt_module(
    "PySide6.QtWidgets",
    **{n: _AnyWidget for n in [
        "QWidget", "QMainWindow", "QHBoxLayout", "QVBoxLayout", "QLabel",
        "QPushButton", "QComboBox", "QDoubleSpinBox", "QSpinBox", "QScrollArea",
        "QGroupBox", "QFormLayout", "QTabWidget", "QTextEdit", "QPlainTextEdit",
        "QProgressBar", "QLineEdit", "QCheckBox", "QSplitter", "QFrame",
        "QListWidget", "QListWidgetItem", "QInputDialog", "QMessageBox",
        "QFileDialog", "QStatusBar", "QStackedWidget", "QApplication",
        "QSizePolicy",
    ]}
)
_pyside6_gui = _make_qt_module(
    "PySide6.QtGui",
    QFont=_AnyWidget, QColor=_AnyWidget, QPainter=_AnyWidget,
    QPen=_AnyWidget, QPainterPath=_AnyWidget,
    QTextCharFormat=_AnyWidget, QTextCursor=_AnyWidget, QFileDialog=_AnyWidget,
)

_pyside6 = types.ModuleType("PySide6")

for _key, _mod in [
    ("PySide6",           _pyside6),
    ("PySide6.QtCore",    _pyside6_core),
    ("PySide6.QtWidgets", _pyside6_widgets),
    ("PySide6.QtGui",     _pyside6_gui),
]:
    sys.modules.setdefault(_key, _mod)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop_app"))

from pages.normal_wheel_page import NormalWheelPage  # noqa: E402
from beamng.ai_controller import TargetSource         # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_beamng_manager(is_connected=False):
    mgr = MagicMock()
    mgr.is_connected = is_connected
    return mgr

def _make_safety():
    s = MagicMock()
    s.clamp_target = lambda x: max(-540.0, min(540.0, x))
    s.enter_ai_mode.return_value = True
    return s

def _make_config():
    c = MagicMock()
    c.get = lambda key, default=None: {
        "beamng.host": "localhost",
        "beamng.port": 64256,
        "beamng.steer_scale": 1.0,
        "wheel.angle_range": 540.0,
        "beamng.safety_max_angle": 450.0,
    }.get(key, default)
    return c


class _FakePanel:
    """
    Minimal host that borrows the real handler methods from NormalWheelPage
    but replaces all widget attributes with MagicMocks.
    """
    def __init__(self, beamng_manager=None):
        self._beamng_manager = beamng_manager
        self._config  = _make_config()
        self._safety  = _make_safety()
        self._serial  = MagicMock()
        self._log     = MagicMock()
        self._bridge  = MagicMock()
        self._ai      = MagicMock()
        self._ad_badge_bng  = MagicMock()
        self._ad_btn_bng    = MagicMock()
        self._ad_status_lbl = MagicMock()
        self._ad_t_target   = MagicMock()
        self._ad_t_mode     = MagicMock()
        self._ad_src_combo  = MagicMock()

    # Borrow real handler methods (unbound)
    _ad_toggle_bng          = NormalWheelPage._ad_toggle_bng
    _ad_on_bng_connected    = NormalWheelPage._ad_on_bng_connected
    _ad_on_bng_disconnected = NormalWheelPage._ad_on_bng_disconnected
    _ad_on_vehicle_state    = NormalWheelPage._ad_on_vehicle_state
    _ad_start               = NormalWheelPage._ad_start
    _ad_stop                = NormalWheelPage._ad_stop
    _ad_estop               = NormalWheelPage._ad_estop
    _ad_on_target           = NormalWheelPage._ad_on_target
    _ad_on_mode             = NormalWheelPage._ad_on_mode

    def _do_estop(self):
        if self._safety:
            self._safety.trigger_estop("Manual E-STOP from UI")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAdToggleBng:
    def test_connect_when_not_connected(self):
        mgr = _make_beamng_manager(is_connected=False)
        panel = _FakePanel(beamng_manager=mgr)
        panel._ad_toggle_bng()
        mgr.connect.assert_called_once_with("localhost", 64256)

    def test_disconnect_when_connected(self):
        mgr = _make_beamng_manager(is_connected=True)
        panel = _FakePanel(beamng_manager=mgr)
        panel._ad_toggle_bng()
        mgr.disconnect.assert_called_once()

    def test_noop_without_manager(self):
        panel = _FakePanel(beamng_manager=None)
        panel._ad_toggle_bng()  # must not raise


class TestAdConnectionBadge:
    def test_badge_ok_on_connected(self):
        panel = _FakePanel()
        panel._ad_on_bng_connected()
        panel._ad_badge_bng.set_ok.assert_called_once_with("Connected")
        panel._ad_btn_bng.setText.assert_called_with("Disconnect BeamNG")

    def test_badge_inactive_on_disconnected(self):
        panel = _FakePanel()
        panel._ad_on_bng_disconnected()
        panel._ad_badge_bng.set_inactive.assert_called_once_with("Not Connected")
        panel._ad_btn_bng.setText.assert_called_with("Connect BeamNG")

    def test_ai_stopped_when_bng_drops_while_active(self):
        panel = _FakePanel()
        panel._ai.is_active = True
        panel._ad_on_bng_disconnected()
        panel._ai.stop.assert_called_once()

    def test_ai_not_stopped_when_already_idle(self):
        panel = _FakePanel()
        panel._ai.is_active = False
        panel._ad_on_bng_disconnected()
        panel._ai.stop.assert_not_called()


class TestAdVehicleState:
    def test_forwards_state_when_active(self):
        panel = _FakePanel()
        panel._ai.is_active = True
        state = {"steering_input": 0.5}
        panel._ad_on_vehicle_state(state)
        panel._bridge.process_vehicle_state.assert_called_once_with(state)

    def test_does_not_forward_when_idle(self):
        panel = _FakePanel()
        panel._ai.is_active = False
        panel._ad_on_vehicle_state({"steering_input": 0.5})
        panel._bridge.process_vehicle_state.assert_not_called()


class TestAdStartStop:
    def test_start_manual_source(self):
        panel = _FakePanel()
        panel._ad_src_combo.currentText.return_value = TargetSource.MANUAL_TEST.value
        panel._ad_start()
        panel._ai.set_source.assert_called_once_with(TargetSource.MANUAL_TEST)
        panel._ai.start.assert_called_once()
        args, _ = panel._ad_status_lbl.setText.call_args
        assert TargetSource.MANUAL_TEST.value in args[0]

    def test_start_beamng_source(self):
        panel = _FakePanel()
        panel._ad_src_combo.currentText.return_value = TargetSource.BEAMNG.value
        panel._ad_start()
        panel._ai.set_source.assert_called_once_with(TargetSource.BEAMNG)
        panel._ai.start.assert_called_once()

    def test_stop_halts_ai_and_clears_readout(self):
        panel = _FakePanel()
        panel._ad_stop()
        panel._ai.stop.assert_called_once()
        panel._ad_t_target.setText.assert_called_with("—")
        panel._ad_t_mode.setText.assert_called_with("—")

    def test_estop_halts_ai_and_triggers_safety(self):
        panel = _FakePanel()
        panel._ad_estop()
        panel._ai.stop.assert_called_once()
        panel._safety.trigger_estop.assert_called()

    def test_estop_label_shows_disengaged(self):
        panel = _FakePanel()
        panel._ad_estop()
        args, _ = panel._ad_status_lbl.setText.call_args
        assert "DISENGAGED" in args[0]


class TestAdLiveReadout:
    def test_on_target_positive(self):
        panel = _FakePanel()
        panel._ad_on_target(42.5)
        panel._ad_t_target.setText.assert_called_with("42.5°")

    def test_on_target_negative(self):
        panel = _FakePanel()
        panel._ad_on_target(-135.0)
        panel._ad_t_target.setText.assert_called_with("-135.0°")

    def test_on_target_zero(self):
        panel = _FakePanel()
        panel._ad_on_target(0.0)
        panel._ad_t_target.setText.assert_called_with("0.0°")

    def test_on_mode_running(self):
        panel = _FakePanel()
        panel._ad_on_mode("BEAMNG")
        panel._ad_t_mode.setText.assert_called_with("BEAMNG")

    def test_on_mode_stopped(self):
        panel = _FakePanel()
        panel._ad_on_mode("STOPPED")
        panel._ad_t_mode.setText.assert_called_with("STOPPED")
