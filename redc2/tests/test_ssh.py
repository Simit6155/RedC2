from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from redc2.core.config import MachineConfig
from redc2.core.ssh import SSHAuthError, SSHConnectionError, SSHSession


def _config(**overrides) -> MachineConfig:
    defaults = dict(
        name="Test-Box",
        host="10.0.0.5",
        port=22,
        username="user",
        key_file=None,
        use_agent=True,
        allow_password_auth=False,
    )
    defaults.update(overrides)
    return MachineConfig(**defaults)


def test_is_connected_false_before_connect():
    session = SSHSession(_config())
    assert session.is_connected is False


@patch("redc2.core.ssh.paramiko.SSHClient")
def test_connect_via_agent_succeeds(mock_client_cls):
    mock_client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    mock_client.get_transport.return_value = transport
    mock_client_cls.return_value = mock_client

    session = SSHSession(_config(use_agent=True, key_file=None))
    session.connect()

    assert session.is_connected is True
    mock_client.connect.assert_called_once()


@patch("redc2.core.ssh.paramiko.SSHClient")
def test_connect_all_methods_fail_raises_auth_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client.connect.side_effect = Exception("agent: no identities")
    mock_client_cls.return_value = mock_client

    session = SSHSession(_config(use_agent=True, key_file=None, allow_password_auth=False))
    with pytest.raises(SSHAuthError):
        session.connect()


def test_run_command_without_connection_raises():
    session = SSHSession(_config())
    with pytest.raises(SSHConnectionError):
        session.run_command("uptime")


def test_open_shell_without_connection_raises():
    session = SSHSession(_config())
    with pytest.raises(SSHConnectionError):
        session.open_shell()


@patch("redc2.core.ssh.paramiko.SSHClient")
def test_run_command_parses_output(mock_client_cls):
    mock_client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    mock_client.get_transport.return_value = transport
    mock_client_cls.return_value = mock_client

    stdin = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.read.return_value = b"hello\n"
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    mock_client.exec_command.return_value = (stdin, stdout, stderr)

    session = SSHSession(_config())
    session.connect()
    result = session.run_command("echo hello")

    assert result.exit_status == 0
    assert result.stdout == "hello\n"


@patch("redc2.core.ssh.paramiko.SSHClient")
def test_close_resets_connected_state(mock_client_cls):
    mock_client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    mock_client.get_transport.return_value = transport
    mock_client_cls.return_value = mock_client

    session = SSHSession(_config())
    session.connect()
    assert session.is_connected is True
    session.close()
    assert session.is_connected is False
