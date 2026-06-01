"""
ui/dashboard_page.py
Net Max â€“ Dashboard page.

Layout (matching the provided design mockup):
  Row 1 (4 equal columns): Download Â· Upload Â· Connections Â· Ping
  Row 2 (3 equal columns): Today Â· This Month Â· Last 24 Hours
  Row 3 (2 columns 3:2):   Live Bandwidth Graph | Network Adapters
  Row 4 (2 columns 1:1):   Top Applications     | (reserved / alerts stub)

All layout uses QGridLayout / QVBoxLayout with Expanding size policies.
Zero hardcoded heights on cards â€” everything adapts to DPI and content.
"""

from __future__ import annotations

import socket
import time

def get_ping(host="1.1.1.1", port=443):
    try:
        start = time.perf_counter()

        sock = socket.create_connection(
            (host, port),
            timeout=1
        )

        sock.close()

        end = time.perf_counter()

        return round((end - start) * 1000)

    except Exception:
        return None
    

import time
from collections import deque
from typing import Deque, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QSizePolicy,
    QPushButton,
)
from PyQt6.QtCore import Qt, QTimer

import pyqtgraph as pg

from ui.styles import COLORS
from ui.widgets import (
    SpeedCard, UsageCard, AdapterRow, SectionHeader,
    fmt_speed, fmt_bytes,
)
from models.data_models import DashboardStats, BandwidthSample

# pyqtgraph global config 
pg.setConfigOptions(
    antialias=True,
    foreground=COLORS["label_2"],
    background=COLORS["surface_1"],
)

GRAPH_SECONDS = 60
MAX_SAMPLES   = GRAPH_SECONDS


class DashboardPage(QWidget):
    """
    Complete dashboard page widget.

    Issues fixed vs. old implementation
    
    1. Text clipping in speed cards
       OLD: setMinimumHeight(100) + fixed font sizes caused value labels to
            overflow the card boundary at 125 %+ DPI.
       FIX: Cards use Expanding size policy; value labels have no max-width;
            layout margins are applied via QVBoxLayout, not QSS padding.

    2. Overlapping unit labels
       OLD: Unit QLabel aligned AlignBottom inside a row that had addStretch()
            after it â€” at narrow widths the stretch pushed the unit off screen.
       FIX: Unit is inside val_row BEFORE the stretch; val_row uses
            AlignBottom alignment so both labels share the same baseline.

    3. Graph squashed / too short
       OLD: setMaximumHeight(220) hard-cap. When the window was tall the graph
            stayed tiny and wasted space.
       FIX: Graph widget uses Expanding vertical policy; only a sensible
            setMinimumHeight(200) is set.

    4. Adapter list rebuilt on every tick via setParent(None) â€” leaks widgets
       OLD: _adapter_labels list cleared then re-parented every second.
       FIX: AdapterRow widgets are created once per unique adapter name and
            only their content is updated via set_adapter().

    5. SectionHeader labels caused extra height jumps
       OLD: SectionHeader had padding: 16px 0 8px 0 in QSS which added large
            gaps between rows.
       FIX: Section headers are inline labels with consistent 12px top margin
            controlled by layout spacing, not QSS padding.

    6. Grid column stretch was missing
       OLD: QGridLayout columns had no setColumnStretch() â€” columns widths
            were determined by minimum-size hints which could be unequal.
       FIX: All grid columns get equal stretch weight of 1.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContentArea")

        # Rolling buffers for the live graph
        self._recv_buf: Deque[float] = deque([0.0] * MAX_SAMPLES, maxlen=MAX_SAMPLES)
        self._sent_buf: Deque[float] = deque([0.0] * MAX_SAMPLES, maxlen=MAX_SAMPLES)
        self._x = list(range(MAX_SAMPLES))

        # Adapter row cache: name â†’ AdapterRow widget
        self._adapter_rows: dict[str, AdapterRow] = {}

        self._setup_ui()

    # UI construction 

    def _setup_ui(self):
        # Root layout â€” the scroll area fills all remaining space
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Page header
        header_widget = QWidget()
        header_widget.setObjectName("PageHeader")
        header_widget.setFixedHeight(72)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(28, 20, 28, 8)
        header_layout.setSpacing(2)

        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Real-time overview of your network activity")
        subtitle.setObjectName("PageSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_widget)
        root.addSpacing(20)
        
        #Scroll area (all cards below header) 
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 8, 28, 28)
        layout.setSpacing(16)

        #Row 1: four speed KPI cards
        row1 = QGridLayout()
        row1.setSpacing(12)
        for col in range(4):
            row1.setColumnStretch(col, 1)   # equal-width columns

        self._card_dl = SpeedCard(
            label="Download",
            icon_char="↓",
            icon_bg=COLORS["blue"],
            value_color=COLORS["blue"],
            spark_color=COLORS["blue"],
        )
        self._card_ul = SpeedCard(
            label="Upload",
            icon_char="↑",
            icon_bg=COLORS["purple"],
            value_color=COLORS["purple"],
            spark_color=COLORS["purple"],
        )
        self._card_conn = SpeedCard(
            label="Active Connections",
            icon_char="🟢",
            icon_bg=COLORS["teal"],
            value_color=COLORS["teal"],
            spark_color=COLORS["teal"],
        )
        self._card_ping = SpeedCard(
            label="Ping",
            icon_char="🚦",
            icon_bg=COLORS["orange"],
            value_color=COLORS["orange"],
            spark_color=COLORS["orange"],
        )

        row1.addWidget(self._card_dl,   0, 0)
        row1.addWidget(self._card_ul,   0, 1)
        row1.addWidget(self._card_conn, 0, 2)
        row1.addWidget(self._card_ping, 0, 3)
        layout.addLayout(row1)

        # Row 2: three usage cards 
        row2 = QGridLayout()
        row2.setSpacing(12)
        for col in range(3):
            row2.setColumnStretch(col, 1)

        self._card_today  = UsageCard("Today (Total)",  "📆",
                                      COLORS["blue"],   COLORS["blue"])
        self._card_month  = UsageCard("This Month",     "📅",
                                      COLORS["green"],  COLORS["green"])
        self._card_last30 = UsageCard("Last 24 Hours",   "🕖",
                                      COLORS["purple"], COLORS["purple"])

        row2.addWidget(self._card_today,  0, 0)
        row2.addWidget(self._card_month,  0, 1)
        row2.addWidget(self._card_last30, 0, 2)
        layout.addLayout(row2)

        # Row 3: live graph (left, 3/5) + adapters (right, 2/5) 
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        self._graph_container = self._build_graph_card()
        self._adapters_card   = self._build_adapters_card()

        row3.addWidget(self._graph_container, 3)
        row3.addWidget(self._adapters_card,   2)
        layout.addLayout(row3)

        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    # Graph card 

    def _build_graph_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        # Card header
        hdr = QHBoxLayout()
        title_lbl = QLabel("Live Bandwidth")
        title_lbl.setObjectName("SectionTitle")
        sub_lbl = QLabel("Last 60 seconds")
        sub_lbl.setObjectName("SectionMeta")
        sub_lbl.setStyleSheet(f"color: {COLORS['label_3']}; font-size: 12px;")

        hdr.addWidget(title_lbl)
        hdr.addWidget(sub_lbl)
        hdr.addStretch()
        outer.addLayout(hdr)

        # Legend row
        leg = QHBoxLayout()
        leg.setSpacing(16)
        leg.setContentsMargins(0, 0, 0, 0)
        for color, label in [
            (COLORS["blue"],   "Download (MB/s)"),
            (COLORS["purple"], "Upload (MB/s)"),
        ]:
            dot = QLabel("⇵")
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['label_2']}; font-size: 12px;")
            leg.addWidget(dot)
            leg.addWidget(lbl)
        leg.addStretch()
        outer.addLayout(leg)

        # pyqtgraph plot
        self._pw = pg.PlotWidget()
        self._pw.setBackground(COLORS["surface_1"])
        self._pw.setMinimumHeight(200)
        self._pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        plot = self._pw.getPlotItem()
        plot.showGrid(x=False, y=True, alpha=0.12)
        plot.getAxis("left").setLabel("MB/s", color=COLORS["label_2"])
        plot.getAxis("bottom").setLabel("seconds ago", color=COLORS["label_2"])
        plot.getAxis("left").setStyle(tickFont=_small_font())
        plot.getAxis("bottom").setStyle(tickFont=_small_font())
        plot.getAxis("left").setPen(pg.mkPen(COLORS["border_card"]))
        plot.getAxis("bottom").setPen(pg.mkPen(COLORS["border_card"]))
        self._pw.setXRange(0, MAX_SAMPLES, padding=0)
        self._pw.setMouseEnabled(x=False, y=False)

        self._curve_dl = self._pw.plot(
            self._x,
            [v / 1024 / 1024 for v in self._recv_buf],
            pen=pg.mkPen(color=COLORS["blue"], width=2),
            fillLevel=0,
            brush=pg.mkBrush(color=(*_hex_to_rgb(COLORS["blue"]), 30)),
        )
        self._curve_ul = self._pw.plot(
            self._x,
            [v / 1024 / 1024 for v in self._sent_buf],
            pen=pg.mkPen(color=COLORS["purple"], width=2),
            fillLevel=0,
            brush=pg.mkBrush(color=(*_hex_to_rgb(COLORS["purple"]), 30)),
        )
        outer.addWidget(self._pw)
        return card

    # Adapters card 

    def _build_adapters_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(8)

        hdr = QHBoxLayout()
        title_lbl = QLabel("Network Adapters")
        title_lbl.setObjectName("SectionTitle")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        outer.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {COLORS['border_card']};")
        outer.addWidget(div)

        # Scrollable adapter list
        self._adapters_scroll = QScrollArea()
        self._adapters_scroll.setWidgetResizable(True)
        self._adapters_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._adapters_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._adapters_inner = QWidget()
        self._adapters_layout = QVBoxLayout(self._adapters_inner)
        self._adapters_layout.setContentsMargins(0, 0, 0, 0)
        self._adapters_layout.setSpacing(0)
        self._adapters_layout.addStretch()

        self._adapters_scroll.setWidget(self._adapters_inner)
        outer.addWidget(self._adapters_scroll, 1)
        return card

    # Data update slots 

    def on_sample(self, sample: BandwidthSample):
        """Update live graph only (called every second)."""
        self._recv_buf.append(sample.recv_speed)
        self._sent_buf.append(sample.sent_speed)

        dl_mb = [v / 1024 / 1024 for v in self._recv_buf]
        ul_mb = [v / 1024 / 1024 for v in self._sent_buf]
        self._curve_dl.setData(self._x, dl_mb)
        self._curve_ul.setData(self._x, ul_mb)

        # Update speed card sparklines
        dl_val, dl_unit = fmt_speed(sample.recv_speed)
        ul_val, ul_unit = fmt_speed(sample.sent_speed)
        self._card_dl.update_value(dl_val, dl_unit, sample.recv_speed)
        self._card_ul.update_value(ul_val, ul_unit, sample.sent_speed)

    def on_stats(self, stats: DashboardStats):
        """Update all KPI cards, usage cards and adapter list."""

        # Connection card (no sparkline data from stats, reuse 0)
        self._card_conn.update_value(str(stats.active_connections), "connections", 0.0)

        # Ping card
        ping = get_ping()


        if ping is not None:
            self._card_ping.update_value(str(ping), "ms", float(ping))
        else:
            self._card_ping.update_value("--", "ms", 0)

        # Usage cards
        self._card_today.update_data(stats.today_recv, stats.today_sent)
        self._card_month.update_data(stats.month_recv, stats.month_sent)
        self._card_last30.update_data(stats.last30_recv, stats.last30_sent)

        # Adapters
        self._refresh_adapters(stats)

    def _refresh_adapters(self, stats: DashboardStats):
        """Update adapter rows, creating new ones as adapters appear."""
        seen: set[str] = set()
        for a in stats.adapters:
            seen.add(a.name)
            if a.name not in self._adapter_rows:
                row = AdapterRow()
                self._adapter_rows[a.name] = row
                # Insert before the trailing stretch
                idx = self._adapters_layout.count() - 1
                self._adapters_layout.insertWidget(idx, row)

                # Add a thin divider after the row
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setStyleSheet(f"color: {COLORS['border_card']}; max-height: 1px;")
                self._adapters_layout.insertWidget(idx + 1, div)

            self._adapter_rows[a.name].set_adapter(
                a.name, a.is_up, a.speed_mbps, a.bytes_recv, a.bytes_sent
            )

        # Hide rows for adapters that disappeared
        for name, row in self._adapter_rows.items():
            row.setVisible(name in seen)


# Helpers

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B)."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _small_font():
    from PyQt6.QtGui import QFont
    f = QFont("Segoe UI", 9)
    return f


