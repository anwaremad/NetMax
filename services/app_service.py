"""
services/app_service.py
Application service layer.

Bridges the NetworkMonitor (raw data) with the DatabaseManager (persistence)
and the AlertService (quota checking). Emits PyQt6 signals consumed by the UI.
"""

import time
import threading
from datetime import date
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal

from monitoring.network_monitor import NetworkMonitor
from database.db_manager import DatabaseManager
from models.data_models import (
    BandwidthSample,
    AppTrafficRecord,
    DashboardStats,
    AlertConfig,
)


class AppService(QObject):
    """
    Central service singleton.  All UI pages connect to its signals.
    Runs safely from any thread via Qt's queued signal dispatch.
    """

    # ── Signals ───────────────────────────────────────────────────────────────
    sig_sample = pyqtSignal(object)      # BandwidthSample
    sig_apps_updated = pyqtSignal(list)  # List[AppTrafficRecord]
    sig_stats_updated = pyqtSignal(object)  # DashboardStats
    sig_alert = pyqtSignal(str, str)     # (title, message)

    # How often to flush aggregated totals to DB (seconds)
    FLUSH_INTERVAL: int = 60

    def __init__(self, db: DatabaseManager, monitor: NetworkMonitor, parent=None):
        super().__init__(parent)
        self._db = db
        self._monitor = monitor
        self._alert_cfg: AlertConfig = self._load_alert_config()

        # Track pending totals for DB flush
        self._flush_recv: int = 0
        self._flush_sent: int = 0
        self._last_flush: float = time.time()
        self._flush_lock = threading.Lock()

        # Today date for midnight rollover detection
        self._today: date = date.today()

        # Wire monitor callbacks → Qt signals
        monitor.on_sample(self._on_sample)
        monitor.on_apps(self._on_apps)
        monitor.on_stats(self._on_stats)

    # ── Start / stop ──────────────────────────────────────────────────────────

    def start(self):
        self._monitor.start()

    def stop(self):
        self._monitor.stop()
        self._flush_to_db()  # Final flush on exit

    # ── Public helpers ────────────────────────────────────────────────────────

    def update_alert_config(self, cfg: AlertConfig):
        self._alert_cfg = cfg
        self._db.set_setting("monthly_quota_gb", str(cfg.monthly_quota_gb))
        self._db.set_setting("warn_pct", str(cfg.warn_pct))
        self._db.set_setting("critical_pct", str(cfg.critical_pct))

    def get_alert_config(self) -> AlertConfig:
        return self._alert_cfg

    # ── Monitor callbacks (called on monitor thread) ──────────────────────────

    def _on_sample(self, sample: BandwidthSample):
        self._check_midnight_rollover()

        with self._flush_lock:
            self._flush_recv += sample.bytes_recv
            self._flush_sent += sample.bytes_sent

        self._maybe_flush()
        self.sig_sample.emit(sample)

    def _on_apps(self, apps: List[AppTrafficRecord]):
        # Persist to DB (async insert)
        if apps:
            records = [
                {
                    "exe_path": a.exe_path,
                    "app_name": a.app_name,
                    "pid": a.pid,
                    "bytes_recv": a.bytes_recv,
                    "bytes_sent": a.bytes_sent,
                }
                for a in apps
                if a.total_bytes > 0
            ]
            if records:
                self._db.upsert_app_traffic(records)

        self.sig_apps_updated.emit(apps)

    def _on_stats(self, stats: DashboardStats):
        # Inject DB-backed today/month totals (more accurate after restart)
        today_row = self._db.get_today_totals()
        month_row = self._db.get_month_totals()
        last24 = self._db.get_last_24_hours_total()

        if today_row:
            stats.today_recv = today_row["bytes_recv"] + self._flush_recv
            stats.today_sent = today_row["bytes_sent"] + self._flush_sent

        if month_row:
            stats.month_recv = month_row["bytes_recv"]
            stats.month_sent = month_row["bytes_sent"]

        stats.last30_recv = last24["bytes_recv"]
        stats.last30_sent = last24["bytes_sent"]

        self._check_quota_alert(stats)
        self.sig_stats_updated.emit(stats)

    # ── DB flush ──────────────────────────────────────────────────────────────

    def _maybe_flush(self):
        if time.time() - self._last_flush < self.FLUSH_INTERVAL:
            return
        self._flush_to_db()

    def _flush_to_db(self):
        with self._flush_lock:
            recv = self._flush_recv
            sent = self._flush_sent
            self._flush_recv = 0
            self._flush_sent = 0

        if recv == 0 and sent == 0:
            return

        # Add to today's running total from DB
        today_row = self._db.get_today_totals()
        base_recv = today_row["bytes_recv"] if today_row else 0
        base_sent = today_row["bytes_sent"] if today_row else 0

        self._db.aggregate_today(base_recv + recv, base_sent + sent)

        # Also update month
        month_row = self._db.get_month_totals()
        m_recv = (month_row["bytes_recv"] if month_row else 0) + recv
        m_sent = (month_row["bytes_sent"] if month_row else 0) + sent

        self._db.aggregate_month(m_recv, m_sent)

        # Save snapshot for Last 24 Hours statistics
        self._db.insert_snapshot(recv, sent)

        self._last_flush = time.time()

        # Prune old raw snapshots weekly
        self._db.prune_old_snapshots(keep_days=7)

    # ── Midnight rollover ─────────────────────────────────────────────────────

    def _check_midnight_rollover(self):
        today = date.today()
        if today != self._today:
            # New day: flush pending data for the previous day first
            self._flush_to_db()
            self._today = today
            self._monitor.reset_today()

    # ── Alert checking ────────────────────────────────────────────────────────

    def _check_quota_alert(self, stats: DashboardStats):
        cfg = self._alert_cfg
        if cfg.monthly_quota_gb <= 0:
            return

        quota_bytes = cfg.monthly_quota_gb * 1024 ** 3
        used = stats.month_recv + stats.month_sent
        pct = (used / quota_bytes) * 100 if quota_bytes > 0 else 0

        if pct >= cfg.critical_pct and not cfg.notified_critical:
            cfg.notified_critical = True
            self.sig_alert.emit(
                "⚠ Critical Data Usage",
                f"You have used {pct:.1f}% of your monthly quota "
                f"({_fmt_bytes(used)} / {cfg.monthly_quota_gb:.1f} GB).",
            )
        elif pct >= cfg.warn_pct and not cfg.notified_warn:
            cfg.notified_warn = True
            self.sig_alert.emit(
                "Data Usage Warning",
                f"You have used {pct:.1f}% of your monthly quota "
                f"({_fmt_bytes(used)} / {cfg.monthly_quota_gb:.1f} GB).",
            )

    # ── Settings load ─────────────────────────────────────────────────────────

    def _load_alert_config(self) -> AlertConfig:
        try:
            quota = float(self._db.get_setting("monthly_quota_gb", "0"))
            warn = float(self._db.get_setting("warn_pct", "80"))
            crit = float(self._db.get_setting("critical_pct", "95"))
        except ValueError:
            quota, warn, crit = 0.0, 80.0, 95.0
        return AlertConfig(
            monthly_quota_gb=quota,
            warn_pct=warn,
            critical_pct=crit,
        )


def _fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} PB"
