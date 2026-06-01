"""
models/data_models.py
Pure dataclasses used across the application.
No UI or database logic here — just structured data containers.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BandwidthSample:
    """A single bandwidth measurement at one point in time."""
    timestamp: float       # Unix epoch seconds
    bytes_recv: int        # Total bytes received since last sample
    bytes_sent: int        # Total bytes sent since last sample
    recv_speed: float = 0  # Bytes per second (computed)
    sent_speed: float = 0  # Bytes per second (computed)


@dataclass
class AppTrafficRecord:
    """Network traffic attributed to a single application."""
    exe_path: str
    app_name: str
    pid: int
    bytes_recv: int
    bytes_sent: int

    @property
    def total_bytes(self) -> int:
        return self.bytes_recv + self.bytes_sent


@dataclass
class DailySummary:
    """Aggregated bandwidth for a calendar day."""
    day_date: str          # 'YYYY-MM-DD'
    bytes_recv: int
    bytes_sent: int

    @property
    def total_bytes(self) -> int:
        return self.bytes_recv + self.bytes_sent


@dataclass
class NetworkAdapterInfo:
    """Snapshot of a single network interface."""
    name: str
    bytes_recv: int
    bytes_sent: int
    packets_recv: int
    packets_sent: int
    speed_mbps: Optional[float] = None   # NIC link speed if available
    is_up: bool = True


@dataclass
class DashboardStats:
    """All data shown on the Dashboard page."""
    download_speed: float = 0.0         # Current B/s
    upload_speed: float = 0.0           # Current B/s
    active_connections: int = 0
    today_recv: int = 0
    today_sent: int = 0
    month_recv: int = 0
    month_sent: int = 0
    last30_recv: int = 0
    last30_sent: int = 0
    adapters: List[NetworkAdapterInfo] = field(default_factory=list)


@dataclass
class AlertConfig:
    """User-configured quota alert settings."""
    monthly_quota_gb: float = 0.0       # 0 means disabled
    warn_pct: float = 80.0              # % at which to warn
    critical_pct: float = 95.0         # % at which to alert critically
    notified_warn: bool = False
    notified_critical: bool = False
