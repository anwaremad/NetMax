"""
services/export_service.py
Exports usage statistics to CSV files.
"""

import csv
import os
from datetime import datetime
from typing import List

from database.db_manager import DatabaseManager


class ExportService:
    """Generates CSV exports of usage history."""

    def __init__(self, db: DatabaseManager, export_dir: str = None):
        self._db = db

        if export_dir is None:
            app_dir = os.path.join(
                os.environ["APPDATA"],
                "Net Max"
            )

            os.makedirs(app_dir, exist_ok=True)

            export_dir = os.path.join(app_dir, "exports")

        self._export_dir = export_dir
        os.makedirs(self._export_dir, exist_ok=True)
    def export_daily(self, days: int = 30) -> str:
        """Export daily totals to CSV. Returns the file path."""
        rows = self._db.get_daily_totals(days)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._export_dir, f"daily_totals_{ts}.csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Downloaded (MB)", "Uploaded (MB)", "Total (MB)"])
            for row in rows:
                recv_mb = row["bytes_recv"] / (1024 * 1024)
                sent_mb = row["bytes_sent"] / (1024 * 1024)
                total_mb = recv_mb + sent_mb
                writer.writerow([row["day_date"], f"{recv_mb:.2f}", f"{sent_mb:.2f}", f"{total_mb:.2f}"])

        return path

    def export_apps_today(self) -> str:
        """Export per-app today stats to CSV. Returns the file path."""
        rows = self._db.get_app_totals_today()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._export_dir, f"app_usage_{ts}.csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["App Name", "Executable", "Downloaded (MB)", "Uploaded (MB)", "Total (MB)"])
            for row in rows:
                recv_mb = row["total_recv"] / (1024 * 1024)
                sent_mb = row["total_sent"] / (1024 * 1024)
                total_mb = recv_mb + sent_mb
                writer.writerow([
                    row["app_name"],
                    row["exe_path"],
                    f"{recv_mb:.2f}",
                    f"{sent_mb:.2f}",
                    f"{total_mb:.2f}",
                ])

        return path
