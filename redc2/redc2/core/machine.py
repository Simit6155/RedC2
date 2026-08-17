"""Runtime machine model: connection state and telemetry snapshots."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from time import monotonic

from redc2.core.config import MachineConfig

HISTORY_LENGTH = 60


class ConnectionState(str, Enum):
    """Lifecycle states for a machine's SSH connection."""

    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    ERROR = "ERROR"

    @property
    def indicator(self) -> str:
        return {
            ConnectionState.ONLINE: "●",
            ConnectionState.OFFLINE: "○",
            ConnectionState.CONNECTING: "◌",
            ConnectionState.ERROR: "!",
        }[self]


@dataclass
class TelemetrySnapshot:
    """A single point-in-time reading of a machine's vitals."""

    hostname: str | None = None
    os_name: str | None = None
    kernel: str | None = None
    architecture: str | None = None
    cpu_model: str | None = None
    cpu_percent: float | None = None
    cpu_cores: int | None = None
    ram_used_gb: float | None = None
    ram_total_gb: float | None = None
    ram_percent: float | None = None
    disk_used_gb: float | None = None
    disk_total_gb: float | None = None
    disk_percent: float | None = None
    uptime_seconds: float | None = None
    ip_address: str | None = None
    net_sent_mb: float | None = None
    net_recv_mb: float | None = None
    temperature_c: float | None = None
    timestamp: float = field(default_factory=monotonic)

    def format_temp(self) -> str:
        return f"{self.temperature_c:.1f}°C" if self.temperature_c is not None else "N/A"

    def format_cpu(self) -> str:
        return f"{self.cpu_percent:.0f}%" if self.cpu_percent is not None else "N/A"

    def format_ram(self) -> str:
        return f"{self.ram_percent:.0f}%" if self.ram_percent is not None else "N/A"

    def format_uptime(self) -> str:
        if self.uptime_seconds is None:
            return "N/A"
        total_seconds = int(self.uptime_seconds)
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


@dataclass
class Machine:
    """A managed machine: its static config plus live runtime state."""

    machine_id: int
    config: MachineConfig
    state: ConnectionState = ConnectionState.OFFLINE
    last_error: str | None = None
    latest: TelemetrySnapshot = field(default_factory=TelemetrySnapshot)
    cpu_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=HISTORY_LENGTH)
    )
    ram_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=HISTORY_LENGTH)
    )
    temperature_history: deque[float] = field(
        default_factory=lambda: deque(maxlen=HISTORY_LENGTH)
    )
    reconnect_attempts: int = 0
    connected_since: float | None = None

    @property
    def name(self) -> str:
        return self.config.name

    def record_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        """Store a new telemetry snapshot and append to history buffers."""
        self.latest = snapshot
        if snapshot.cpu_percent is not None:
            self.cpu_history.append(snapshot.cpu_percent)
        if snapshot.ram_percent is not None:
            self.ram_history.append(snapshot.ram_percent)
        if snapshot.temperature_c is not None:
            self.temperature_history.append(snapshot.temperature_c)

    def mark_online(self) -> None:
        self.state = ConnectionState.ONLINE
        self.last_error = None
        self.reconnect_attempts = 0
        self.connected_since = monotonic()

    def mark_offline(self) -> None:
        self.state = ConnectionState.OFFLINE
        self.connected_since = None

    def mark_connecting(self) -> None:
        self.state = ConnectionState.CONNECTING

    def mark_error(self, reason: str) -> None:
        self.state = ConnectionState.ERROR
        self.last_error = reason
        self.connected_since = None
