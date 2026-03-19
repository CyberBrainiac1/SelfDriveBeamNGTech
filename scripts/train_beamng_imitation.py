"""
Train a BeamNG driving-policy imitation model from one or more teacher directories.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from training.beamng_imitation import DEFAULT_MODEL_PATH, train_model
from training.paths import BEAMNG_TEACHER_DATA_DIR, ensure_training_roots
from training.beamng_teacher_runs import (
    DEFAULT_APPROVED_RACE_MAPS,
    curate_teacher_runs,
    discover_teacher_dirs,
    write_curation_report,
)


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train BeamNG imitation driving-policy model")
    parser.add_argument(
        "--teacher-dir",
        action="append",
        help="Teacher directory created by `python main.py --teacher-dir ...`; bare names resolve under training_data/beamng_teacher. If omitted, all canonical teacher dirs are scanned.",
    )
    parser.add_argument("--teacher-root", default=str(BEAMNG_TEACHER_DATA_DIR))
    parser.add_argument(
        "--allow-map",
        action="append",
        help=f"Approved race maps for training. Defaults to: {', '.join(DEFAULT_APPROVED_RACE_MAPS)}",
    )
    parser.add_argument("--min-frames", type=int, default=120)
    parser.add_argument("--min-ticks", type=int, default=120)
    parser.add_argument("--max-damage", type=float, default=0.0)
    parser.add_argument("--min-max-speed-kph", type=float, default=40.0)
    parser.add_argument(
        "--curation-report",
        default=os.path.join("models", "beamng_teacher_curation.json"),
        help="Write accepted/rejected teacher-run report here.",
    )
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def _resolve_teacher_dirs(values: list[str] | None, teacher_root: str) -> list[str]:
    if not values:
        return discover_teacher_dirs(teacher_root)
    resolved: list[str] = []
    for path in values:
        if not os.path.isabs(path) and len(os.path.normpath(path).split(os.sep)) == 1:
            resolved.append(str(BEAMNG_TEACHER_DATA_DIR / path))
        else:
            resolved.append(path)
    return resolved


if __name__ == "__main__":
    args = _parse()
    ensure_training_roots()
    teacher_dirs = _resolve_teacher_dirs(args.teacher_dir, args.teacher_root)
    approved_maps = args.allow_map or list(DEFAULT_APPROVED_RACE_MAPS)
    assessments = curate_teacher_runs(
        teacher_dirs=teacher_dirs,
        approved_maps=approved_maps,
        min_frames=args.min_frames,
        min_ticks=args.min_ticks,
        max_damage=args.max_damage,
        min_max_speed_kph=args.min_max_speed_kph,
    )
    write_curation_report(assessments, args.curation_report)
    accepted_teacher_dirs = [assessment.teacher_dir for assessment in assessments if assessment.accepted]

    print("=== BeamNG Imitation Training ===")
    print(f"Teacher root : {args.teacher_root}")
    print(f"Curation file: {args.curation_report}")
    print(f"Approved maps: {', '.join(approved_maps)}")
    print("Accepted teacher dirs:")
    for path in accepted_teacher_dirs:
        print(f"  - {path}")
    rejected = [assessment for assessment in assessments if not assessment.accepted]
    if rejected:
        print("Rejected teacher dirs:")
        for assessment in rejected:
            reason_text = "; ".join(assessment.reasons)
            print(f"  - {assessment.teacher_dir}: {reason_text}")
    print(f"Model out : {args.model_path}")
    print(f"Epochs    : {args.epochs}")
    print(f"Batch     : {args.batch_size}\n")
    if not accepted_teacher_dirs:
        raise SystemExit(
            "No teacher runs passed curation. Check the curation report and add clean race-map captures with run_summary.json."
        )
    train_model(
        teacher_dirs=accepted_teacher_dirs,
        model_path=args.model_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
