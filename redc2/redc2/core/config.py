from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

class ConfigError(Exception):
    pass

@dataclass(frozen=True)
class MachineConfig:
    name: str
    host: str
    port: int = 22
    username: str = ""
    password: str | None = None
    key_file: str | None = None
    use_agent: bool = True
    allow_password_auth: bool = False
    known_hosts_file: str | None = None
    strict_host_key_checking: bool = True
    telemetry_interval: float = 2.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ConfigError("Machine entry is missing a 'name'.")
        if not self.host:
            raise ConfigError(f"Machine '{self.name}' is missing a 'host'.")
        if not (0 < self.port < 65536):
            raise ConfigError(
                f"Machine '{self.name}' has an invalid port: {self.port}"
            )

@dataclass(frozen=True)
class AppConfig:
    machines: list[MachineConfig] = field(default_factory=list)
    log_file: str = "~/.redc2/redc2.log"
    refresh_interval: float = 2.0
    connection_timeout: float = 8.0
    max_reconnect_attempts: int = 5
    reconnect_backoff_base: float = 2.0
    reconnect_backoff_max: float = 60.0

def _build_machine_config(raw: dict[str, Any]) -> MachineConfig:
    try:
        return MachineConfig(
            name=str(raw.get("name", "")),
            host=str(raw.get("host", "")),
            port=int(raw.get("port", 22)),
            username=str(raw.get("username", "")),
            password=raw.get("password"),
            key_file=raw.get("key_file"),
            use_agent=bool(raw.get("use_agent", True)),
            allow_password_auth=bool(raw.get("allow_password_auth", False)),
            known_hosts_file=raw.get("known_hosts_file"),
            strict_host_key_checking=bool(
                raw.get("strict_host_key_checking", True)
            ),
            telemetry_interval=float(raw.get("telemetry_interval", 2.0)),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid machine configuration: {raw!r} ({exc})") from exc

def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Could not parse '{config_path}': {exc}") from exc

    raw_machines = raw.get("machines", [])
    if not isinstance(raw_machines, list):
        raise ConfigError("'machines' must be an array of tables ([[machines]]).")

    machines = [_build_machine_config(entry) for entry in raw_machines]

    settings = raw.get("settings", {})
    if not isinstance(settings, dict):
        settings = {}

    try:
        return AppConfig(
            machines=machines,
            log_file=str(settings.get("log_file", "~/.redc2/redc2.log")),
            refresh_interval=float(settings.get("refresh_interval", 2.0)),
            connection_timeout=float(settings.get("connection_timeout", 8.0)),
            max_reconnect_attempts=int(settings.get("max_reconnect_attempts", 5)),
            reconnect_backoff_base=float(
                settings.get("reconnect_backoff_base", 2.0)
            ),
            reconnect_backoff_max=float(
                settings.get("reconnect_backoff_max", 60.0)
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid [settings] section: {exc}") from exc

def find_default_config() -> Path | None:
    candidates = [
        Path.cwd() / "config" / "machines.toml",
        Path.cwd() / "machines.toml",
        Path.home() / ".redc2" / "machines.toml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
