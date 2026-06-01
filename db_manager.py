"""
database/db_manager.py
SQLite database manager for Net Max.
Handles schema creation, data insertion, and queries for network usage statistics.
"""
import os
from pathlib import Path
import sqlite3
import threading
import time
from datetime import datetime, date
from typing import Optional, List, Dict, Any


# ── Schema SQL ────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

-- Stores per-second snapshots of total bandwidth
CREATE TABLE IF NOT EXISTS bandwidth_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL    NOT NULL,
    bytes_recv  INTEGER NOT NULL DEFAULT 0,
    bytes_sent  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_bs_timestamp ON bandwidth_snapshots(timestamp);

-- Stores per-application traffic rolled up every minute
CREATE TABLE IF NOT EXISTS app_traffic (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL    NOT NULL,
    exe_path    TEXT    NOT NULL,
    app_name    TEXT    NOT NULL,
    pid         INTEGER NOT NULL DEFAULT 0,
    bytes_recv  INTEGER NOT NULL DEFAULT 0,
    bytes_sent  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_at_timestamp ON app_traffic(timestamp);
CREATE INDEX IF NOT EXISTS idx_at_exe       ON app_traffic(exe_path);

-- Daily aggregated totals
CREATE TABLE IF NOT EXISTS daily_totals (
    day_date    TEXT    PRIMARY KEY,   -- 'YYYY-MM-DD'
    bytes_recv  INTEGER NOT NULL DEFAULT 0,
    bytes_sent  INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL    NOT NULL
);

-- Monthly aggregated totals
CREATE TABLE IF NOT EXISTS monthly_totals (
    month_key   TEXT    PRIMARY KEY,   -- 'YYYY-MM'
    bytes_recv  INTEGER NOT NULL DEFAULT 0,
    bytes_sent  INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL    NOT NULL
);

-- Per-app daily aggregated totals
CREATE TABLE IF NOT EXISTS app_daily_totals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    day_date    TEXT    NOT NULL,
    exe_path    TEXT    NOT NULL,
    app_name    TEXT    NOT NULL,
    bytes_recv  INTEGER NOT NULL DEFAULT 0,
    bytes_sent  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(day_date, exe_path)
);
CREATE INDEX IF NOT EXISTS idx_adt_day ON app_daily_totals(day_date);

-- User settings (key-value store)
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""


class DatabaseManager:
    """Thread-safe SQLite database manager with WAL mode for concurrent access."""

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        if db_path is None:
            app_dir = os.path.join(
                os.environ["APPDATA"],
                "Net Max"
            )

            os.makedirs(app_dir, exist_ok=True)

            db_path = os.path.join(app_dir, "netscope.db")

        self._db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()

        self._init_schema()
        self._initialized = True

    # ── Connection management ─────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection (creates one if needed)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self):
        conn = sqlite3.connect(self._db_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

    # ── Bandwidth snapshots ───────────────────────────────────────────────────

    def insert_snapshot(self, bytes_recv: int, bytes_sent: int):
        

        ts = time.time()

        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO bandwidth_snapshots (timestamp, bytes_recv, bytes_sent) VALUES (?,?,?)",
                (ts, bytes_recv, bytes_sent),
            )
            conn.commit()

    def get_snapshots_since(self, since_ts: float) -> List[sqlite3.Row]:
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM bandwidth_snapshots WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since_ts,),
        ).fetchall()

    # ── App traffic ───────────────────────────────────────────────────────────

    def upsert_app_traffic(self, records: List[Dict[str, Any]]):
        """Bulk-upsert per-app traffic records."""
        ts = time.time()
        with self._write_lock:
            conn = self._get_conn()
            conn.executemany(
                """INSERT INTO app_traffic
                   (timestamp, exe_path, app_name, pid, bytes_recv, bytes_sent)
                   VALUES (:ts, :exe_path, :app_name, :pid, :bytes_recv, :bytes_sent)""",
                [{**r, "ts": ts} for r in records],
            )
            conn.commit()

    def get_app_totals_today(self) -> List[sqlite3.Row]:
        """Return per-app totals since midnight today."""
        midnight = datetime.combine(date.today(), datetime.min.time()).timestamp()
        conn = self._get_conn()
        return conn.execute(
            """SELECT app_name, exe_path,
                      SUM(bytes_recv) AS total_recv,
                      SUM(bytes_sent) AS total_sent,
                      SUM(bytes_recv + bytes_sent) AS total_traffic
               FROM app_traffic
               WHERE timestamp >= ?
               GROUP BY exe_path
               ORDER BY total_traffic DESC""",
            (midnight,),
        ).fetchall()

    # ── Daily / monthly aggregation ───────────────────────────────────────────

    def aggregate_today(self, bytes_recv: int, bytes_sent: int):
        """Update the daily total for today."""
        day = date.today().isoformat()
        now = time.time()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO daily_totals (day_date, bytes_recv, bytes_sent, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(day_date) DO UPDATE SET
                       bytes_recv=excluded.bytes_recv,
                       bytes_sent=excluded.bytes_sent,
                       updated_at=excluded.updated_at""",
                (day, bytes_recv, bytes_sent, now),
            )
            conn.commit()

    def aggregate_month(self, bytes_recv: int, bytes_sent: int):
        """Update the monthly total for the current month."""
        month = date.today().strftime("%Y-%m")
        now = time.time()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO monthly_totals (month_key, bytes_recv, bytes_sent, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(month_key) DO UPDATE SET
                       bytes_recv=excluded.bytes_recv,
                       bytes_sent=excluded.bytes_sent,
                       updated_at=excluded.updated_at""",
                (month, bytes_recv, bytes_sent, now),
            )
            conn.commit()

    def get_daily_totals(self, days: int = 30) -> List[sqlite3.Row]:
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM daily_totals ORDER BY day_date DESC LIMIT ?", (days,)
        ).fetchall()

    def get_today_totals(self) -> Optional[sqlite3.Row]:
        day = date.today().isoformat()
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM daily_totals WHERE day_date = ?", (day,)
        ).fetchone()

    def get_month_totals(self) -> Optional[sqlite3.Row]:
        month = date.today().strftime("%Y-%m")
        conn = self._get_conn()
        return conn.execute(
            "SELECT * FROM monthly_totals WHERE month_key = ?", (month,)
        ).fetchone()

    def get_last_24_hours_total(self):
        cutoff = time.time() - (24 * 60 * 60)

        conn = self._get_conn()
        row = conn.execute(
        """
        SELECT
            COALESCE(SUM(bytes_recv),0) AS recv,
            COALESCE(SUM(bytes_sent),0) AS sent
        FROM bandwidth_snapshots
        WHERE timestamp >= ?
        """,
        (cutoff,)
    ).fetchone()

        return {
        "bytes_recv": row["recv"],
        "bytes_sent": row["sent"]
    }

    # ── Settings ──────────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()

    # ── Maintenance ───────────────────────────────────────────────────────────

    def prune_old_snapshots(self, keep_days: int = 7):
        """Delete raw snapshots older than `keep_days` to keep the DB small."""
        cutoff = time.time() - keep_days * 86400
        with self._write_lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM bandwidth_snapshots WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM app_traffic WHERE timestamp < ?", (cutoff,))
            conn.commit()

    def reset_all(self):
        """Wipe all usage data (keep settings)."""
        with self._write_lock:
            conn = self._get_conn()
            conn.executescript(
                """DELETE FROM bandwidth_snapshots;
                   DELETE FROM app_traffic;
                   DELETE FROM daily_totals;
                   DELETE FROM monthly_totals;
                   DELETE FROM app_daily_totals;"""
            )
            conn.commit()
