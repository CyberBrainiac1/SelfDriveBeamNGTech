"""
desktop_app/core/config_manager.py — Persistent settings storage using TOML.
All settings are saved to output/profiles/app_config.toml.
"""
import os
import toml
from typing import Any, Dict

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "output", "profiles", "app_config.toml"
)

# Default configuration values
DEFAULTS: Dict[str, Any] = {
    "serial": {
        "port": "",
        "baud": 115200,
        "timeout": 2.0,
    },
    "wheel": {
        "angle_range": 540.0,
        "center_offset": 0.0,
        "max_motor_output": 200,
        "centering_strength": 1.0,
        "damping": 0.12,
        "friction": 0.05,
        "inertia": 0.05,
        "smoothing": 0.1,
        "invert_motor": False,
        "invert_encoder": False,
        "counts_per_rev": 2400,
        "gear_ratio": 1.0,
    },
    "beamng": {
        "host": "localhost",
        "port": 64256,
        "auto_connect": False,
        "steer_scale": 1.0,
        "angle_map_min": -540.0,
        "angle_map_max": 540.0,
        "safety_max_angle": 450.0,
        "safety_max_rate": 180.0,
    },
    "ui": {
        "theme": "dark",
        "update_rate_hz": 10,
        "chart_history_s": 10,
    },
    "logging": {
        "log_dir": "output/logs",
        "level": "INFO",
    },
}


class ConfigManager:
    """
    Loads/saves application configuration as TOML.
    Supports dot-notation key access: config.get("wheel.angle_range")
    """

    def __init__(self, config_path: str = CONFIG_PATH):
        self._path = config_path
        self._data: Dict[str, Any] = {}
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                self._data = toml.load(self._path)
            except Exception:
                self._data = {}
        # Merge defaults for missing keys
        self._data = self._deep_merge(DEFAULTS, self._data)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def save(self):
        with open(self._path, "w") as f:
            toml.dump(self._data, f)

    def get(self, key: str, default=None) -> Any:
        """Get value using dot notation: 'wheel.angle_range'"""
        parts = key.split(".")
        node = self._data
        for p in parts:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return default
        return node

    def set(self, key: str, value: Any):
        """Set value using dot notation and save."""
        parts = key.split(".")
        node = self._data
        for p in parts[:-1]:
            if p not in node or not isinstance(node[p], dict):
                node[p] = {}
            node = node[p]
        node[parts[-1]] = value
        self.save()

    def get_section(self, section: str) -> Dict[str, Any]:
        return dict(self._data.get(section, {}))

    def set_section(self, section: str, values: Dict[str, Any]):
        self._data[section] = values
        self.save()

    @property
    def all(self) -> Dict[str, Any]:
        return self._data
