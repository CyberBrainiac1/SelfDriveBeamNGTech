"""
config.py - Configuration loader with dot-access support.

Loads YAML config files and exposes settings as nested attributes.
Supports a base config and named override merging.
"""

import os
import yaml
from pathlib import Path


class Config:
    """
    Dot-access configuration object.  Nested dicts become nested Config instances.
    """

    def __init__(self, data: dict = None):
        self._data = data or {}
        for key, value in self._data.items():
            if isinstance(value, dict):
                setattr(self, key, Config(value))
            elif isinstance(value, list):
                setattr(self, key, value)
            else:
                setattr(self, key, value)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "Config":
        """
        Load a YAML config from *path*.

        If *path* points to a named config (e.g. hirochi_endurance.yaml) the
        loader also tries to find a ``default.yaml`` in the same directory and
        deep-merges it underneath the named config (named wins).
        """
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            named_data = yaml.safe_load(fh) or {}

        # Optionally merge with default.yaml in the same directory
        default_path = path.parent / "default.yaml"
        if default_path.exists() and default_path != path:
            with open(default_path, "r", encoding="utf-8") as fh:
                default_data = yaml.safe_load(fh) or {}
            merged = cls._deep_merge(default_data, named_data)
        else:
            merged = named_data

        return cls(merged)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base*; override wins on conflict."""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default=None):
        """Dict-style get with a default."""
        return getattr(self, key, default)

    def as_dict(self) -> dict:
        """Recursively convert back to a plain dict."""
        result = {}
        for key, value in self._data.items():
            if isinstance(value, Config):
                result[key] = value.as_dict()
            else:
                result[key] = value
        return result

    def __repr__(self) -> str:
        return f"Config({list(self._data.keys())})"

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getattr__(self, name: str):
        # Prevent infinite recursion for private attrs
        if name.startswith("_"):
            raise AttributeError(name)
        raise AttributeError(f"Config has no attribute '{name}'")
