"""
run_neural.py
=============
Convenience wrapper — run the CNN-based neural driver.

  python ac_driver/scripts/run_neural.py
  python ac_driver/scripts/run_neural.py --debug --target-speed 70
"""

from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.argv = [sys.argv[0], "--mode", "neural"] + sys.argv[1:]

from main import main

if __name__ == "__main__":
    main()
