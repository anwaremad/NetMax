"""
ui/settings_page.py
Settings page: autostart, tray, quota alerts, data management, export.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QFileDialog, QMessageBox, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import COLORS
from ui.widgets import SectionHeader, HDivider
from database.db_manager import DatabaseManager
from services.export_service import ExportService
from services.system_service import set_autostart, is_autostart_enabled
from models.data_models import AlertConfig


class SettingsPage(QWidget):
    """User preferences and system integration settings."""

    sig_alert_config_changed = pyqtSignal(object)   # AlertConfig

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._export_svc = ExportService(db)
        self._setup_ui()
        self._load_settings()

    # â”€â”€ UI construction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        root.addSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(8)

        # â”€â”€ System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        #layout.addWidget(SectionHeader("System"))
        #layout.addWidget(HDivider())

        self._chk_autostart = QCheckBox("Start Net Max with Windows")
        self._chk_autostart.stateChanged.connect(self._on_autostart_changed)
        layout.addWidget(self._chk_autostart)

        self._chk_tray = QCheckBox("Minimize to system tray instead of taskbar")
        self._chk_tray.stateChanged.connect(lambda s: self._save_setting("minimize_to_tray", "1" if s else "0"))
        layout.addWidget(self._chk_tray)

        layout.addSpacing(16)

        # â”€â”€ Update interval â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        layout.addWidget(SectionHeader("Monitoring"))
        layout.addWidget(HDivider())

        row_interval = QHBoxLayout()
        lbl_interval = QLabel("UI refresh interval:")
        lbl_interval.setFixedWidth(140)
        self._spin_interval = QSpinBox()
        self._spin_interval.setRange(1, 10)
        self._spin_interval.setSuffix(" seconds")
        self._spin_interval.setValue(1)
        self._spin_interval.valueChanged.connect(lambda v: self._save_setting("ui_interval", str(v)))
        row_interval.addWidget(lbl_interval)
        row_interval.addWidget(self._spin_interval)
        row_interval.addStretch()
        layout.addLayout(row_interval)
        layout.addSpacing(16)

        # â”€â”€ Data quota â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        layout.addWidget(SectionHeader("Monthly Data Quota Alerts"))
        layout.addWidget(HDivider())

        row_quota = QHBoxLayout()
        lbl_quota = QLabel("Monthly quota limit (GB):")
        lbl_quota.setFixedWidth(220)
        self._spin_quota = QDoubleSpinBox()
        self._spin_quota.setRange(0, 10000)
        self._spin_quota.setDecimals(1)
        self._spin_quota.setSuffix(" GB")
        self._spin_quota.setSpecialValueText("Disabled")
        self._spin_quota.setValue(0)
        self._spin_quota.valueChanged.connect(self._on_quota_changed)
        row_quota.addWidget(lbl_quota)
        row_quota.addWidget(self._spin_quota)
        row_quota.addStretch()
        layout.addLayout(row_quota)

        row_warn = QHBoxLayout()
        lbl_warn = QLabel("Warning threshold (%):")
        lbl_warn.setFixedWidth(220)
        self._spin_warn = QDoubleSpinBox()
        self._spin_warn.setRange(1, 99)
        self._spin_warn.setDecimals(0)
        self._spin_warn.setSuffix(" %")
        self._spin_warn.setValue(80)
        self._spin_warn.valueChanged.connect(self._on_quota_changed)
        row_warn.addWidget(lbl_warn)
        row_warn.addWidget(self._spin_warn)
        row_warn.addStretch()
        layout.addLayout(row_warn)

        row_crit = QHBoxLayout()
        lbl_crit = QLabel("Critical threshold (%):")
        lbl_crit.setFixedWidth(220)
        self._spin_crit = QDoubleSpinBox()
        self._spin_crit.setRange(1, 100)
        self._spin_crit.setDecimals(0)
        self._spin_crit.setSuffix(" %")
        self._spin_crit.setValue(95)
        self._spin_crit.valueChanged.connect(self._on_quota_changed)
        row_crit.addWidget(lbl_crit)
        row_crit.addWidget(self._spin_crit)
        row_crit.addStretch()
        layout.addLayout(row_crit)

        layout.addSpacing(16)

        # â”€â”€ Export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        layout.addWidget(SectionHeader("Export Data"))
        layout.addWidget(HDivider())

        export_row = QHBoxLayout()
        export_row.setSpacing(10)

        btn_export_daily = QPushButton("Export Daily Totals (CSV)")
        btn_export_daily.setObjectName("PrimaryBtn")
        btn_export_daily.clicked.connect(self._export_daily)

        btn_export_apps = QPushButton("Export App Usage Today (CSV)")
        btn_export_apps.setObjectName("PrimaryBtn")
        btn_export_apps.clicked.connect(self._export_apps)

        export_row.addWidget(btn_export_daily)
        export_row.addWidget(btn_export_apps)
        export_row.addStretch()
        layout.addLayout(export_row)

        layout.addSpacing(16)

        # â”€â”€ Danger zone â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        layout.addWidget(SectionHeader("Data Management"))
        layout.addWidget(HDivider())

        danger_row = QHBoxLayout()
        btn_reset = QPushButton("Reset All Statistics")
        btn_reset.setObjectName("DangerBtn")
        btn_reset.setFixedWidth(200)
        btn_reset.clicked.connect(self._confirm_reset)
        danger_row.addWidget(btn_reset)
        danger_row.addStretch()
        layout.addLayout(danger_row)

        lbl_reset_note = QLabel("This will permanently delete all recorded bandwidth data.")
        lbl_reset_note.setStyleSheet(f"color: {COLORS['label_2']}; font-size: 11px;")
        layout.addWidget(lbl_reset_note)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    # â”€â”€ Load / save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _load_settings(self):
        self._chk_autostart.setChecked(is_autostart_enabled())
        self._chk_tray.setChecked(self._db.get_setting("minimize_to_tray", "0") == "1")
        self._spin_interval.setValue(int(self._db.get_setting("ui_interval", "1")))
        try:
            quota = float(self._db.get_setting("monthly_quota_gb", "0"))
            warn  = float(self._db.get_setting("warn_pct", "80"))
            crit  = float(self._db.get_setting("critical_pct", "95"))
        except ValueError:
            quota, warn, crit = 0.0, 80.0, 95.0
        self._spin_quota.setValue(quota)
        self._spin_warn.setValue(warn)
        self._spin_crit.setValue(crit)

    def _save_setting(self, key: str, value: str):
        self._db.set_setting(key, value)

    def _on_autostart_changed(self, state: int):
        enabled = state == Qt.CheckState.Checked.value
        set_autostart(enabled)

    def _on_quota_changed(self, _):
        cfg = AlertConfig(
            monthly_quota_gb=self._spin_quota.value(),
            warn_pct=self._spin_warn.value(),
            critical_pct=self._spin_crit.value(),
        )
        self._save_setting("monthly_quota_gb", str(cfg.monthly_quota_gb))
        self._save_setting("warn_pct", str(cfg.warn_pct))
        self._save_setting("critical_pct", str(cfg.critical_pct))
        self.sig_alert_config_changed.emit(cfg)

    # â”€â”€ Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _export_daily(self):
        try:
            path = self._export_svc.export_daily()
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _export_apps(self):
        try:
            path = self._export_svc.export_apps_today()
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _confirm_reset(self):
        reply = QMessageBox.question(
            self, "Reset Statistics",
            "Are you sure you want to delete all usage data?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.reset_all()
            QMessageBox.information(self, "Done", "All statistics have been reset.")


