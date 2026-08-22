from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import paramiko

from redc2.core.config import MachineConfig

logger = logging.getLogger("redc2.ssh")

class SSHAuthError(Exception):
    pass

class SSHConnectionError(Exception):
    pass

class SSHHostKeyError(Exception):
    pass

@dataclass
class CommandResult:
    exit_status: int
    stdout: str
    stderr: str

def _load_host_keys(machine: MachineConfig) -> paramiko.HostKeys:
    host_keys = paramiko.HostKeys()
    candidates = []
    if machine.known_hosts_file:
        candidates.append(Path(machine.known_hosts_file).expanduser())
    candidates.append(Path.home() / ".ssh" / "known_hosts")

    for candidate in candidates:
        if candidate.is_file():
            try:
                host_keys.load(str(candidate))
            except Exception as exc:
                logger.warning("Could not load known_hosts %s: %s", candidate, exc)
            break
    return host_keys

class _VerifyingPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, strict: bool) -> None:
        self.strict = strict

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key) -> None:
        fingerprint = key.get_fingerprint().hex()
        if self.strict:
            raise SSHHostKeyError(
                f"Host key for '{hostname}' is not in known_hosts "
                f"(fingerprint {fingerprint}). Add it with 'ssh-keyscan' / "
                f"by connecting once with the OpenSSH client, or set "
                f"strict_host_key_checking = false for this machine if you "
                f"understand the risk."
            )
        logger.warning(
            "Accepting unknown host key for '%s' (fingerprint %s) because "
            "strict_host_key_checking is disabled for this machine.",
            hostname,
            fingerprint,
        )

class SSHSession:
    def __init__(self, config: MachineConfig, connection_timeout: float = 8.0) -> None:
        self._config = config
        self._timeout = connection_timeout
        self._client: paramiko.SSHClient | None = None

    @property
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        transport = self._client.get_transport()
        return bool(transport and transport.is_active())

    def connect(self, password_prompt: Callable[[], str] | None = None) -> None:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        host_keys = _load_host_keys(self._config)
        for hostname in host_keys.keys():
            for keytype, key in host_keys[hostname].items():
                client.get_host_keys().add(hostname, keytype, key)
        client.set_missing_host_key_policy(
            _VerifyingPolicy(strict=self._config.strict_host_key_checking)
        )

        auth_errors: list[str] = []
        connected = False

        if self._config.key_file:
            try:
                self._connect_with_key(client)
                connected = True
            except Exception as exc:
                auth_errors.append(f"key_file: {exc}")

        if not connected and self._config.use_agent:
            try:
                client.connect(
                    hostname=self._config.host,
                    port=self._config.port,
                    username=self._config.username or None,
                    timeout=self._timeout,
                    allow_agent=True,
                    look_for_keys=False,
                )
                connected = True
            except (SSHHostKeyError,):
                raise
            except Exception as exc:
                auth_errors.append(f"agent: {exc}")

        if not connected and self._config.allow_password_auth:
            password = None

            if self._config.password:
                try:
                    client.connect(
                        hostname=self._config.host,
                        port=self._config.port,
                        username=self._config.username or None,
                        password=self._config.password,
                        timeout=self._timeout,
                        allow_agent=False,
                        look_for_keys=False,
                    )
                    connected = True
                except (SSHHostKeyError,):
                    raise
                except Exception as exc:
                    auth_errors.append(f"password: {exc}")

            elif password_prompt is not None:
                try:
                    password = password_prompt()
                    client.connect(
                        hostname=self._config.host,
                        port=self._config.port,
                        username=self._config.username or None,
                        password=password,
                        timeout=self._timeout,
                        allow_agent=False,
                        look_for_keys=False,
                    )
                    connected = True
                except (SSHHostKeyError,):
                    raise
                except Exception as exc:
                    auth_errors.append(f"password: {exc}")
                finally:
                    password = None

        if not connected:
            client.close()
            if any("Unable to connect" in e or "timed out" in e.lower() for e in auth_errors):
                raise SSHConnectionError(
                    f"Could not reach {self._config.host}:{self._config.port}"
                )
            raise SSHAuthError(
                f"Authentication failed for '{self._config.name}'. "
                f"Tried: {'; '.join(auth_errors) if auth_errors else 'no methods configured'}."
            )

        self._client = client
        logger.info("SSH connection established to %s", self._config.name)

    def _connect_with_key(self, client: paramiko.SSHClient) -> None:
        key_path = Path(self._config.key_file).expanduser()
        if not key_path.is_file():
            raise SSHAuthError(f"Key file not found: {key_path}")

        last_exc: Exception | None = None
        for key_cls in (
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.RSAKey,
            paramiko.DSSKey,
        ):
            try:
                pkey = key_cls.from_private_key_file(str(key_path))
            except paramiko.PasswordRequiredException as exc:
                raise SSHAuthError(
                    f"Key '{key_path}' is encrypted; passphrase-protected keys "
                    f"are not supported non-interactively yet."
                ) from exc
            except Exception as exc:
                last_exc = exc
                continue

            try:
                client.connect(
                    hostname=self._config.host,
                    port=self._config.port,
                    username=self._config.username or None,
                    pkey=pkey,
                    timeout=self._timeout,
                    allow_agent=False,
                    look_for_keys=False,
                )
                return
            except SSHHostKeyError:
                raise
            except Exception as exc:
                last_exc = exc
                continue

        raise SSHAuthError(f"Could not use key '{key_path}': {last_exc}")

    def run_command(self, command: str, timeout: float = 10.0) -> CommandResult:
        if not self.is_connected or self._client is None:
            raise SSHConnectionError("Not connected.")
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        stdin.close()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        return CommandResult(exit_status=status, stdout=out, stderr=err)

    def open_shell(self, term: str = "xterm-256color", width: int = 80, height: int = 24):
        if not self.is_connected or self._client is None:
            raise SSHConnectionError("Not connected.")
        channel = self._client.invoke_shell(term=term, width=width, height=height)
        channel.settimeout(0.0)
        return channel

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                logger.info("SSH connection closed to %s", self._config.name)
                self._client = None
