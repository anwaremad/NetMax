"""
ui/apps_page.py
Applications page: per-process network usage table with search + sort.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QColor

from ui.styles import COLORS
from ui.widgets import fmt_bytes, SectionHeader
from models.data_models import AppTrafficRecord
from database.db_manager import DatabaseManager
from typing import List, Dict


class AppsPage(QWidget):
    """Shows a sortable, searchable table of per-application network usage."""

    # Column indices
    COL_NAME   = 0
    COL_PID    = 1
    COL_RECV   = 2
    COL_SENT   = 3
    COL_TOTAL  = 4
    COL_PATH   = 5

    COLUMNS = ["Application", "PID", "Downloaded", "Uploaded", "Total", "Executable Path"]

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        # Accumulate totals per exe path across updates
        self._totals: Dict[str, Dict] = {}
        self._setup_ui()

    # â”€â”€ UI construction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(0)

        title = QLabel("Applications")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addSpacing(20)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by application name or path")
        self._search.textChanged.connect(self._apply_filter)
        self._search.setMaximumWidth(400)

        self._lbl_count = QLabel("0 applications")
        self._lbl_count.setStyleSheet(f"color: {COLORS['label_2']};")

        search_row.addWidget(self._search)
        search_row.addWidget(self._lbl_count)
        search_row.addStretch()
        root.addSpacing(8)
        root.addLayout(search_row)
        root.addSpacing(12)

        # Table
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_NAME,  QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_PID,   QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_RECV,  QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_SENT,  QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_TOTAL, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_PATH,  QHeaderView.ResizeMode.Stretch)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # Default sort: Total descending
        self._table.sortByColumn(self.COL_TOTAL, Qt.SortOrder.DescendingOrder)

        root.addWidget(self._table)

        # Note
        note = QLabel(
            "Per-app byte counts are derived from process I/O counters. "
            "Admin privileges improve accuracy."
        )
        note.setStyleSheet(f"color: {COLORS['label_2']}; font-size: 11px;")
        note.setWordWrap(True)
        root.addSpacing(6)
        root.addWidget(note)

    # â”€â”€ Data update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_apps_updated(self, apps: List[AppTrafficRecord]):
        """Called from the main window when new app data arrives."""
        # Accumulate into running totals keyed by exe path
        for a in apps:
            key = a.exe_path
            if key not in self._totals:
                self._totals[key] = {
                    "app_name": a.app_name,
                    "pid": a.pid,
                    "exe_path": a.exe_path,
                    "bytes_recv": 0,
                    "bytes_sent": 0,
                }
            self._totals[key]["bytes_recv"] += a.bytes_recv
            self._totals[key]["bytes_sent"] += a.bytes_sent
            self._totals[key]["pid"] = a.pid  # Update PID (may change)
            self._totals[key]["app_name"] = a.app_name

        self._refresh_table()

    def refresh_from_db(self):
        """Load today's totals from the DB (called on page switch or restart)."""
        rows = self._db.get_app_totals_today()
        for row in rows:
            key = row["exe_path"]
            self._totals[key] = {
                "app_name": row["app_name"],
                "pid": 0,
                "exe_path": row["exe_path"],
                "bytes_recv": row["total_recv"],
                "bytes_sent": row["total_sent"],
            }
        self._refresh_table()

    def _refresh_table(self):
        filter_text = self._search.text().lower()
        records = [
            r for r in self._totals.values()
            if not filter_text
            or filter_text in r["app_name"].lower()
            or filter_text in r["exe_path"].lower()
        ]

        # Compute max total for proportional colour intensity
        max_total = max((r["bytes_recv"] + r["bytes_sent"] for r in records), default=1)

        # Temporarily disable sorting to avoid mid-fill re-sort
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(records))

        for row_idx, r in enumerate(records):
            total = r["bytes_recv"] + r["bytes_sent"]
            recv_v, recv_u = fmt_bytes(r["bytes_recv"])
            sent_v, sent_u = fmt_bytes(r["bytes_sent"])
            tot_v,  tot_u  = fmt_bytes(total)

            items = [
                (self.COL_NAME,  r["app_name"]),
                (self.COL_PID,   str(r["pid"]) if r["pid"] else "--"),
                (self.COL_RECV,  f"{recv_v} {recv_u}"),
                (self.COL_SENT,  f"{sent_v} {sent_u}"),
                (self.COL_TOTAL, f"{tot_v} {tot_u}"),
                (self.COL_PATH,  r["exe_path"]),
            ]

            for col, text in items:
                item = SortableTableItem(text)
                # Store raw bytes for numeric sorting on traffic columns
                if col in (self.COL_RECV, self.COL_SENT, self.COL_TOTAL):
                    raw = {
                        self.COL_RECV:  r["bytes_recv"],
                        self.COL_SENT:  r["bytes_sent"],
                        self.COL_TOTAL: total,
                    }[col]
                    item.setData(Qt.ItemDataRole.UserRole, raw)
                item.setToolTip(text)
                self._table.setItem(row_idx, col, item)

        self._table.setSortingEnabled(True)
        self._lbl_count.setText(f"{len(records)} application{'s' if len(records) != 1 else ''}")

    def _apply_filter(self, _text: str):
        self._refresh_table()


class SortableTableItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically when UserRole data is set."""

    def __lt__(self, other: "SortableTableItem") -> bool:
        my_data = self.data(Qt.ItemDataRole.UserRole)
        other_data = other.data(Qt.ItemDataRole.UserRole)
        if my_data is not None and other_data is not None:
            return my_data < other_data
        return self.text() < other.text()


