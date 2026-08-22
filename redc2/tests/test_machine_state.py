from __future__ import annotations

from redc2.core.config import MachineConfig
from redc2.core.machine import ConnectionState, Machine, TelemetrySnapshot

def _machine() -> Machine:
    return Machine(machine_id=0, config=MachineConfig(name="Test", host="10.0.0.1"))

def test_initial_state_is_offline():
    machine = _machine()
    assert machine.state == ConnectionState.OFFLINE
    assert machine.state.indicator == "○"

def test_mark_connecting():
    machine = _machine()
    machine.mark_connecting()
    assert machine.state == ConnectionState.CONNECTING
    assert machine.state.indicator == "◌"

def test_mark_online_clears_error_and_resets_attempts():
    machine = _machine()
    machine.reconnect_attempts = 3
    machine.mark_error("boom")
    assert machine.state == ConnectionState.ERROR
    machine.mark_online()
    assert machine.state == ConnectionState.ONLINE
    assert machine.last_error is None
    assert machine.reconnect_attempts == 0
    assert machine.connected_since is not None

def test_mark_offline_clears_connected_since():
    machine = _machine()
    machine.mark_online()
    assert machine.connected_since is not None
    machine.mark_offline()
    assert machine.state == ConnectionState.OFFLINE
    assert machine.connected_since is None

def test_mark_error_records_reason():
    machine = _machine()
    machine.mark_error("connection refused")
    assert machine.state == ConnectionState.ERROR
    assert machine.last_error == "connection refused"
    assert machine.state.indicator == "!"

def test_record_snapshot_appends_history():
    machine = _machine()
    machine.record_snapshot(TelemetrySnapshot(cpu_percent=10.0, ram_percent=20.0, temperature_c=30.0))
    machine.record_snapshot(TelemetrySnapshot(cpu_percent=15.0, ram_percent=25.0, temperature_c=35.0))
    assert list(machine.cpu_history) == [10.0, 15.0]
    assert list(machine.ram_history) == [20.0, 25.0]
    assert list(machine.temperature_history) == [30.0, 35.0]
    assert machine.latest.cpu_percent == 15.0

def test_record_snapshot_skips_none_values_in_history():
    machine = _machine()
    machine.record_snapshot(TelemetrySnapshot(cpu_percent=None, ram_percent=20.0, temperature_c=None))
    assert list(machine.cpu_history) == []
    assert list(machine.ram_history) == [20.0]
    assert list(machine.temperature_history) == []

def test_history_bounded_length():
    machine = _machine()
    for i in range(200):
        machine.record_snapshot(TelemetrySnapshot(cpu_percent=float(i)))
    assert len(machine.cpu_history) == 60
    assert machine.cpu_history[-1] == 199.0
