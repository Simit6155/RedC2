from __future__ import annotations

import pytest

from redc2.core.config import AppConfig, MachineConfig
from redc2.core.machine import ConnectionState
from redc2.core.manager import MachineManager, MachineNotFoundError


def _config(*names: str) -> AppConfig:
    machines = [MachineConfig(name=n, host=f"10.0.0.{i}") for i, n in enumerate(names)]
    return AppConfig(machines=machines)


def test_machine_ids_start_at_zero():
    manager = MachineManager(_config("Debian-Laptop", "Raspberry-Pi"))
    machines = manager.list_machines()
    assert [m.machine_id for m in machines] == [0, 1]
    assert machines[0].name == "Debian-Laptop"
    assert machines[1].name == "Raspberry-Pi"


def test_get_existing_machine():
    manager = MachineManager(_config("A", "B"))
    machine = manager.get(1)
    assert machine.name == "B"


def test_get_missing_machine_raises():
    manager = MachineManager(_config("A"))
    with pytest.raises(MachineNotFoundError):
        manager.get(5)


def test_exists():
    manager = MachineManager(_config("A"))
    assert manager.exists(0) is True
    assert manager.exists(1) is False


def test_online_count_ignores_offline():
    manager = MachineManager(_config("A", "B"))
    manager.get(0).mark_online()
    assert manager.online_count() == 1
    assert manager.count() == 2


def test_add_machine_gets_next_id():
    manager = MachineManager(_config("A", "B"))
    new = manager.add_machine(MachineConfig(name="C", host="10.0.0.9"))
    assert new.machine_id == 2
    assert manager.count() == 3


def test_add_machine_to_empty_manager_starts_at_zero():
    manager = MachineManager(AppConfig(machines=[]))
    new = manager.add_machine(MachineConfig(name="Only", host="10.0.0.1"))
    assert new.machine_id == 0


def test_offline_machine_does_not_block_others():
    manager = MachineManager(_config("A", "B"))
    manager.get(0).mark_error("connection refused")
    manager.get(1).mark_online()
    assert manager.get(0).state == ConnectionState.ERROR
    assert manager.get(1).state == ConnectionState.ONLINE
