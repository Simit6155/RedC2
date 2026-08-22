from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest

from redc2.core.config import AppConfig, MachineConfig
from redc2.core.machine import ConnectionState
from redc2.core.manager import MachineManager
from redc2.core.ssh import SSHConnectionError

def _manager(**settings) -> MachineManager:
    config = AppConfig(
        machines=[MachineConfig(name="A", host="10.0.0.1")],
        **settings,
    )
    return MachineManager(config)

@pytest.mark.asyncio
async def test_connect_success_marks_online():
    manager = _manager()
    with patch.object(manager.get_session(0), "connect", return_value=None):
        await manager.connect(0)
    assert manager.get(0).state == ConnectionState.ONLINE

@pytest.mark.asyncio
async def test_connect_failure_marks_error():
    manager = _manager()
    with patch.object(
        manager.get_session(0), "connect", side_effect=SSHConnectionError("unreachable")
    ):
        await manager.connect(0)
    assert manager.get(0).state == ConnectionState.ERROR
    assert "unreachable" in manager.get(0).last_error

@pytest.mark.asyncio
async def test_reconnect_respects_max_attempts():
    manager = _manager(max_reconnect_attempts=2)
    with patch.object(
        manager.get_session(0), "connect", side_effect=SSHConnectionError("down")
    ):
        await manager.reconnect_with_backoff(0)
        await manager.reconnect_with_backoff(0)
        assert manager.get(0).reconnect_attempts == 2

        await manager.reconnect_with_backoff(0)
        assert manager.get(0).reconnect_attempts == 2

@pytest.mark.asyncio
async def test_poll_telemetry_noop_when_offline():
    manager = _manager()

    await manager.poll_telemetry(0)
    assert manager.get(0).latest.cpu_percent is None

@pytest.mark.asyncio
async def test_poll_telemetry_records_snapshot_when_online():
    manager = _manager()
    from redc2.core.machine import TelemetrySnapshot

    with patch.object(manager.get_session(0), "connect", return_value=None):
        await manager.connect(0)
    with patch.object(
        type(manager.get_session(0)), "is_connected", new_callable=PropertyMock
    ) as mock_connected, patch(
        "redc2.core.manager.collect_snapshot",
        return_value=TelemetrySnapshot(cpu_percent=33.3),
    ):
        mock_connected.return_value = True
        await manager.poll_telemetry(0)
    assert manager.get(0).latest.cpu_percent == 33.3

@pytest.mark.asyncio
async def test_poll_telemetry_error_marks_machine_error():
    manager = _manager()
    with patch.object(manager.get_session(0), "connect", return_value=None):
        await manager.connect(0)
    with patch.object(
        type(manager.get_session(0)), "is_connected", new_callable=PropertyMock
    ) as mock_connected, patch(
        "redc2.core.manager.collect_snapshot",
        side_effect=SSHConnectionError("dropped"),
    ):
        mock_connected.return_value = True
        await manager.poll_telemetry(0)
    assert manager.get(0).state == ConnectionState.ERROR

def test_backoff_delay_grows_and_caps():
    manager = _manager(reconnect_backoff_base=2.0, reconnect_backoff_max=10.0)
    machine = manager.get(0)
    machine.reconnect_attempts = 1
    assert manager.next_backoff_delay(0) == 2.0
    machine.reconnect_attempts = 3
    assert manager.next_backoff_delay(0) == 8.0
    machine.reconnect_attempts = 10
    assert manager.next_backoff_delay(0) == 10.0
