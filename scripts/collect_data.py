"""
collect_data.py
===============
CLI entry point for training data collection.
Grabs the screen and syncs with AC telemetry to save labelled frames.

Usage
-----
  python scripts/collect_data.py

Press 'q' in the preview window (or Ctrl+C in the terminal) to stop.
Data is saved to  training_data/assetto_corsa/  as  .npz  shards.
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import CFG
from training.data_collector import collect

if __name__ == "__main__":
    print("=== ACDriver Data Collection ===")
    print(f"Target directory: {CFG.training.data_dir}")
    print("Press 'q' or Ctrl+C to stop.\n")
    collect(CFG)
