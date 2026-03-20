"""
beamng_detector.py — Locate and validate the BeamNG.tech installation.
"""

import os
from pathlib import Path

DEFAULT_BEAMNG_HOME = r"C:\Beamngtech\BeamNG.tech.v0.38.3.0"
BEAMNG_EXE_NAME = "BeamNG.tech.exe"


class BeamNGDetector:
    """
    Validates that a BeamNG.tech installation exists at the given (or default) path.
    """

    def __init__(self):
        pass

    def detect(self, home_path: str = None) -> str:
        """
        Locate BeamNG.tech installation.

        Checks in order:
        1. *home_path* if provided.
        2. BEAMNG_HOME environment variable.
        3. Default path: C:\\Beamngtech\\BeamNG.tech.v0.38.3.0

        Returns the validated installation directory as a string.
        Raises RuntimeError with a descriptive message if not found.
        """
        candidates = []

        if home_path:
            candidates.append(Path(home_path))

        env_path = os.environ.get("BEAMNG_HOME")
        if env_path:
            candidates.append(Path(env_path))

        candidates.append(Path(DEFAULT_BEAMNG_HOME))

        errors = []
        for candidate in candidates:
            result = self._validate(candidate)
            if result is not None:
                return result
            errors.append(str(candidate))

        raise RuntimeError(
            f"BeamNG.tech installation not found.\n"
            f"Searched paths:\n"
            + "\n".join(f"  - {p}" for p in errors)
            + f"\n\nPlease install BeamNG.tech or set --beamng-home / BEAMNG_HOME env var."
        )

    def _validate(self, path: Path) -> str | None:
        """
        Return the path string if valid, else None.

        A valid installation directory must:
        - exist as a directory
        - contain BeamNG.tech.exe
        """
        if not path.is_dir():
            return None
        exe = path / BEAMNG_EXE_NAME
        if not exe.is_file():
            return None
        return str(path)
