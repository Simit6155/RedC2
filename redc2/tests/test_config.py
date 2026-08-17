from __future__ import annotations

import pytest

from redc2.core.config import ConfigError, load_config


def test_load_example_config(tmp_path):
    toml_text = """
[settings]
refresh_interval = 3.0

[[machines]]
name = "Test-Box"
host = "10.0.0.5"
username = "user"
key_file = "~/.ssh/id_ed25519"
"""
    path = tmp_path / "machines.toml"
    path.write_text(toml_text)

    config = load_config(path)

    assert config.refresh_interval == 3.0
    assert len(config.machines) == 1
    assert config.machines[0].name == "Test-Box"
    assert config.machines[0].port == 22


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_machine_missing_host_raises(tmp_path):
    toml_text = """
[[machines]]
name = "Bad-Box"
"""
    path = tmp_path / "machines.toml"
    path.write_text(toml_text)
    with pytest.raises(ConfigError):
        load_config(path)


def test_invalid_port_raises(tmp_path):
    toml_text = """
[[machines]]
name = "Bad-Port"
host = "10.0.0.1"
port = 70000
"""
    path = tmp_path / "machines.toml"
    path.write_text(toml_text)
    with pytest.raises(ConfigError):
        load_config(path)


def test_machines_not_list_raises(tmp_path):
    toml_text = """
machines = "oops"
"""
    path = tmp_path / "machines.toml"
    path.write_text(toml_text)
    with pytest.raises(ConfigError):
        load_config(path)
