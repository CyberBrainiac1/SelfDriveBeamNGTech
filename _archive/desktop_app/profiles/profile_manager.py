"""
desktop_app/profiles/profile_manager.py — User profile management.
Profiles store named collections of settings for different use cases.
"""
import os
import json
import shutil
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, Signal

PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "output", "profiles"
)

DEFAULT_PROFILES = {
    "Normal Mode": {
        "description": "Standard wheel use",
        "wheel": {
            "angle_range": 540.0,
            "centering_strength": 1.0,
            "damping": 0.12,
            "friction": 0.05,
            "max_motor_output": 200,
        },
    },
    "AI Coach Mode": {
        "description": "BeamNG AI coach operation",
        "wheel": {
            "angle_range": 540.0,
            "centering_strength": 0.5,
            "damping": 0.08,
            "max_motor_output": 150,
        },
        "beamng": {
            "steer_scale": 1.0,
            "safety_max_angle": 400.0,
        },
    },
    "Test Mode": {
        "description": "Low-power testing and diagnostics",
        "wheel": {
            "angle_range": 180.0,
            "max_motor_output": 80,
            "centering_strength": 0.3,
        },
    },
    "Safe Low-Power": {
        "description": "Safe mode with minimal motor output",
        "wheel": {
            "angle_range": 360.0,
            "max_motor_output": 60,
            "centering_strength": 0.2,
            "damping": 0.05,
        },
    },
}


class ProfileManager(QObject):
    profile_loaded  = Signal(str)
    profile_saved   = Signal(str)
    profiles_changed = Signal()

    def __init__(self, config_manager, logger):
        super().__init__()
        self._config = config_manager
        self._log = logger
        self._current_name: Optional[str] = None
        os.makedirs(PROFILES_DIR, exist_ok=True)
        self._seed_defaults()

    def _profile_path(self, name: str) -> str:
        safe = name.replace(" ", "_").replace("/", "-")
        return os.path.join(PROFILES_DIR, f"profile_{safe}.json")

    def _seed_defaults(self):
        for name, data in DEFAULT_PROFILES.items():
            path = self._profile_path(name)
            if not os.path.exists(path):
                self._write(path, {"name": name, **data})

    def _write(self, path: str, data: dict):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _read(self, path: str) -> dict:
        with open(path, "r") as f:
            return json.load(f)

    def list_profiles(self) -> List[str]:
        names = []
        for f in os.listdir(PROFILES_DIR):
            if f.startswith("profile_") and f.endswith(".json"):
                try:
                    data = self._read(os.path.join(PROFILES_DIR, f))
                    names.append(data.get("name", f))
                except Exception:
                    pass
        return sorted(names)

    def load(self, name: str) -> bool:
        path = self._profile_path(name)
        if not os.path.exists(path):
            self._log.error(f"Profile not found: {name}")
            return False
        try:
            data = self._read(path)
            for section, values in data.items():
                if section in ("name", "description"):
                    continue
                if isinstance(values, dict):
                    self._config.set_section(section, {
                        **self._config.get_section(section),
                        **values,
                    })
            self._current_name = name
            self._log.info(f"Profile loaded: {name}")
            self.profile_loaded.emit(name)
            return True
        except Exception as e:
            self._log.error(f"Profile load error: {e}")
            return False

    def save(self, name: str, description: str = ""):
        data = {
            "name": name,
            "description": description,
            "wheel": self._config.get_section("wheel"),
            "beamng": self._config.get_section("beamng"),
        }
        self._write(self._profile_path(name), data)
        self._current_name = name
        self._log.info(f"Profile saved: {name}")
        self.profile_saved.emit(name)
        self.profiles_changed.emit()

    def duplicate(self, name: str, new_name: str) -> bool:
        src = self._profile_path(name)
        dst = self._profile_path(new_name)
        if not os.path.exists(src):
            return False
        shutil.copy2(src, dst)
        # Update name field
        data = self._read(dst)
        data["name"] = new_name
        self._write(dst, data)
        self.profiles_changed.emit()
        return True

    def delete(self, name: str) -> bool:
        path = self._profile_path(name)
        if os.path.exists(path):
            os.remove(path)
            self.profiles_changed.emit()
            return True
        return False

    def export_profile(self, name: str, dest_path: str) -> bool:
        src = self._profile_path(name)
        if not os.path.exists(src):
            return False
        shutil.copy2(src, dest_path)
        return True

    def import_profile(self, src_path: str) -> str:
        """Import a profile JSON. Returns profile name."""
        data = self._read(src_path)
        name = data.get("name", os.path.basename(src_path))
        dst = self._profile_path(name)
        shutil.copy2(src_path, dst)
        self.profiles_changed.emit()
        return name

    @property
    def current_name(self) -> Optional[str]:
        return self._current_name
