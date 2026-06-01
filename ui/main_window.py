"""
ui/main_window.py
Net Max â€“ Main application window.

Changes vs. old version
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â€¢ App renamed to "Net Max" with ⚡ speed icon
â€¢ Sidebar rebuilt as a proper QWidget with logo area, nav section label,
  nav buttons, spacer, status indicator, version label
â€¢ Window title bar shows "Net Max"
â€¢ Sidebar width increased to 220px for breathing room
â€¢ Status indicator at the bottom of the sidebar (green dot + "Active")
â€¢ Tray icon drawn to match the new accent colour
â€¢ All hard-coded strings updated
â€¢ closeEvent now correctly references "Net Max"
"""

from __future__ import annotations

import os
import sys
from unittest import result
from services.update_service import UpdateService

from PyQt6.QtWidgets import QMessageBox

import webbrowser

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QStatusBar, QSystemTrayIcon,
    QMenu, QMessageBox, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QFont,
    QLinearGradient, QPen, QAction,
)

from ui.styles import DARK_THEME, COLORS
from ui.widgets import SidebarButton
from ui.dashboard_page import DashboardPage
from ui.apps_page import AppsPage
from ui.stats_page import StatsPage
from ui.settings_page import SettingsPage

from services.app_service import AppService
from database.db_manager import DatabaseManager
from models.data_models import BandwidthSample, DashboardStats

APP_NAME = "Net Max"
APP_VERSION = "v1.0.1"

# â”€â”€ Navigation items: (emoji, label, page_index) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
NAV_ITEMS = [
    ("📊", "Dashboard",    0),
    ("☰", "Applications", 1),
    ("📈", "Statistics",   2),
    ("⚙️", "Settings",     3),
]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Tray icon
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_tray_icon(size: int = 32) -> QIcon:
    """Render a styled ⚡ icon on a blue rounded background."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background circle
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(COLORS["blue"]))
    p.drawRoundedRect(0, 0, size, size, size * 0.28, size * 0.28)

    # Lightning bolt text
    font = QFont("Segoe UI Emoji", int(size * 0.55))
    p.setFont(font)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(
        px.rect(),
        Qt.AlignmentFlag.AlignCenter,
        "⚡",
    )
    p.end()
    return QIcon(px)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main window
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MainWindow(QMainWindow):
    """Primary application window for Net Max."""

    def __init__(self, service: AppService, db: DatabaseManager):
        super().__init__()
        self._service = service
        self._db = db
        self._minimize_to_tray = db.get_setting("minimize_to_tray", "0") == "1"

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(_make_tray_icon(64))
        self.setMinimumSize(1050, 680)
        self.resize(1280, 820)
        self.setStyleSheet(DARK_THEME)

        self._build_ui()
        self._build_tray()
        self._connect_signals()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start(5000)
        
        QTimer.singleShot(
            5000,
            self._check_updates
)

    def _check_updates(self):
        result = UpdateService.check_for_updates()
        if result["available"]:
                msg = QMessageBox(self)

                msg.setWindowTitle("Update Available")

        msg.setText(
            f"Net Max {result['version']} is available"
        )

        msg.setInformativeText(
            "Do you want to open the download page?"
        )

        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if msg.exec() == QMessageBox.StandardButton.Yes:
                webbrowser.open(result["url"])

    # â”€â”€ Build UI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # â”€â”€ Sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # â”€â”€ Content stack â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentArea")
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)

        self._page_dashboard = DashboardPage()
        self._page_apps      = AppsPage(self._db)
        self._page_stats     = StatsPage(self._db)
        self._page_settings  = SettingsPage(self._db)

        self._stack.addWidget(self._page_dashboard)
        self._stack.addWidget(self._page_apps)
        self._stack.addWidget(self._page_stats)
        self._stack.addWidget(self._page_settings)

        root.addWidget(self._stack, 1)

        # â”€â”€ Status bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._lbl_status = QLabel("Monitoring active")
        self._lbl_status.setStyleSheet(
            f"color: {COLORS['green']}; font-size: 11px; font-weight: 500;"
        )
        sb.addWidget(self._lbl_status)

        self._lbl_db = QLabel()
        self._lbl_db.setStyleSheet(f"color: {COLORS['label_3']}; font-size: 11px;")
        sb.addPermanentWidget(self._lbl_db)

        self._navigate(0)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # â”€â”€ Logo / brand area â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        brand = QWidget()
        brand.setObjectName("BrandLogoArea")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(20, 22, 20, 16)
        brand_layout.setSpacing(10)

        # Speed icon badge (⚡)
        icon_lbl = QLabel("⚡")
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background: {COLORS['blue']};"
            f" border-radius: 10px;"
            f" font-size: 18px;"
            f" color: white;"
        )

        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        name_col.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(APP_NAME)
        name_lbl.setObjectName("BrandName")
        tag_lbl  = QLabel("Network Monitor")
        tag_lbl.setObjectName("BrandTagline")

        name_col.addWidget(name_lbl)
        name_col.addWidget(tag_lbl)

        brand_layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_layout.addLayout(name_col)
        brand_layout.addStretch()

        layout.addWidget(brand)

       # Navigation section label
        nav_label = QLabel("NAVIGATION")
        nav_label.setObjectName("NavSection")
        nav_label.setContentsMargins(14, 0, 0, 0)
        layout.addWidget(nav_label)

        # â”€â”€ Navigation buttons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._nav_buttons: list[SidebarButton] = []
        for icon, label, idx in NAV_ITEMS:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda _checked, i=idx: self._navigate(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # â”€â”€ Status indicator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        status_widget = QWidget()
        status_widget.setObjectName("SidebarStatus")
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(20, 10, 20, 10)
        status_layout.setSpacing(4)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {COLORS['border_card']};")
        div.setFixedHeight(1)
        layout.addWidget(div)

        mon_row = QHBoxLayout()
        mon_row.setSpacing(8)
        dot = QWidget()
        dot.setObjectName("StatusDot")
        dot.setFixedSize(8, 8)
        sl = QLabel("Monitoring")
        sl.setObjectName("StatusLabel")
        mon_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        mon_row.addWidget(sl,  0, Qt.AlignmentFlag.AlignVCenter)
        mon_row.addStretch()
        sv = QLabel("Active")
        sv.setObjectName("StatusValue")
        mon_row.addWidget(sv, 0, Qt.AlignmentFlag.AlignVCenter)
        status_layout.addLayout(mon_row)

        layout.addWidget(status_widget)

        # â”€â”€ Version â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        ver = QLabel(APP_VERSION)
        ver.setObjectName("VersionLabel")
        layout.addWidget(ver)

        return sidebar

    # â”€â”€ Tray â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(_make_tray_icon(32), self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        act_show = QAction(f"Show {APP_NAME}", self)
        act_show.triggered.connect(self._show_from_tray)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self._quit_app)

        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # â”€â”€ Signal wiring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _connect_signals(self):
        svc = self._service
        svc.sig_sample.connect(self._on_sample)
        svc.sig_stats_updated.connect(self._on_stats)
        svc.sig_apps_updated.connect(self._page_apps.on_apps_updated)
        svc.sig_alert.connect(self._show_alert)
        self._page_settings.sig_alert_config_changed.connect(svc.update_alert_config)

    # â”€â”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _navigate(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)
        if index == 1:
            self._page_apps.refresh_from_db()

    # â”€â”€ Slots â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @pyqtSlot(object)
    def _on_sample(self, sample: BandwidthSample):
        self._page_dashboard.on_sample(sample)
        self._page_stats.on_sample(sample)

    @pyqtSlot(object)
    def _on_stats(self, stats: DashboardStats):
        self._page_dashboard.on_stats(stats)

    @pyqtSlot(str, str)
    def _show_alert(self, title: str, message: str):
        if hasattr(self, "_tray"):
            self._tray.showMessage(title, message,
                                   QSystemTrayIcon.MessageIcon.Warning, 8000)
        QMessageBox.warning(self, title, message)

    def _update_status_bar(self):
        try:
            size_kb = os.path.getsize(self._db._db_path) // 1024
            self._lbl_db.setText(f"DB {size_kb} KB  -  {self._db._db_path}")
        except OSError:
            pass

    # â”€â”€ Tray / close â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def closeEvent(self, event):
        if self._minimize_to_tray and hasattr(self, "_tray"):
            event.ignore()
            self.hide()
            self._tray.showMessage(
                APP_NAME,
                "Running in the background. Double-click the tray icon to restore.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            self._quit_app()

    def _quit_app(self):
        self._service.stop()
        if hasattr(self, "_tray"):
            self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()


