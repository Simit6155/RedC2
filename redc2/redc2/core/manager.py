from __future__ import annotations

import asyncio
import logging

from redc2.core.config import AppConfig, MachineConfig
from redc2.core.machine import ConnectionState, Machine
from redc2.core.ssh import (
    SSHAuthError,
    SSHConnectionError,
    SSHHostKeyError,
    SSHSession,
)
from redc2.core.telemetry import collect_snapshot

logger = logging.getLogger("redc2.manager")

class MachineNotFoundError(Exception):
    def __init__(self, machine_id: int) -> None:
        self.machine_id = machine_id
        super().__init__(f"machine {machine_id} does not exist.")

class MachineManager:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._machines: dict[int, Machine] = {
            idx: Machine(machine_id=idx, config=machine_config)
            for idx, machine_config in enumerate(config.machines)
        }
        self._sessions: dict[int, SSHSession] = {
            idx: SSHSession(machine_config, connection_timeout=config.connection_timeout)
            for idx, machine_config in self._machines_configs().items()
        }
        self._locks: dict[int, asyncio.Lock] = {idx: asyncio.Lock() for idx in self._machines}

    def _machines_configs(self) -> dict[int, MachineConfig]:
        return {idx: machine.config for idx, machine in self._machines.items()}

    @property
    def config(self) -> AppConfig:
        return self._config

    def list_machines(self) -> list[Machine]:
        return [self._machines[i] for i in sorted(self._machines)]

    def get(self, machine_id: int) -> Machine:
        try:
            return self._machines[machine_id]
        except KeyError as exc:
            raise MachineNotFoundError(machine_id) from exc

    def get_session(self, machine_id: int) -> SSHSession:
        try:
            return self._sessions[machine_id]
        except KeyError as exc:
            raise MachineNotFoundError(machine_id) from exc

    def exists(self, machine_id: int) -> bool:
        return machine_id in self._machines

    def count(self) -> int:
        return len(self._machines)

    def online_count(self) -> int:
        return sum(
            1 for m in self._machines.values() if m.state == ConnectionState.ONLINE
        )

    def add_machine(self, machine_config: MachineConfig) -> Machine:
        next_id = (max(self._machines) + 1) if self._machines else 0
        machine = Machine(machine_id=next_id, config=machine_config)
        self._machines[next_id] = machine
        self._sessions[next_id] = SSHSession(
            machine_config, connection_timeout=self._config.connection_timeout
        )
        self._locks[next_id] = asyncio.Lock()
        return machine

    async def connect(self, machine_id: int) -> None:
        machine = self.get(machine_id)
        session = self.get_session(machine_id)
        lock = self._locks[machine_id]

        async with lock:
            if session.is_connected:
                machine.mark_online()
                return

            machine.mark_connecting()
            try:
                await asyncio.to_thread(session.connect)
            except SSHHostKeyError as exc:
                machine.mark_error(str(exc))
                logger.error("Host key verification failed for %s: %s", machine.name, exc)
            except SSHAuthError as exc:
                machine.mark_error(str(exc))
                logger.error("Authentication failure for %s: %s", machine.name, exc)
            except SSHConnectionError as exc:
                machine.mark_error(str(exc))
                logger.warning("Connection failed for %s: %s", machine.name, exc)
            except Exception as exc:
                machine.mark_error(f"Unexpected error: {exc}")
                logger.exception("Unexpected error connecting to %s", machine.name)
            else:
                machine.mark_online()
                logger.info("Machine '%s' is online", machine.name)

    async def disconnect(self, machine_id: int) -> None:
        session = self.get_session(machine_id)
        machine = self.get(machine_id)
        await asyncio.to_thread(session.close)
        machine.mark_offline()

    async def reconnect_with_backoff(self, machine_id: int) -> None:
        machine = self.get(machine_id)
        if machine.reconnect_attempts >= self._config.max_reconnect_attempts:
            logger.warning(
                "Machine '%s' hit max reconnect attempts (%d); manual 'reconnect' required.",
                machine.name,
                self._config.max_reconnect_attempts,
            )
            return
        machine.reconnect_attempts += 1
        await self.connect(machine_id)

    def next_backoff_delay(self, machine_id: int) -> float:
        machine = self.get(machine_id)
        base = self._config.reconnect_backoff_base
        delay = base * (2 ** max(0, machine.reconnect_attempts - 1))
        return min(delay, self._config.reconnect_backoff_max)

    async def poll_telemetry(self, machine_id: int) -> None:
        machine = self.get(machine_id)
        session = self.get_session(machine_id)
        if machine.state != ConnectionState.ONLINE or not session.is_connected:
            return
        try:
            snapshot = await asyncio.to_thread(collect_snapshot, session)
        except SSHConnectionError as exc:
            machine.mark_error(f"Lost connection during telemetry poll: {exc}")
            logger.warning("Telemetry error for %s: %s", machine.name, exc)
            return
        except Exception as exc:
            logger.exception("Unexpected telemetry error for %s", machine.name)
            return
        machine.record_snapshot(snapshot)

    async def shutdown(self) -> None:
        for machine_id, session in self._sessions.items():
            if session.is_connected:
                await asyncio.to_thread(session.close)
                self.get(machine_id).mark_offline()
