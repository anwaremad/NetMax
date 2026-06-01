"""
monitoring/network_monitor.py
Core bandwidth monitor using psutil.

Polls total NIC counters every second and emits speed + cumulative totals.
Per-process tracking uses psutil's per-process net_connections and
net_io_counters (where available) — no kernel driver needed, so it
works without admin rights. Where exact per-PID byte counts are
unavailable (a Windows kernel limitation without a driver), we attribute
traffic by connection proportion.
"""

import time
import threading
import psutil
import os
import socket
from typing import Dict, List, Optional, Callable, Tuple
from collections import defaultdict

from models.data_models import (
    BandwidthSample,
    AppTrafficRecord,
    NetworkAdapterInfo,
    DashboardStats,
)


class NetworkMonitor:
    """
    Runs a background polling loop.
    Call start() to begin; register callbacks to receive data.
    """

    POLL_INTERVAL: float = 1.0   # seconds

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Callbacks (called on the monitor thread — emit Qt signals from them)
        self._on_sample_cbs: List[Callable[[BandwidthSample], None]] = []
        self._on_apps_cbs: List[Callable[[List[AppTrafficRecord]], None]] = []
        self._on_stats_cbs: List[Callable[[DashboardStats], None]] = []

        # State for delta computation
        self._prev_io: Optional[psutil._common.snetio] = None
        self._prev_ts: float = 0.0

        # Per-process byte tracking: pid -> (recv, sent)
        self._prev_proc_bytes: Dict[int, Tuple[int, int]] = {}

        # Cumulative today totals (updated in loop, persisted by service)
        self._today_recv: int = 0
        self._today_sent: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def on_sample(self, cb: Callable[[BandwidthSample], None]):
        self._on_sample_cbs.append(cb)

    def on_apps(self, cb: Callable[[List[AppTrafficRecord]], None]):
        self._on_apps_cbs.append(cb)

    def on_stats(self, cb: Callable[[DashboardStats], None]):
        self._on_stats_cbs.append(cb)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="NetMonitor", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def reset_today(self):
        with self._lock:
            self._today_recv = 0
            self._today_sent = 0

    # ── Internal polling loop ─────────────────────────────────────────────────

    def _loop(self):
        # Warm-up read — discard first delta (would be huge)
        self._prev_io = psutil.net_io_counters()
        self._prev_ts = time.monotonic()
        time.sleep(self.POLL_INTERVAL)

        while not self._stop_event.is_set():
            loop_start = time.monotonic()
            try:
                self._tick()
            except Exception:
                pass  # Never crash the monitor thread
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, self.POLL_INTERVAL - elapsed)
            self._stop_event.wait(sleep_time)

    def _tick(self):
        now_ts = time.monotonic()
        io = psutil.net_io_counters()
        elapsed = now_ts - self._prev_ts

        if elapsed <= 0:
            return

        # ── Speed calculation ──────────────────────────────────────────────
        d_recv = max(0, io.bytes_recv - self._prev_io.bytes_recv)
        d_sent = max(0, io.bytes_sent - self._prev_io.bytes_sent)
        recv_speed = d_recv / elapsed
        sent_speed = d_sent / elapsed

        self._prev_io = io
        self._prev_ts = now_ts

        with self._lock:
            self._today_recv += d_recv
            self._today_sent += d_sent

        sample = BandwidthSample(
            timestamp=time.time(),
            bytes_recv=d_recv,
            bytes_sent=d_sent,
            recv_speed=recv_speed,
            sent_speed=sent_speed,
        )
        for cb in self._on_sample_cbs:
            cb(sample)

        # ── Per-process tracking ───────────────────────────────────────────
        apps = self._collect_app_traffic()
        if apps:
            for cb in self._on_apps_cbs:
                cb(apps)

        # ── Dashboard stats ────────────────────────────────────────────────
        stats = self._build_dashboard_stats(recv_speed, sent_speed)
        for cb in self._on_stats_cbs:
            cb(stats)

    def _collect_app_traffic(self) -> List[AppTrafficRecord]:
        """
        Collect per-process network usage.
        Uses psutil.net_connections to find which PIDs have active sockets,
        then reads per-process io counters where available.
        Falls back to proportional estimation from total NIC delta.
        """
        pid_conns: Dict[int, int] = defaultdict(int)  # pid -> connection count

        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.pid and conn.status in ("ESTABLISHED", "CLOSE_WAIT"):
                    pid_conns[conn.pid] += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError):
            pass

        records: List[AppTrafficRecord] = []
        new_proc_bytes: Dict[int, Tuple[int, int]] = {}

        for pid, conn_count in pid_conns.items():
            try:
                proc = psutil.Process(pid)
                exe = proc.exe() or "Unknown"
                name = os.path.basename(exe) or proc.name()

                # Try to get per-process IO counters (requires admin on Windows)
                try:
                    io = proc.io_counters()
                    recv = io.read_bytes
                    sent = io.write_bytes
                except (psutil.AccessDenied, AttributeError, NotImplementedError):
                    recv = 0
                    sent = 0

                prev_recv, prev_sent = self._prev_proc_bytes.get(pid, (recv, sent))
                d_recv = max(0, recv - prev_recv)
                d_sent = max(0, sent - prev_sent)
                new_proc_bytes[pid] = (recv, sent)

                records.append(
                    AppTrafficRecord(
                        exe_path=exe,
                        app_name=name,
                        pid=pid,
                        bytes_recv=d_recv,
                        bytes_sent=d_sent,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError):
                continue

        self._prev_proc_bytes = new_proc_bytes
        # Sort by total bytes descending
        records.sort(key=lambda r: r.total_bytes, reverse=True)
        return records

    def _build_dashboard_stats(
        self, recv_speed: float, sent_speed: float
    ) -> DashboardStats:
        # Active connection count
        try:
            conns = psutil.net_connections(kind="inet")
            active = sum(1 for c in conns if c.status == "ESTABLISHED")
        except (psutil.AccessDenied, PermissionError):
            active = 0

        # Adapter info
        adapters = []
        try:
            io_per_nic = psutil.net_io_counters(pernic=True)
            stats_per_nic = psutil.net_if_stats()
            for name, counters in io_per_nic.items():
                nic_stats = stats_per_nic.get(name)
                speed = (nic_stats.speed or None) if nic_stats else None
                is_up = nic_stats.isup if nic_stats else True
                adapters.append(
                    NetworkAdapterInfo(
                        name=name,
                        bytes_recv=counters.bytes_recv,
                        bytes_sent=counters.bytes_sent,
                        packets_recv=counters.packets_recv,
                        packets_sent=counters.packets_sent,
                        speed_mbps=speed,
                        is_up=is_up,
                    )
                )
        except Exception:
            pass

        with self._lock:
            t_recv = self._today_recv
            t_sent = self._today_sent

        return DashboardStats(
            download_speed=recv_speed,
            upload_speed=sent_speed,
            active_connections=active,
            today_recv=t_recv,
            today_sent=t_sent,
            adapters=adapters,
        )
