"""
Shared training-data path helpers.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATA_ROOT = REPO_ROOT / "training_data"
AC_TRAINING_DATA_DIR = TRAINING_DATA_ROOT / "assetto_corsa"
BEAMNG_TEACHER_DATA_DIR = TRAINING_DATA_ROOT / "beamng_teacher"


def ensure_training_roots() -> None:
    AC_TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    BEAMNG_TEACHER_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "capture"


def resolve_beamng_teacher_dir(
    requested: Optional[str],
    map_name: str,
    vehicle: str,
    stage: str,
    speed_kph: float,
) -> Optional[Path]:
    if not requested:
        return None

    ensure_training_roots()

    if requested == "auto":
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = "_".join(
            [
                stamp,
                _slug(map_name),
                _slug(vehicle),
                _slug(stage),
                f"{int(round(speed_kph))}kph",
            ]
        )
        return BEAMNG_TEACHER_DATA_DIR / run_name

    path = Path(requested)
    if not path.is_absolute() and len(path.parts) == 1:
        return BEAMNG_TEACHER_DATA_DIR / path
    return path
