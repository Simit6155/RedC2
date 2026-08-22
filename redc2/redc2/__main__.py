from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from redc2.core.config import AppConfig, ConfigError, find_default_config, load_config

def _setup_logging(log_file: str) -> None:
    log_path = Path(log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="redc2", description="REDC2 SSH management TUI")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to machines.toml (default: config/machines.toml, ./machines.toml, or ~/.redc2/machines.toml)",
    )
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    config_path = Path(args.config).expanduser() if args.config else find_default_config()
    if config_path is None:
        print(
            "No configuration found. Create config/machines.toml "
            "(see config/machines.toml.example) or pass --config <path>.",
            file=sys.stderr,
        )
        return 1

    try:
        config: AppConfig = load_config(config_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    _setup_logging(config.log_file)
    logging.getLogger("redc2").info("Starting REDC2 with %d machine(s)", len(config.machines))

    from redc2.app import REDC2App

    app = REDC2App(config)
    app.run()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
