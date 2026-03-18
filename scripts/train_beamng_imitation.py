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


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train BeamNG imitation driving-policy model")
    parser.add_argument(
        "--teacher-dir",
        action="append",
        required=True,
        help="Teacher directory created by `python main.py --teacher-dir ...`; bare names resolve under training_data/beamng_teacher",
    )
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse()
    ensure_training_roots()
    teacher_dirs = []
    for path in args.teacher_dir:
        if not os.path.isabs(path) and len(os.path.normpath(path).split(os.sep)) == 1:
            teacher_dirs.append(str(BEAMNG_TEACHER_DATA_DIR / path))
        else:
            teacher_dirs.append(path)
    print("=== BeamNG Imitation Training ===")
    print("Teacher dirs:")
    for path in teacher_dirs:
        print(f"  - {path}")
    print(f"Model out : {args.model_path}")
    print(f"Epochs    : {args.epochs}")
    print(f"Batch     : {args.batch_size}\n")
    train_model(
        teacher_dirs=teacher_dirs,
        model_path=args.model_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
