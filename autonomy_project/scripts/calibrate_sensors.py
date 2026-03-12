#!/usr/bin/env python3
"""
calibrate_sensors.py — View live sensor data to tune perception thresholds.

Opens the BeamNG camera feed and shows:
  • Raw colour image
  • HSV‑thresholded road mask
  • Canny edges
  • Hough lines

Use the printed pixel‑value readout to adjust the HSV bounds in config.py.

Press 'q' to quit.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np

from config import CFG
from beamng_interface.connection import SimConnection
from beamng_interface.scenario_manager import ScenarioManager
from beamng_interface.sensors import SensorSuite
from utils.image_utils import stack_debug


def main() -> None:
    CFG.debug.show_overlay = False  # we handle our own windows

    conn = SimConnection()
    try:
        bng = conn.open()
        scene = ScenarioManager(bng)
        vehicle = scene.create_and_start()
        sensors = SensorSuite(vehicle)
        sensors.attach_all()

        print("[calibrate] Streaming. Press 'q' to quit.")

        while True:
            bng.control.step(CFG.loop.beamng_steps)
            data = sensors.poll()

            if data.colour_image is None:
                continue

            img = data.colour_image
            h, w = img.shape[:2]
            roi_top = int(h * CFG.perception.roi_top_frac)
            roi = img[roi_top:, :]

            # HSV mask
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower = np.array(CFG.perception.road_hsv_lower, dtype=np.uint8)
            upper = np.array(CFG.perception.road_hsv_upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)

            # Edges
            grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(grey, CFG.perception.canny_low, CFG.perception.canny_high)

            canvas = stack_debug(roi, mask, edges, target_h=300)
            cv2.imshow("Calibrate Sensors", canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    finally:
        cv2.destroyAllWindows()
        conn.close()


if __name__ == "__main__":
    main()
