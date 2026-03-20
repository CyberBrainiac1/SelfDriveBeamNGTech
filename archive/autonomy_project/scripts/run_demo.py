#!/usr/bin/env python3
"""
run_demo.py — Convenience launcher with optional CLI overrides.

Usage:
    python scripts/run_demo.py                     # defaults
    python scripts/run_demo.py --speed 60 --no-overlay
"""

from __future__ import annotations

import argparse
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import CFG


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Launch autonomy demo")
    p.add_argument("--speed", type=float, default=None, help="Target speed in kph")
    p.add_argument("--no-overlay", action="store_true", help="Disable debug window")
    p.add_argument("--save-frames", action="store_true", help="Save camera frames to disk")
    p.add_argument("--no-csv", action="store_true", help="Disable CSV logging")
    p.add_argument("--level", type=str, default=None, help="Map name")
    p.add_argument("--vehicle", type=str, default=None, help="Vehicle model")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Apply overrides to singleton config
    if args.speed is not None:
        CFG.speed.target_speed_kph = args.speed
    if args.no_overlay:
        CFG.debug.show_overlay = False
    if args.save_frames:
        CFG.debug.save_frames = True
    if args.no_csv:
        CFG.debug.log_csv = False
    if args.level:
        CFG.scenario.level = args.level
    if args.vehicle:
        CFG.scenario.vehicle_model = args.vehicle

    # Import and run
    from main import main as run_main
    run_main()


if __name__ == "__main__":
    main()
