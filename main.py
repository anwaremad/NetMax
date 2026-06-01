"""
main.py
Net Max — Application entry point.

Bootstraps all services and launches the PyQt6 GUI.
Run with:  python main.py
"""

import sys
import os

# Ensure the project root is on the path when frozen by PyInstaller
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS          # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

# High-DPI scaling (must be set before QApplication)
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor, QFont, QPainter

from database.db_manager import DatabaseManager
from monitoring.network_monitor import NetworkMonitor
from services.app_service import AppService
from ui.main_window import MainWindow


def _make_splash() -> QSplashScreen:
    """Create a minimal splash screen while the app loads."""
    px = QPixmap(480, 260)
    px.fill(QColor("#0d1117"))
    painter = QPainter(px)
    painter.setPen(QColor("#58a6ff"))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "Net Max")
    painter.setPen(QColor("#8b949e"))
    font2 = QFont("Segoe UI", 11)
    painter.setFont(font2)
    painter.drawText(
        px.rect().adjusted(0, 80, 0, 0),
        Qt.AlignmentFlag.AlignCenter,
        "Starting up…",
    )
    painter.end()
    splash = QSplashScreen(px, Qt.WindowType.WindowStaysOnTopHint)
    return splash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Net Max")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("NetScope")

    # Prevent the app from quitting when the last window closes
    # (we use the tray for background mode)
    app.setQuitOnLastWindowClosed(False)

    # ── Splash ────────────────────────────────────────────────────────────
    splash = _make_splash()
    splash.show()
    app.processEvents()

    # ── Bootstrap services ────────────────────────────────────────────────
    db = DatabaseManager()

    monitor  = NetworkMonitor()
    service  = AppService(db, monitor)

    window   = MainWindow(service, db)

    # ── Start monitoring ──────────────────────────────────────────────────
    service.start()

    # ── Show main window, hide splash ─────────────────────────────────────
    QTimer.singleShot(1200, lambda: (splash.finish(window), window.show()))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
