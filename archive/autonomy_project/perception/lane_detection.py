"""
Lane / road‑edge detection using classical OpenCV.

Strategy (v1):
  1. Crop to bottom half of the image (ROI).
  2. Convert to HSV and threshold for road‑coloured pixels.
  3. Canny edge detection on the ROI.
  4. Hough line transform to find lane‑like lines.
  5. Separate lines into left/right by slope.
  6. Average each group and compute a lane centre.

The output is a *lane offset* — how far the detected centre is from
the image centre, normalised to [-1, 1].

This is intentionally simple; swap in a neural model later by
replacing this file while keeping the same interface.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config import CFG


# ── Result container ───────────────────────────────────────────────
@dataclass
class LaneDetectionResult:
    offset: float = 0.0            # -1 (left) to +1 (right)  — road centre vs image centre
    confidence: float = 0.0        # 0‑1
    left_lane: Optional[np.ndarray] = None   # averaged line [x1,y1,x2,y2]
    right_lane: Optional[np.ndarray] = None
    road_mask: Optional[np.ndarray] = None   # binary mask (for debug)
    overlay: Optional[np.ndarray] = None     # annotated debug image


# ── Detector class ─────────────────────────────────────────────────
class LaneDetector:
    """Classical lane‑detection pipeline."""

    def __init__(self) -> None:
        self.pcfg = CFG.perception

    # ── public API ─────────────────────────────────────────────────
    def detect(self, bgr_image: np.ndarray) -> LaneDetectionResult:
        """Run full pipeline and return a LaneDetectionResult."""
        h, w = bgr_image.shape[:2]
        roi_top = int(h * self.pcfg.roi_top_frac)
        roi_bottom = int(h * self.pcfg.roi_bottom_frac)
        roi = bgr_image[roi_top:roi_bottom, :]

        road_mask = self._road_mask(roi)
        edges = self._edges(roi, road_mask)
        lines = self._hough_lines(edges)
        left_lines, right_lines = self._separate_lines(lines, roi.shape)
        left_avg = self._average_line(left_lines, roi.shape)
        right_avg = self._average_line(right_lines, roi.shape)

        offset, conf = self._compute_offset(left_avg, right_avg, w)

        # Build debug overlay
        overlay = bgr_image.copy()
        self._draw_overlay(overlay, left_avg, right_avg, roi_top, offset, conf)

        return LaneDetectionResult(
            offset=offset,
            confidence=conf,
            left_lane=left_avg,
            right_lane=right_avg,
            road_mask=road_mask,
            overlay=overlay,
        )

    # ── internals ──────────────────────────────────────────────────
    def _road_mask(self, roi: np.ndarray) -> np.ndarray:
        """HSV thresholding to isolate road (asphalt)."""
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower = np.array(self.pcfg.road_hsv_lower, dtype=np.uint8)
        upper = np.array(self.pcfg.road_hsv_upper, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        # morphology to clean up
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask

    def _edges(self, roi: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Canny edges masked by road region."""
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(grey, (self.pcfg.blur_kernel, self.pcfg.blur_kernel), 0)
        edges = cv2.Canny(blurred, self.pcfg.canny_low, self.pcfg.canny_high)
        # Keep only edges near the road
        edges = cv2.bitwise_and(edges, mask)
        return edges

    def _hough_lines(self, edges: np.ndarray) -> Optional[np.ndarray]:
        return cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=self.pcfg.hough_threshold,
            minLineLength=self.pcfg.hough_min_line_len,
            maxLineGap=self.pcfg.hough_max_line_gap,
        )

    @staticmethod
    def _separate_lines(
        lines: Optional[np.ndarray],
        roi_shape: Tuple[int, int, int],
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Split lines into left (negative slope) and right (positive slope)."""
        left: List[np.ndarray] = []
        right: List[np.ndarray] = []
        if lines is None:
            return left, right
        mid_x = roi_shape[1] // 2
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 == x1:
                continue
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) < 0.3:       # nearly horizontal — ignore
                continue
            # In image coords, y increases downward → left lanes have negative slope
            if slope < 0 and x1 < mid_x and x2 < mid_x:
                left.append(line[0])
            elif slope > 0 and x1 > mid_x and x2 > mid_x:
                right.append(line[0])
        return left, right

    @staticmethod
    def _average_line(
        lines_group: List[np.ndarray],
        roi_shape: Tuple[int, int, int],
    ) -> Optional[np.ndarray]:
        """Fit a single average line through a group of detected segments."""
        if not lines_group:
            return None
        xs, ys = [], []
        for x1, y1, x2, y2 in lines_group:
            xs += [x1, x2]
            ys += [y1, y2]
        if len(xs) < 2:
            return None
        poly = np.polyfit(ys, xs, 1)  # x = f(y)
        y_bottom = roi_shape[0]
        y_top = int(roi_shape[0] * 0.4)
        x_bottom = int(np.polyval(poly, y_bottom))
        x_top = int(np.polyval(poly, y_top))
        return np.array([x_top, y_top, x_bottom, y_bottom])

    @staticmethod
    def _compute_offset(
        left: Optional[np.ndarray],
        right: Optional[np.ndarray],
        img_width: int,
    ) -> Tuple[float, float]:
        """
        Compute normalised lane‑centre offset and confidence.
        Returns (offset, confidence).
        """
        centre_x = img_width / 2.0
        half = img_width / 2.0

        if left is not None and right is not None:
            # Both lanes detected — compute midpoint at bottom
            lane_mid = (left[2] + right[2]) / 2.0
            offset = (lane_mid - centre_x) / half
            confidence = 1.0
        elif left is not None:
            # Only left lane — assume road extends rightward
            lane_mid = left[2] + img_width * 0.35
            offset = np.clip((lane_mid - centre_x) / half, -0.35, 0.35)
            confidence = 0.5
        elif right is not None:
            lane_mid = right[2] - img_width * 0.35
            offset = np.clip((lane_mid - centre_x) / half, -0.35, 0.35)
            confidence = 0.5
        else:
            offset = 0.0
            confidence = 0.0
        return np.clip(offset, -1.0, 1.0), confidence

    # ── debug drawing ─────────────────────────────────────────────
    @staticmethod
    def _draw_overlay(
        img: np.ndarray,
        left: Optional[np.ndarray],
        right: Optional[np.ndarray],
        roi_top: int,
        offset: float,
        confidence: float,
    ) -> None:
        """Draw lane lines and centre indicator on the image."""
        h, w = img.shape[:2]

        def shift_line(line: np.ndarray) -> Tuple[Tuple[int, int], Tuple[int, int]]:
            return (int(line[0]), int(line[1] + roi_top)), (int(line[2]), int(line[3] + roi_top))

        if left is not None:
            pt1, pt2 = shift_line(left)
            cv2.line(img, pt1, pt2, (255, 0, 0), 3)
        if right is not None:
            pt1, pt2 = shift_line(right)
            cv2.line(img, pt1, pt2, (0, 0, 255), 3)

        # Centre target
        target_x = int(w / 2 + offset * w / 2)
        cv2.circle(img, (target_x, h - 30), 10, (0, 255, 0), -1)
        cv2.line(img, (w // 2, h - 40), (w // 2, h - 20), (255, 255, 255), 2)

        # Text
        colour = (0, 255, 0) if confidence > 0.5 else (0, 165, 255) if confidence > 0 else (0, 0, 255)
        cv2.putText(img, f"off={offset:+.2f} conf={confidence:.2f}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
