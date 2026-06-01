"""
ui/stats_page.py
Statistics page: historical charts for last hour, 24 h, and 30 days.
"""

from collections import deque
from typing import Deque, List
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import QTimer

import pyqtgraph as pg

from ui.styles import COLORS
from ui.widgets import fmt_bytes, SectionHeader
from database.db_manager import DatabaseManager
from models.data_models import BandwidthSample

pg.setConfigOptions(antialias=True, foreground=COLORS["label_2"], background=COLORS["surface_1"])

HOUR_POINTS  = 3600   # 1 point per second  â†’ 1 hour
DAY_POINTS   = 1440   # 1 point per minute  â†’ 24 hours
MONTH_POINTS = 30     # 1 point per day     â†’ 30 days


class StatsPage(QWidget):
    """Tabbed historical bandwidth charts."""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db

        # Buffers for live accumulation
        self._hour_recv:  Deque[float] = deque([0.0] * HOUR_POINTS,  maxlen=HOUR_POINTS)
        self._hour_sent:  Deque[float] = deque([0.0] * HOUR_POINTS,  maxlen=HOUR_POINTS)

        # Per-minute accumulator
        self._min_recv_acc = 0.0
        self._min_sent_acc = 0.0
        self._sec_in_min   = 0

        self._day_recv:   Deque[float] = deque([0.0] * DAY_POINTS,   maxlen=DAY_POINTS)
        self._day_sent:   Deque[float] = deque([0.0] * DAY_POINTS,   maxlen=DAY_POINTS)

        self._setup_ui()
        self._load_db_history()

        # Refresh 30-day chart every 5 min
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._load_db_history)
        self._refresh_timer.start(300_000)

    # â”€â”€ UI construction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(0)

        title = QLabel("Statistics")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addSpacing(20)
        
        tabs = QTabWidget()
        root.addWidget(tabs)

        # â”€â”€ Last Hour â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hour_page = QWidget()
        hour_layout = QVBoxLayout(hour_page)
        hour_layout.setContentsMargins(12, 12, 12, 12)
        self._hour_plot = self._make_plot("Speed (B/s)", "seconds ago", HOUR_POINTS)
        self._curve_h_dl = self._hour_plot.plot(
            pen=pg.mkPen(COLORS["green"], width=2),
            fillLevel=0, brush=pg.mkBrush(63, 185, 80, 40), name="Download",
        )
        self._curve_h_ul = self._hour_plot.plot(
            pen=pg.mkPen(COLORS["red"], width=2),
            fillLevel=0, brush=pg.mkBrush(248, 81, 73, 40), name="Upload",
        )
        hour_layout.addWidget(self._hour_plot)
        tabs.addTab(hour_page, "Last Hour")

        # â”€â”€ Last 24 Hours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        day_page = QWidget()
        day_layout = QVBoxLayout(day_page)
        day_layout.setContentsMargins(12, 12, 12, 12)
        self._day_plot = self._make_plot("Volume (MB)", "minutes ago", DAY_POINTS)
        self._curve_d_dl = self._day_plot.plot(
            pen=pg.mkPen(COLORS["green"], width=2),
            fillLevel=0, brush=pg.mkBrush(63, 185, 80, 40), name="Download",
        )
        self._curve_d_ul = self._day_plot.plot(
            pen=pg.mkPen(COLORS["red"], width=2),
            fillLevel=0, brush=pg.mkBrush(248, 81, 73, 40), name="Upload",
        )
        day_layout.addWidget(self._day_plot)
        tabs.addTab(day_page, "Last 24 Hours")

        # â”€â”€ Last 24 Hours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        month_page = QWidget()
        month_layout = QVBoxLayout(month_page)
        month_layout.setContentsMargins(12, 12, 12, 12)
        self._month_plot = self._make_bar_plot()
        month_layout.addWidget(self._month_plot)
        tabs.addTab(month_page, "Last 24 Hours")

    @staticmethod
    def _make_plot(y_label: str, x_label: str, n_points: int) -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setMinimumHeight(300)
        pw.setBackground(COLORS["surface_1"])
        pw.getPlotItem().showGrid(x=False, y=True, alpha=0.15)
        pw.setLabel("left", y_label, color=COLORS["label_2"])
        pw.setLabel("bottom", x_label, color=COLORS["label_2"])
        pw.setXRange(0, n_points, padding=0)
        legend = pw.addLegend(offset=(10, 10))
        legend.setLabelTextColor(COLORS["label_2"])
        return pw

    @staticmethod
    def _make_bar_plot() -> pg.PlotWidget:
        pw = pg.PlotWidget()
        pw.setMinimumHeight(300)
        pw.setBackground(COLORS["surface_1"])
        pw.getPlotItem().showGrid(x=False, y=True, alpha=0.15)
        pw.setLabel("left", "Volume (MB)", color=COLORS["label_2"])
        pw.setLabel("bottom", "Days ago", color=COLORS["label_2"])
        return pw

    # â”€â”€ Data updates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_sample(self, sample: BandwidthSample):
        """Feed a 1-second bandwidth sample into both rolling buffers."""
        self._hour_recv.append(sample.recv_speed)
        self._hour_sent.append(sample.sent_speed)

        self._min_recv_acc += sample.recv_speed
        self._min_sent_acc += sample.sent_speed
        self._sec_in_min   += 1

        if self._sec_in_min >= 60:
            # Push a per-minute megabyte volume point
            self._day_recv.append(self._min_recv_acc / (1024 * 1024))
            self._day_sent.append(self._min_sent_acc / (1024 * 1024))
            self._min_recv_acc = 0.0
            self._min_sent_acc = 0.0
            self._sec_in_min   = 0

        x_hour  = list(range(HOUR_POINTS))
        x_day   = list(range(DAY_POINTS))

        self._curve_h_dl.setData(x_hour, list(self._hour_recv))
        self._curve_h_ul.setData(x_hour, list(self._hour_sent))
        self._curve_d_dl.setData(x_day,  list(self._day_recv))
        self._curve_d_ul.setData(x_day,  list(self._day_sent))

    def _load_db_history(self):
        """Refresh the 30-day bar chart from the database."""
        self._month_plot.clear()
        rows = self._db.get_daily_totals(30)
        if not rows:
            return

        # rows are ordered DESC (newest first)
        n = len(rows)
        x = list(range(n - 1, -1, -1))  # 0 = oldest â†’ n-1 = today
        recv_mb = [r["bytes_recv"] / (1024 * 1024) for r in reversed(rows)]
        sent_mb = [r["bytes_sent"] / (1024 * 1024) for r in reversed(rows)]

        w = 0.35
        dl_bars = pg.BarGraphItem(x=[xi - w/2 for xi in x], height=recv_mb, width=w,
                                  brush=pg.mkBrush(COLORS["green"]))
        ul_bars = pg.BarGraphItem(x=[xi + w/2 for xi in x], height=sent_mb, width=w,
                                  brush=pg.mkBrush(COLORS["red"]))

        self._month_plot.addItem(dl_bars)
        self._month_plot.addItem(ul_bars)

        legend = self._month_plot.addLegend(offset=(10, 10))
        legend.setLabelTextColor(COLORS["label_2"])
        legend.addItem(pg.PlotDataItem(pen=pg.mkPen(COLORS["green"])), "Download")
        legend.addItem(pg.PlotDataItem(pen=pg.mkPen(COLORS["red"])),   "Upload")


