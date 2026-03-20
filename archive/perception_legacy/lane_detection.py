"""
lane_detection.py
=================
Classical OpenCV lane-detection pipeline for Assetto Corsa.

Compared to the original ACDriver which only ran Canny edges for screen
capture data collection, this adds:
  • HSV road masking
  • Hough line grouping into left / right lanes
  • Lane-centre offset computation (normalised -1 … +1)
  • Confidence score
  • Annotated debug overlay image

The interface is identical to the BeamNG version so code can be shared.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from config import CFG


@dataclass
class LaneDetectionResult:
    offset: float = 0.0        # -1 (left) … +1 (right)  road centre vs image centre
    confidence: float = 0.0    # 0–1
    left_lane: Optional[np.ndarray] = None
    right_lane: Optional[np.ndarray] = None
    road_mask: Optional[np.ndarray] = None
    overlay: Optional[np.ndarray] = None


class LaneDetector:
    """
    Classical Canny + Hough lane detector.
    Input : BGR image (any size — uses the frame as-is)
    Output: LaneDetectionResult with lane offset and debug overlay
    """

    def __init__(self, pcfg=None) -> None:
        self.pcfg = pcfg or CFG.perception
        self.last_result: LaneDetectionResult = LaneDetectionResult()

    # ── public API ─────────────────────────────────────────────────
    def detect(self, bgr: np.ndarray) -> LaneDetectionResult:
        h, w = bgr.shape[:2]
        roi_top = int(h * self.pcfg.roi_top_frac)
        roi = bgr[roi_top:, :]

        mask   = self._road_mask(roi)
        edges  = self._edges(roi, mask)
        lines  = self._hough(edges)
        lefts, rights = self._separate(lines, roi.shape)
        left_avg  = self._average_line(lefts, roi.shape)
        right_avg = self._average_line(rights, roi.shape)

        offset, conf = self._offset(left_avg, right_avg, w)

        overlay = bgr.copy()
        self._draw(overlay, left_avg, right_avg, roi_top, offset, conf)

        result = LaneDetectionResult(
            offset=offset,
            confidence=conf,
            left_lane=left_avg,
            right_lane=right_avg,
            road_mask=mask,
            overlay=overlay,
        )
        self.last_result = result
        return result

    # ── internals ──────────────────────────────────────────────────
    def _road_mask(self, roi: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lo = np.array(self.pcfg.road_hsv_lower, np.uint8)
        hi = np.array(self.pcfg.road_hsv_upper, np.uint8)
        mask = cv2.inRange(hsv, lo, hi)
        k = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k, iterations=1)
        return mask

    def _edges(self, roi: np.ndarray, mask: np.ndarray) -> np.ndarray:
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(grey,
                                (self.pcfg.blur_kernel, self.pcfg.blur_kernel), 0)
        edges = cv2.Canny(blur, self.pcfg.canny_low, self.pcfg.canny_high)
        return cv2.bitwise_and(edges, mask)

    def _hough(self, edges: np.ndarray) -> Optional[np.ndarray]:
        return cv2.HoughLinesP(
            edges, 1, np.pi / 180,
            threshold=self.pcfg.hough_threshold,
            minLineLength=self.pcfg.hough_min_line_len,
            maxLineGap=self.pcfg.hough_max_line_gap,
        )

    @staticmethod
    def _separate(
        lines: Optional[np.ndarray],
        roi_shape: Tuple[int, int, int],
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        left, right = [], []
        if lines is None:
            return left, right
        mid = roi_shape[1] // 2
        for ln in lines:
            x1, y1, x2, y2 = ln[0]
            if x2 == x1:
                continue
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) < 0.3:
                continue
            if slope < 0 and x1 < mid and x2 < mid:
                left.append(ln[0])
            elif slope > 0 and x1 > mid and x2 > mid:
                right.append(ln[0])
        return left, right

    @staticmethod
    def _average_line(
        group: List[np.ndarray],
        roi_shape: Tuple[int, int, int],
    ) -> Optional[np.ndarray]:
        if not group:
            return None
        xs, ys = [], []
        for x1, y1, x2, y2 in group:
            xs += [x1, x2]
            ys += [y1, y2]
        if len(xs) < 2:
            return None
        poly = np.polyfit(ys, xs, 1)
        y_bot = roi_shape[0]
        y_top = int(roi_shape[0] * 0.4)
        x_bot = int(np.polyval(poly, y_bot))
        x_top = int(np.polyval(poly, y_top))
        return np.array([x_top, y_top, x_bot, y_bot])

    @staticmethod
    def _offset(
        left: Optional[np.ndarray],
        right: Optional[np.ndarray],
        img_w: int,
    ) -> Tuple[float, float]:
        cx = img_w / 2.0
        half = img_w / 2.0
        if left is not None and right is not None:
            lane_mid = (left[2] + right[2]) / 2.0
            conf = 1.0
        elif left is not None:
            lane_mid = left[2] + img_w * 0.25
            conf = 0.5
        elif right is not None:
            lane_mid = right[2] - img_w * 0.25
            conf = 0.5
        else:
            return 0.0, 0.0
        return float(np.clip((lane_mid - cx) / half, -1.0, 1.0)), conf

    @staticmethod
    def _draw(
        img: np.ndarray,
        left: Optional[np.ndarray],
        right: Optional[np.ndarray],
        roi_top: int,
        offset: float,
        conf: float,
    ) -> None:
        h, w = img.shape[:2]

        def shift(ln): return (int(ln[0]), int(ln[1] + roi_top)), \
                               (int(ln[2]), int(ln[3] + roi_top))

        if left  is not None: cv2.line(img, *shift(left),  (255, 0,   0), 2)
        if right is not None: cv2.line(img, *shift(right), (0,   0, 255), 2)

        tx = int(w / 2 + offset * w / 2)
        cv2.circle(img, (tx, h - 20), 8, (0, 255, 0), -1)
        cv2.line(img, (w // 2, h - 28), (w // 2, h - 12), (255, 255, 255), 1)

        col = (0, 255, 0) if conf > 0.5 else (0, 165, 255) if conf > 0 else (0, 0, 255)
        cv2.putText(img, f"off={offset:+.2f} c={conf:.1f}",
                    (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
