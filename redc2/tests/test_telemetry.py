from __future__ import annotations

import json

import pytest

from redc2.core.machine import TelemetrySnapshot
from redc2.core.telemetry import collect_snapshot, parse_telemetry_json


class _FakeCommandResult:
    def __init__(self, exit_status: int, stdout: str, stderr: str = "") -> None:
        self.exit_status = exit_status
        self.stdout = stdout
        self.stderr = stderr


class _FakeSession:
    """Stands in for SSHSession without touching the network."""

    def __init__(self, probe_result: _FakeCommandResult, ip_result: _FakeCommandResult | None = None):
        self._probe_result = probe_result
        self._ip_result = ip_result or _FakeCommandResult(0, "192.168.1.50\n")
        self.calls: list[str] = []

    def run_command(self, command: str, timeout: float = 10.0):
        self.calls.append(command)
        if "hostname -I" in command:
            return self._ip_result
        return self._probe_result


def test_parse_telemetry_json_valid():
    parsed = parse_telemetry_json('{"cpu_percent": 12.5}')
    assert parsed["cpu_percent"] == 12.5


def test_parse_telemetry_json_invalid_raises():
    with pytest.raises(ValueError):
        parse_telemetry_json("not json at all")


def test_collect_snapshot_full_payload():
    payload = {
        "hostname": "debian-laptop",
        "os_name": "Linux 6.1.0",
        "kernel": "6.1.0",
        "architecture": "x86_64",
        "cpu_model": "Intel(R) Core(TM) i5",
        "cpu_percent": 18.4,
        "cpu_cores": 8,
        "ram_total_gb": 7.7,
        "ram_used_gb": 3.2,
        "ram_percent": 41.5,
        "disk_total_gb": 200.0,
        "disk_used_gb": 50.0,
        "disk_percent": 25.0,
        "uptime_seconds": 3600 * 26,
        "net_sent_mb": 120.5,
        "net_recv_mb": 900.2,
        "temperature_c": 42.1,
    }
    session = _FakeSession(_FakeCommandResult(0, json.dumps(payload)))
    snapshot = collect_snapshot(session)

    assert isinstance(snapshot, TelemetrySnapshot)
    assert snapshot.hostname == "debian-laptop"
    assert snapshot.cpu_percent == 18.4
    assert snapshot.ram_percent == 41.5
    assert snapshot.temperature_c == 42.1
    assert snapshot.ip_address == "192.168.1.50"
    assert snapshot.format_temp() == "42.1°C"
    assert snapshot.format_uptime() == "1d 2h"


def test_collect_snapshot_missing_sensors_gracefully_none():
    payload = {"hostname": "pi", "cpu_percent": None, "temperature_c": None}
    session = _FakeSession(_FakeCommandResult(0, json.dumps(payload)))
    snapshot = collect_snapshot(session)

    assert snapshot.cpu_percent is None
    assert snapshot.format_cpu() == "N/A"
    assert snapshot.temperature_c is None
    assert snapshot.format_temp() == "N/A"


def test_collect_snapshot_probe_failed_returns_empty_snapshot():
    session = _FakeSession(_FakeCommandResult(1, "", "python3: command not found"))
    snapshot = collect_snapshot(session)
    assert snapshot.cpu_percent is None
    assert snapshot.hostname is None


def test_collect_snapshot_malformed_json_does_not_raise():
    session = _FakeSession(_FakeCommandResult(0, "not valid json {{{"))
    snapshot = collect_snapshot(session)
    assert snapshot.cpu_percent is None
