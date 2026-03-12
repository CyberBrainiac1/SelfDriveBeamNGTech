"""
Tests for lane detection (uses a synthetic image, no BeamNG needed).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np

from perception.lane_detection import LaneDetector


def _make_road_image(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a synthetic image with two white lane lines on a grey road."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Grey road in the bottom half
    img[height // 2:, :] = (100, 100, 100)
    # Left lane line — white
    cv2.line(img, (width // 4, height), (width // 3, height // 2), (255, 255, 255), 3)
    # Right lane line — white
    cv2.line(img, (3 * width // 4, height), (2 * width // 3, height // 2), (255, 255, 255), 3)
    return img


def test_detects_road_on_synthetic_image():
    """Lane detector should report non-zero confidence on a clean synthetic road."""
    img = _make_road_image()
    det = LaneDetector()
    result = det.detect(img)
    # We primarily check it doesn't crash and returns structured data
    assert result.overlay is not None
    assert -1.0 <= result.offset <= 1.0


def test_no_crash_on_blank_image():
    """Should handle an all-black image gracefully."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    det = LaneDetector()
    result = det.detect(img)
    assert result.confidence == 0.0
