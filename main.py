#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from dataclasses import dataclass, field
from typing import Any


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
            raise ValueError("Machine entry is missing a 'name'.")
        if not self.host:
            raise ValueError(f"Machine '{self.name}' is missing a 'host'.")
        if not (0 < self.port < 65536):
            raise ValueError(f"Machine '{self.name}' has an invalid port: {self.port}")


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
            strict_host_key_checking=bool(raw.get("strict_host_key_checking", True)),
            telemetry_interval=float(raw.get("telemetry_interval", 2.0)),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid machine configuration: {raw!r} ({exc})") from exc


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open("rb") as fh:
            raw = tomllib.load(fh)
    except Exception as exc:
        raise ValueError(f"Could not parse '{config_path}': {exc}") from exc

    raw_machines = raw.get("machines", [])
    if not isinstance(raw_machines, list):
        raise ValueError("'machines' must be an array of tables ([[machines]]).")

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
            reconnect_backoff_base=float(settings.get("reconnect_backoff_base", 2.0)),
            reconnect_backoff_max=float(settings.get("reconnect_backoff_max", 60.0)),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid [settings] section: {exc}") from exc


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


def setup_logging(log_file: str) -> None:
    log_path = Path(log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="stardust-redc2", description="Homelab SSH Management Dashboard")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to machines.toml config file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv if argv is not None else sys.argv[1:])

        config_path = Path(args.config).expanduser() if args.config else find_default_config()
        if config_path is None:
            print(
                "No configuration found. Create config/machines.toml "
                "(see config/machines.toml.example) or pass --config <path>.",
                file=sys.stderr,
            )
            return 1

        config: AppConfig = load_config(config_path)
        setup_logging(config.log_file)
        logging.getLogger("redc2").info("Starting with %d machine(s)", len(config.machines))

        from redc2.app import REDC2App

        app = REDC2App(config)
        app.run()
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
