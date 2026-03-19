"""
Import a BeamNG teacher capture into the canonical training-data area.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from training.paths import BEAMNG_TEACHER_DATA_DIR, ensure_training_roots


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a BeamNG teacher run into training_data/beamng_teacher")
    parser.add_argument("--source-dir", required=True, help="Directory containing labels.csv and images/")
    parser.add_argument("--summary-json", required=True, help="Run summary JSON proving the capture quality")
    parser.add_argument("--name", help="Optional destination folder name under training_data/beamng_teacher")
    parser.add_argument("--force", action="store_true", help="Overwrite destination if it already exists")
    return parser.parse_args()


def main() -> None:
    args = _parse()
    ensure_training_roots()

    source_dir = Path(args.source_dir).resolve()
    summary_json = Path(args.summary_json).resolve()
    if not (source_dir / "labels.csv").is_file():
        raise SystemExit(f"labels.csv not found in {source_dir}")
    if not summary_json.is_file():
        raise SystemExit(f"summary JSON not found: {summary_json}")

    with open(summary_json, "r", encoding="utf-8") as fh:
        summary = json.load(fh)
    run_name = args.name or source_dir.name
    destination = (BEAMNG_TEACHER_DATA_DIR / run_name).resolve()

    if destination.exists():
        if not args.force:
            raise SystemExit(f"Destination already exists: {destination} (use --force to overwrite)")
        shutil.rmtree(destination)

    shutil.copytree(source_dir, destination)
    with open(destination / "run_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"[import] Source      : {source_dir}")
    print(f"[import] Summary     : {summary_json}")
    print(f"[import] Destination : {destination}")


if __name__ == "__main__":
    main()
