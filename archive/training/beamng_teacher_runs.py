"""
Teacher-run discovery and quality gates for BeamNG imitation training.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from training.paths import BEAMNG_TEACHER_DATA_DIR


DEFAULT_APPROVED_RACE_MAPS = (
    "hirochi_raceway",
    "automation_test_track",
    "east_coast_usa",
    "west_coast_usa",
    "derby",
)
DEFAULT_ALLOWED_STAGES = ("ai", "custom")
DEFAULT_MIN_FRAMES = 120
DEFAULT_MIN_TICKS = 120
DEFAULT_MAX_DAMAGE = 0.0
DEFAULT_MIN_MAX_SPEED_KPH = 40.0


@dataclass
class TeacherRunAssessment:
    teacher_dir: str
    labels_path: str
    summary_path: Optional[str]
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    frame_count: int = 0
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["summary"] = dict(self.summary)
        return payload


def discover_teacher_dirs(root: str | os.PathLike[str] = BEAMNG_TEACHER_DATA_DIR) -> list[str]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    teacher_dirs: list[str] = []
    for entry in sorted(root_path.iterdir()):
        if entry.is_dir() and (entry / "labels.csv").is_file():
            teacher_dirs.append(str(entry.resolve()))
    return teacher_dirs


def _count_labels(labels_path: str) -> int:
    count = 0
    with open(labels_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("image_path"):
                count += 1
    return count


def _load_summary(summary_path: str) -> dict:
    with open(summary_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Summary is not a JSON object: {summary_path}")
    return data


def find_run_summary_path(teacher_dir: str | os.PathLike[str]) -> Optional[str]:
    teacher_path = Path(teacher_dir)
    direct = teacher_path / "run_summary.json"
    if direct.is_file():
        return str(direct.resolve())
    legacy = teacher_path.with_suffix(".json")
    if legacy.is_file():
        return str(legacy.resolve())
    return None


def assess_teacher_run(
    teacher_dir: str | os.PathLike[str],
    approved_maps: Optional[Sequence[str]] = DEFAULT_APPROVED_RACE_MAPS,
    allowed_stages: Sequence[str] = DEFAULT_ALLOWED_STAGES,
    min_frames: int = DEFAULT_MIN_FRAMES,
    min_ticks: int = DEFAULT_MIN_TICKS,
    max_damage: float = DEFAULT_MAX_DAMAGE,
    min_max_speed_kph: float = DEFAULT_MIN_MAX_SPEED_KPH,
) -> TeacherRunAssessment:
    teacher_dir = str(Path(teacher_dir).resolve())
    labels_path = os.path.join(teacher_dir, "labels.csv")
    reasons: list[str] = []
    frame_count = 0
    summary_path = find_run_summary_path(teacher_dir)
    summary: dict = {}

    if not os.path.isfile(labels_path):
        reasons.append("missing labels.csv")
    else:
        try:
            frame_count = _count_labels(labels_path)
        except Exception as exc:
            reasons.append(f"failed to count labels: {exc}")
        if frame_count < min_frames:
            reasons.append(f"only {frame_count} frames (< {min_frames})")

    if summary_path is None:
        reasons.append("missing run_summary.json")
    else:
        try:
            summary = _load_summary(summary_path)
        except Exception as exc:
            reasons.append(f"failed to load summary: {exc}")
            summary = {}

    if summary:
        map_name = str(summary.get("map") or "").strip()
        stage = str(summary.get("stage") or "").strip()
        success = bool(summary.get("success"))
        damage_failure = bool(summary.get("damage_failure"))
        route_failure = bool(summary.get("route_failure"))
        ticks = int(summary.get("ticks") or 0)
        max_run_damage = float(summary.get("max_damage") or 0.0)
        max_speed_kph = float(summary.get("max_speed_kph") or 0.0)

        if approved_maps is not None and map_name not in approved_maps:
            reasons.append(f"map {map_name or '<unknown>'} not in approved race-map list")
        if stage not in allowed_stages:
            reasons.append(f"stage {stage or '<unknown>'} not allowed")
        if not success:
            reasons.append("run summary reports success=false")
        if damage_failure:
            reasons.append("run ended with damage failure")
        if route_failure:
            reasons.append("run ended with route failure")
        if ticks < min_ticks:
            reasons.append(f"only {ticks} ticks (< {min_ticks})")
        if max_run_damage > max_damage:
            reasons.append(f"max_damage {max_run_damage:.3f} > {max_damage:.3f}")
        if max_speed_kph < min_max_speed_kph:
            reasons.append(f"max_speed_kph {max_speed_kph:.1f} < {min_max_speed_kph:.1f}")

    return TeacherRunAssessment(
        teacher_dir=teacher_dir,
        labels_path=labels_path,
        summary_path=summary_path,
        accepted=not reasons,
        reasons=reasons,
        frame_count=frame_count,
        summary=summary,
    )


def curate_teacher_runs(
    teacher_dirs: Iterable[str | os.PathLike[str]],
    approved_maps: Optional[Sequence[str]] = DEFAULT_APPROVED_RACE_MAPS,
    allowed_stages: Sequence[str] = DEFAULT_ALLOWED_STAGES,
    min_frames: int = DEFAULT_MIN_FRAMES,
    min_ticks: int = DEFAULT_MIN_TICKS,
    max_damage: float = DEFAULT_MAX_DAMAGE,
    min_max_speed_kph: float = DEFAULT_MIN_MAX_SPEED_KPH,
) -> list[TeacherRunAssessment]:
    return [
        assess_teacher_run(
            teacher_dir=teacher_dir,
            approved_maps=approved_maps,
            allowed_stages=allowed_stages,
            min_frames=min_frames,
            min_ticks=min_ticks,
            max_damage=max_damage,
            min_max_speed_kph=min_max_speed_kph,
        )
        for teacher_dir in teacher_dirs
    ]


def write_curation_report(assessments: Sequence[TeacherRunAssessment], report_path: str | os.PathLike[str]) -> None:
    report_path = str(report_path)
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    payload = {
        "accepted_count": sum(1 for assessment in assessments if assessment.accepted),
        "rejected_count": sum(1 for assessment in assessments if not assessment.accepted),
        "runs": [assessment.to_dict() for assessment in assessments],
    }
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
