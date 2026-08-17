from __future__ import annotations

import pytest

from redc2.commands.parser import (
    ActionKind,
    CommandDispatcher,
    CommandError,
    parse_command,
)
from redc2.core.config import AppConfig, MachineConfig
from redc2.core.manager import MachineManager


def _manager() -> MachineManager:
    machines = [
        MachineConfig(name="Debian-Laptop", host="192.168.1.100", username="user"),
        MachineConfig(name="Raspberry-Pi", host="192.168.1.101", username="pi"),
    ]
    return MachineManager(AppConfig(machines=machines))


def test_parse_command_basic():
    parsed = parse_command("select 0")
    assert parsed.name == "select"
    assert parsed.args == ("0",)


def test_parse_command_case_insensitive_verb():
    parsed = parse_command("LIST")
    assert parsed.name == "list"


def test_parse_command_empty():
    parsed = parse_command("   ")
    assert parsed.name == ""


def test_parse_command_bad_quoting_raises():
    with pytest.raises(CommandError):
        parse_command('select "unterminated')


def test_dispatch_list():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("list")
    assert result.action is ActionKind.LIST
    assert "Debian-Laptop" in result.message
    assert "Raspberry-Pi" in result.message


def test_dispatch_select_valid():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("select 1")
    assert result.action is ActionKind.SELECT_MACHINE
    assert result.machine_id == 1
    assert not result.is_error


def test_dispatch_select_invalid_id():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("select 99")
    assert result.is_error
    assert "does not exist" in result.message


def test_dispatch_select_missing_arg():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("select")
    assert result.is_error


def test_dispatch_select_non_integer():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("select abc")
    assert result.is_error


def test_dispatch_unknown_command():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("frobnicate")
    assert result.is_error
    assert "Unknown command" in result.message


def test_dispatch_empty_command():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("")
    assert result.action is ActionKind.NONE
    assert result.message == ""


def test_dispatch_quit_and_exit():
    dispatcher = CommandDispatcher(_manager())
    assert dispatcher.dispatch("quit").action is ActionKind.QUIT
    assert dispatcher.dispatch("exit").action is ActionKind.QUIT


def test_dispatch_help():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("help")
    assert result.action is ActionKind.HELP
    assert "select" in result.message


def test_dispatch_reconnect_invalid():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("reconnect 42")
    assert result.is_error


def test_dispatch_info_valid():
    dispatcher = CommandDispatcher(_manager())
    result = dispatcher.dispatch("info 0")
    assert result.action is ActionKind.SHOW_INFO
    assert "Debian-Laptop" in result.message
