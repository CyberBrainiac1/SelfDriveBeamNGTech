"""
tests/test_config_manager.py — Unit tests for ConfigManager.
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "desktop_app"))

from core.config_manager import ConfigManager


@pytest.fixture
def temp_config():
    """Create a ConfigManager with a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        path = f.name
    # Remove so ConfigManager creates a fresh one
    os.unlink(path)
    cfg = ConfigManager(config_path=path)
    yield cfg
    if os.path.exists(path):
        os.unlink(path)


def test_default_values(temp_config):
    """Defaults should be present after init."""
    assert temp_config.get("serial.baud") == 115200
    assert temp_config.get("wheel.angle_range") == 540.0
    assert temp_config.get("beamng.host") == "localhost"


def test_set_and_get(temp_config):
    """Values should persist after set."""
    temp_config.set("wheel.angle_range", 270.0)
    assert temp_config.get("wheel.angle_range") == 270.0


def test_set_new_key(temp_config):
    """Setting a new key should work."""
    temp_config.set("wheel.custom_key", "test_value")
    assert temp_config.get("wheel.custom_key") == "test_value"


def test_default_for_missing_key(temp_config):
    """Missing key should return provided default."""
    result = temp_config.get("nonexistent.key", default="fallback")
    assert result == "fallback"


def test_section_get_set(temp_config):
    """get_section / set_section should work."""
    section = temp_config.get_section("wheel")
    assert "angle_range" in section
    section["angle_range"] = 360.0
    temp_config.set_section("wheel", section)
    assert temp_config.get("wheel.angle_range") == 360.0


def test_save_and_reload(temp_config):
    """Saved config should reload correctly."""
    path = temp_config._path
    temp_config.set("wheel.angle_range", 900.0)
    temp_config.save()

    cfg2 = ConfigManager(config_path=path)
    assert cfg2.get("wheel.angle_range") == 900.0


def test_deep_merge_preserves_defaults(temp_config):
    """Partial override should not lose other defaults."""
    temp_config.set("serial.port", "COM5")
    # baud should still be default
    assert temp_config.get("serial.baud") == 115200
    assert temp_config.get("serial.port") == "COM5"
