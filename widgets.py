"""
ui/widgets.py
Net Max â€“ Reusable widget library.

Every widget here is designed to:
  â€¢ Never clip text regardless of value length
  â€¢ Use QSizePolicy.Expanding so grids distribute space evenly
  â€¢ Accept variable-length strings through proper layout managers
  â€¢ Paint custom chrome (sparklines, mini-bars, icon badges) with QPainter
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QRectF, QTimer, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QLinearGradient, QFontMetrics,
)

from ui.styles import COLORS


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Formatting helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def fmt_bytes(b: float) -> tuple[str, str]:
    """Return (value_str, unit_str) for byte-size display."""
    if b < 0:
        b = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024.0:
            # Avoid showing e.g. "1024.0 KB" â€” stay at 1 decimal
            return f"{b:.1f}", unit
        b /= 1024.0
    return f"{b:.1f}", "PB"


def fmt_speed(bps: float) -> tuple[str, str]:
    """Return (value_str, unit_str) for bandwidth speed display."""
    if bps < 0:
        bps = 0.0
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024.0:
            return f"{bps:.1f}", unit
        bps /= 1024.0
    return f"{bps:.1f}", "GB/s"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SpeedCard â€” top row KPI with colour-coded icon badge + mini sparkline
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SpeedCard(QFrame):
    """
    KPI card for live speed metrics (Download, Upload, Connections, Ping).

    Layout (top to bottom):
        [icon badge]  [label]
        [large value] [unit]
        [mini sparkline]

    Fix list vs the old StatCard:
      â€¢ No setMinimumHeight / setMaximumHeight â€” card grows with font metrics
      â€¢ Value + unit on the same baseline row, unit aligned to BOTTOM of value
      â€¢ Sparkline is a separate QPainter widget that never overlaps text
      â€¢ All QLabels have word-wrap OFF and are sized by their font metrics
    """

    SPARK_SAMPLES = 40

    def __init__(
        self,
        label: str,
        icon_char: str = "↓",
        icon_bg: str   = COLORS["blue"],
        value_color: str = COLORS["label"],
        spark_color: str = COLORS["blue"],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("SpeedCard")
        # Allow card to stretch horizontally; height driven by content
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._spark_color = spark_color
        self._spark_buf: Deque[float] = deque([0.0] * self.SPARK_SAMPLES,
                                              maxlen=self.SPARK_SAMPLES)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(0)

        # â”€â”€ Row 1: badge + label â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.setContentsMargins(0, 0, 0, 0)

        self._badge = _IconBadge(icon_char, icon_bg)
        top_row.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self._lbl_label = QLabel(label)
        self._lbl_label.setObjectName("CardLabel")
        self._lbl_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Preferred)
        # Prevent text clipping â€“ allow wrapping only if really necessary
        self._lbl_label.setWordWrap(False)
        top_row.addWidget(self._lbl_label, 1, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top_row)

        outer.addSpacing(10)

        # â”€â”€ Row 2: value + unit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        val_row.setContentsMargins(0, 0, 0, 0)
        val_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self._lbl_value = QLabel("0.0")
        self._lbl_value.setObjectName("CardValue")
        f = QFont("Segoe UI Variable Display", 26)
        f.setWeight(QFont.Weight.Bold)
        self._lbl_value.setFont(f)
        self._lbl_value.setStyleSheet(f"color: {value_color};")
        self._lbl_value.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Preferred)
        # Key fix: never let the value label clip â€” allow it to be as wide as needed
        self._lbl_value.setMinimumWidth(1)

        self._lbl_unit = QLabel("")
        self._lbl_unit.setObjectName("CardUnit")
        self._lbl_unit.setStyleSheet(f"color: {COLORS['label_2']};")
        self._lbl_unit.setSizePolicy(QSizePolicy.Policy.Preferred,
                                     QSizePolicy.Policy.Preferred)

        val_row.addWidget(self._lbl_value, 0, Qt.AlignmentFlag.AlignBottom)
        val_row.addWidget(self._lbl_unit,  0, Qt.AlignmentFlag.AlignBottom)
        val_row.addStretch()
        outer.addLayout(val_row)

        outer.addSpacing(10)

        # â”€â”€ Row 3: sparkline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._spark = _Sparkline(self._spark_color, height=28)
        outer.addWidget(self._spark)

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def update_value(self, value: str, unit: str = "", spark_sample: float = 0.0):
        self._lbl_value.setText(value)
        if unit:
            self._lbl_unit.setText(unit)
        self._spark_buf.append(spark_sample)
        self._spark.set_data(list(self._spark_buf))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UsageCard â€” second row (Today / Month / 30-days) with down↓ / up↑ breakdown
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class UsageCard(QFrame):
    """
    Larger card showing total data used in a period.

    Shows:
        [icon badge]  [label]
        [large total value + unit]
        [↓ xx.x GB   ↑ xx.x GB]
        [progress bar]

    Fixes vs old approach:
      â€¢ progress bar has fixed height of 3px â€” no min-height that fights the card
      â€¢ down/up sub-labels use a stretchy HBox so they never overlap
      â€¢ card height is entirely driven by content â€” no setFixedHeight/setMaximumHeight
    """

    def __init__(
        self,
        label: str,
        icon_char: str = "📅",
        icon_bg: str   = COLORS["blue"],
        bar_color: str = COLORS["blue"],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("UsageCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._bar_color = bar_color

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(0)

        # â”€â”€ Header: badge + label â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        hdr.setContentsMargins(0, 0, 0, 0)

        self._badge = _IconBadge(icon_char, icon_bg, size=36)
        hdr.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self._lbl_label = QLabel(label)
        self._lbl_label.setObjectName("CardLabel")
        self._lbl_label.setWordWrap(False)
        self._lbl_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Preferred)
        hdr.addWidget(self._lbl_label, 1)
        outer.addLayout(hdr)
        outer.addSpacing(10)

        # â”€â”€ Total value â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        val_row.setContentsMargins(0, 0, 0, 0)
        val_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self._lbl_total = QLabel("0.0")
        self._lbl_total.setObjectName("CardValue")
        f = QFont("Segoe UI Variable Display", 30)
        f.setWeight(QFont.Weight.Bold)
        self._lbl_total.setFont(f)
        self._lbl_total.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Preferred)
        self._lbl_total.setMinimumWidth(1)

        self._lbl_unit = QLabel("MB")
        self._lbl_unit.setObjectName("CardUnit")
        self._lbl_unit.setStyleSheet(f"color: {COLORS['label_2']};")

        val_row.addWidget(self._lbl_total, 0, Qt.AlignmentFlag.AlignBottom)
        val_row.addWidget(self._lbl_unit,  0, Qt.AlignmentFlag.AlignBottom)
        val_row.addStretch()
        outer.addLayout(val_row)
        outer.addSpacing(8)

        # â”€â”€ Down / Up sub-row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sub_row = QHBoxLayout()
        sub_row.setSpacing(0)
        sub_row.setContentsMargins(0, 0, 0, 0)

        self._lbl_down = QLabel("↓ 0 B")
        self._lbl_down.setStyleSheet(
            f"color: {COLORS['green']}; font-size: 12px; font-weight: 600;"
        )
        self._lbl_down.setWordWrap(False)

        self._lbl_up = QLabel("↑ 0 B")
        self._lbl_up.setStyleSheet(
            f"color: {COLORS['purple']}; font-size: 12px; font-weight: 600;"
        )
        self._lbl_up.setWordWrap(False)

        sub_row.addWidget(self._lbl_down)
        sub_row.addSpacing(16)
        sub_row.addWidget(self._lbl_up)
        sub_row.addStretch()
        outer.addLayout(sub_row)
        outer.addSpacing(10)

        # â”€â”€ Progress bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._progress = _ThinBar(bar_color)
        outer.addWidget(self._progress)

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def update_data(
        self,
        total_recv: int,
        total_sent: int,
        quota_bytes: int = 0,
    ):
        total = total_recv + total_sent
        t_val, t_unit = fmt_bytes(total)
        self._lbl_total.setText(t_val)
        self._lbl_unit.setText(t_unit)

        d_val, d_unit = fmt_bytes(total_recv)
        u_val, u_unit = fmt_bytes(total_sent)
        self._lbl_down.setText(f"↓ {d_val} {d_unit}")
        self._lbl_up.setText(f"↑ {u_val} {u_unit}")

        if quota_bytes > 0:
            pct = min(total / quota_bytes, 1.0)
        else:
            pct = 0.0
        self._progress.set_fraction(pct)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# _IconBadge â€” coloured rounded square with a centred character/emoji
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _IconBadge(QWidget):
    """
    Fixed-size rounded-square badge.  Accepts a single Unicode character or
    short emoji.  Painted entirely via QPainter so border-radius works on all
    Windows DPI scales without QSS quirks.
    """

    def __init__(self, char: str, bg_color: str, size: int = 38, parent=None):
        super().__init__(parent)
        self._char = char
        self._bg = QColor(bg_color)
        # Make bg slightly transparent for a glassy feel
        self._bg.setAlpha(180)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        radius = self._size * 0.28
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._bg))
        p.drawRoundedRect(0, 0, self._size, self._size, radius, radius)

        font = QFont("Segoe UI Emoji", int(self._size * 0.44))
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(
            QRectF(0, 0, self._size, self._size),
            Qt.AlignmentFlag.AlignCenter,
            self._char,
        )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# _Sparkline â€” 40-sample rolling micro chart
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _Sparkline(QWidget):
    """
    Thin anti-aliased line chart that renders 40 data points.
    Height is fixed; width expands with the card.
    """

    def __init__(self, color: str, height: int = 28, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._data: list[float] = [0.0] * 40
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_data(self, data: list[float]):
        self._data = data
        self.update()

    def paintEvent(self, _event):
        if not self._data or max(self._data) == 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        n = len(self._data)
        mx = max(self._data) or 1.0

        def px(i: int) -> float:
            return i * w / max(n - 1, 1)

        def py(v: float) -> float:
            return h - 2 - (v / mx) * (h - 4)

        # Build path
        path = QPainterPath()
        path.moveTo(px(0), py(self._data[0]))
        for i in range(1, n):
            # Smooth cubic bezier
            x0 = px(i - 1);  y0 = py(self._data[i - 1])
            x1 = px(i);      y1 = py(self._data[i])
            cx = (x0 + x1) / 2
            path.cubicTo(cx, y0, cx, y1, x1, y1)

        # Fill under the curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(px(n - 1), h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()

        fill_color = QColor(self._color)
        fill_color.setAlpha(30)
        p.fillPath(fill_path, QBrush(fill_color))

        # Stroke
        pen = QPen(self._color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# _ThinBar â€” a 3px tall progress bar drawn via QPainter
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _ThinBar(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._frac = 0.0
        self.setFixedHeight(3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_fraction(self, frac: float):
        self._frac = max(0.0, min(frac, 1.0))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Track
        track = QColor(COLORS["surface_2"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track))
        p.drawRoundedRect(0, 0, w, h, 1.5, 1.5)
        # Fill
        fw = int(w * self._frac)
        if fw > 0:
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(0, 0, fw, h, 1.5, 1.5)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AdapterRow â€” one network adapter entry in the adapter card
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AdapterRow(QWidget):
    """
    Single adapter entry:
        ● Name  Active        ↓ xx.x GB  ↑ xx.x MB
          1000 Mbps
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 8)
        root.setSpacing(2)

        # Top row: dot + name + status + spacer + traffic
        top = QHBoxLayout()
        top.setSpacing(6)
        top.setContentsMargins(0, 0, 0, 0)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color: {COLORS['green']}; font-size: 10px;")

        self._lbl_name = QLabel("-")
        self._lbl_name.setStyleSheet(
            f"color: {COLORS['label']}; font-size: 13px; font-weight: 600;"
        )
        self._lbl_name.setWordWrap(False)

        self._lbl_status = QLabel("Active")
        self._lbl_status.setStyleSheet(
            f"color: {COLORS['green']}; font-size: 11px; font-weight: 500;"
            f" padding: 1px 6px; background: #0D2B1A; border-radius: 4px;"
        )

        self._lbl_traffic = QLabel("↓ 0 B  ↑ 0 B")
        self._lbl_traffic.setStyleSheet(f"color: {COLORS['label_2']}; font-size: 12px;")
        self._lbl_traffic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._lbl_name, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._lbl_status, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        top.addWidget(self._lbl_traffic, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(top)

        # Bottom: speed label
        bot = QHBoxLayout()
        bot.setContentsMargins(20, 0, 0, 0)
        self._lbl_speed = QLabel("")
        self._lbl_speed.setStyleSheet(f"color: {COLORS['label_3']}; font-size: 11px;")
        bot.addWidget(self._lbl_speed)
        bot.addStretch()
        root.addLayout(bot)

    def set_adapter(self, name: str, is_up: bool, speed_mbps,
                    bytes_recv: int, bytes_sent: int):
        self._lbl_name.setText(name)

        if is_up:
            self._dot.setStyleSheet(
                f"color: {COLORS['green']}; font-size: 10px;"
            )
            self._lbl_status.setText("Active")
            self._lbl_status.setStyleSheet(
                f"color: {COLORS['green']}; font-size: 11px; font-weight: 500;"
                f" padding: 1px 6px; background: #0D2B1A; border-radius: 4px;"
            )
        else:
            self._dot.setStyleSheet(
                f"color: {COLORS['label_3']}; font-size: 10px;"
            )
            self._lbl_status.setText("Inactive")
            self._lbl_status.setStyleSheet(
                f"color: {COLORS['label_3']}; font-size: 11px; font-weight: 500;"
                f" padding: 1px 6px; background: #252834; border-radius: 4px;"
            )

        r_v, r_u = fmt_bytes(bytes_recv)
        s_v, s_u = fmt_bytes(bytes_sent)
        self._lbl_traffic.setText(
            f"<span style='color:{COLORS['green']}'>↓ {r_v} {r_u}</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color:{COLORS['purple']}'>↑ {s_v} {s_u}</span>"
        )
        self._lbl_traffic.setTextFormat(Qt.TextFormat.RichText)

        if speed_mbps:
            self._lbl_speed.setText(f"{int(speed_mbps)} Mbps")
        else:
            self._lbl_speed.setText("")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SidebarButton â€” macOS-style nav pill
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SidebarButton(QPushButton):
    """Navigation button with icon + label. Active state highlighted via property."""

    def __init__(self, icon_char: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarBtn")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        self._icon_lbl = QLabel(icon_char)
        self._icon_lbl.setStyleSheet(
        "background: transparent;")

        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        icon_font = QFont()
        icon_font.setPointSize(15)
        self._icon_lbl.setFont(icon_font)

        self._text_lbl = QLabel(label)
        self._text_lbl.setStyleSheet(
        "background: transparent;")

        self._text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_font = QFont("Segoe UI Variable Display", 13)
        text_font.setWeight(QFont.Weight.Medium)
        self._text_lbl.setFont(text_font)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

        self.setMinimumHeight(42)
        self.setFlat(True)
        self._active = False

    def set_active(self, active: bool):
        self._active = active

        color = COLORS["sidebar_active_text"] if active else COLORS["label_2"]

        self._text_lbl.setStyleSheet(
        f"background: transparent; color: {color};")

        self._icon_lbl.setStyleSheet(
        f"background: transparent; color: {color};")

        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SectionHeader â€” small label above a content group
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SectionHeader(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("SectionTitle")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class HDivider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet(f"color: {COLORS['border_card']};")
        self.setFixedHeight(1)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LoadingSpinner
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class LoadingSpinner(QWidget):
    def __init__(self, size: int = 28, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(25)

    def _tick(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = 3
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        pen = QPen(QColor(COLORS["blue"]), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, self._angle * 16, 270 * 16)

    def stop(self):
        self._timer.stop()
        self.hide()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MiniBar â€” proportional bar (used in app table)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MiniBar(QWidget):
    def __init__(self, color: str = COLORS["blue"], parent=None):
        super().__init__(parent)
        self._frac  = 0.0
        self._color = QColor(color)
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_value(self, value: int, max_val: int):
        self._frac = value / max(max_val, 1)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(COLORS["surface_2"])))
        p.drawRoundedRect(0, 0, w, h, 2, 2)
        fw = int(w * min(self._frac, 1.0))
        if fw > 0:
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(0, 0, fw, h, 2, 2)


