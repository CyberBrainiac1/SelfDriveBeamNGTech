"""
desktop_app/widgets/mini_chart.py
Compact QPainter-based line chart. No external chart library needed.
Draws up to two series (e.g. angle + target) with a subtle grid.
"""
from collections import deque
from typing import Optional
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath


class MiniChart(QWidget):
    """
    Lightweight scrolling line chart.
    Call push(value) to add a data point.
    Call push2(value) to add a second series (drawn as dashed line).
    """
    def __init__(self, title: str = "", y_label: str = "",
                 color: str = "#4a90d9", color2: str = "#4caf50",
                 history: int = 200,
                 y_min: Optional[float] = None, y_max: Optional[float] = None,
                 height: int = 120, parent=None):
        super().__init__(parent)
        self._title   = title
        self._y_label = y_label
        self._color   = QColor(color)
        self._color2  = QColor(color2)
        self._buf     = deque(maxlen=history)
        self._buf2: Optional[deque] = None
        self._y_min   = y_min
        self._y_max   = y_max
        self._fixed_h = height
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")

    def push(self, value: float):
        self._buf.append(float(value))
        self.update()

    def push2(self, value: float):
        if self._buf2 is None:
            self._buf2 = deque(maxlen=self._buf.maxlen)
        self._buf2.append(float(value))
        self.update()

    def clear(self):
        self._buf.clear()
        if self._buf2:
            self._buf2.clear()
        self.update()

    # ----------------------------------------------------------------
    def paintEvent(self, _event):
        data = list(self._buf)
        if not data:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        PAD_L, PAD_R, PAD_T, PAD_B = 36, 8, 18, 16

        plot_w = w - PAD_L - PAD_R
        plot_h = h - PAD_T - PAD_B

        # Background
        p.fillRect(0, 0, w, h, QColor("#1e1e1e"))

        # Y range
        all_vals = list(data)
        if self._buf2:
            all_vals += list(self._buf2)
        y_min = self._y_min if self._y_min is not None else min(all_vals)
        y_max = self._y_max if self._y_max is not None else max(all_vals)
        y_range = y_max - y_min if y_max != y_min else 1.0
        # 5% padding
        y_min -= y_range * 0.05
        y_max += y_range * 0.05
        y_range = y_max - y_min

        def px(i, total):
            return PAD_L + int(i / max(total - 1, 1) * plot_w)

        def py(val):
            return PAD_T + plot_h - int((val - y_min) / y_range * plot_h)

        # Grid lines (3 horizontal)
        grid_pen = QPen(QColor("#2a2a2a"), 1, Qt.PenStyle.SolidLine)
        p.setPen(grid_pen)
        for i in range(3):
            gy = PAD_T + int(i * plot_h / 2)
            p.drawLine(PAD_L, gy, PAD_L + plot_w, gy)

        # Zero line if 0 is in range
        if y_min < 0 < y_max:
            zero_y = py(0.0)
            p.setPen(QPen(QColor("#383838"), 1, Qt.PenStyle.DashLine))
            p.drawLine(PAD_L, zero_y, PAD_L + plot_w, zero_y)

        # Border
        p.setPen(QPen(QColor("#333333"), 1))
        p.drawRect(PAD_L, PAD_T, plot_w, plot_h)

        # Y axis labels
        label_font = QFont("Consolas", 8)
        p.setFont(label_font)
        p.setPen(QColor("#555555"))
        for i, val in enumerate([y_min, (y_min + y_max) / 2, y_max]):
            gy = PAD_T + plot_h - int(i * plot_h / 2)
            txt = f"{val:.0f}" if abs(val) >= 10 else f"{val:.1f}"
            p.drawText(0, gy - 5, PAD_L - 2, 12,
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       txt)

        # Series 1
        if len(data) >= 2:
            path = QPainterPath()
            path.moveTo(px(0, len(data)), py(data[0]))
            for i in range(1, len(data)):
                path.lineTo(px(i, len(data)), py(data[i]))
            p.setPen(QPen(self._color, 1.5))
            p.drawPath(path)

        # Series 2
        if self._buf2 and len(self._buf2) >= 2:
            d2 = list(self._buf2)
            path2 = QPainterPath()
            path2.moveTo(px(0, len(d2)), py(d2[0]))
            for i in range(1, len(d2)):
                path2.lineTo(px(i, len(d2)), py(d2[i]))
            pen2 = QPen(self._color2, 1, Qt.PenStyle.DashLine)
            p.setPen(pen2)
            p.drawPath(path2)

        # Current value label (top-right)
        if data:
            val_font = QFont("Consolas", 9)
            val_font.setBold(True)
            p.setFont(val_font)
            p.setPen(self._color)
            p.drawText(PAD_L + plot_w - 60, PAD_T, 60, 14,
                       Qt.AlignmentFlag.AlignRight,
                       f"{data[-1]:.1f}")

        # Title (top-left)
        if self._title:
            title_font = QFont("Segoe UI", 8)
            p.setFont(title_font)
            p.setPen(QColor("#606060"))
            p.drawText(PAD_L + 2, PAD_T, 100, 14,
                       Qt.AlignmentFlag.AlignLeft, self._title)

        p.end()
