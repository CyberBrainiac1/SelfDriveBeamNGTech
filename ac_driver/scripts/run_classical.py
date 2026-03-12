"""
run_classical.py
================
Convenience wrapper — run the classical CV driver.

  python ac_driver/scripts/run_classical.py
  python ac_driver/scripts/run_classical.py --debug --target-speed 50
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Patch sys.argv so main.py sees the right flags
sys.argv = [sys.argv[0], "--mode", "classical"] + sys.argv[1:]

from main import main

if __name__ == "__main__":
    main()
