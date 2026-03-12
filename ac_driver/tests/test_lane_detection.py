"""
test_lane_detection.py
======================
Unit tests for perception/lane_detection.py.
Uses synthetic black-and-silver frames — no AC required.
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from config import CFG
from perception.lane_detection import LaneDetector, LaneDetectionResult


@pytest.fixture
def detector() -> LaneDetector:
    return LaneDetector(CFG.perception)


def _make_frame(w: int = 200, h: int = 66) -> np.ndarray:
    """Solid grey frame — no lane lines → detect() should return valid=False."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _make_lane_frame(w: int = 200, h: int = 66) -> np.ndarray:
    """Frame with two white vertical stripes to simulate road markings."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # left lane mark at x~40, right lane mark at x~160
    frame[:, 38:42, :] = 255
    frame[:, 158:162, :] = 255
    return frame


class TestLaneDetector:
    def test_returns_result_type(self, detector: LaneDetector) -> None:
        frame = _make_frame()
        result = detector.detect(frame)
        assert isinstance(result, LaneDetectionResult)

    def test_invalid_on_featureless_frame(self, detector: LaneDetector) -> None:
        result = detector.detect(_make_frame())
        # A featureless grey frame should produce low confidence
        assert result.confidence < 0.5

    def test_offset_range(self, detector: LaneDetector) -> None:
        frame = _make_lane_frame()
        result = detector.detect(frame)
        if result.valid:
            assert -1.0 <= result.offset <= 1.0

    def test_annotated_frame_shape(self, detector: LaneDetector) -> None:
        frame = _make_frame()
        result = detector.detect(frame)
        assert result.overlay.shape == frame.shape

    def test_no_crash_on_tiny_frame(self, detector: LaneDetector) -> None:
        tiny = np.zeros((10, 20, 3), dtype=np.uint8)
        result = detector.detect(tiny)
        assert isinstance(result, LaneDetectionResult)
