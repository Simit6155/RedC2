"""Command parsing and dispatch for the REDC2 command line.

This module is intentionally UI-agnostic: :func:`parse_command` turns raw
text into a :class:`ParsedCommand`, and :class:`CommandDispatcher` turns a
``ParsedCommand`` (plus the current :class:`MachineManager`) into a
:class:`CommandResult`. The Textual app layer reacts to ``CommandResult``
(e.g. to switch screens) but no Paramiko or Textual code lives here, so it
is fully unit-testable.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum, auto

from redc2.core.manager import MachineManager, MachineNotFoundError

HELP_TEXT = """\
Available commands:
  help              Show this help text
  list              List all configured machines
  select <id>       Open the detail/terminal view for a machine
  info <id>         Show detailed telemetry for a machine
  dashboard         Return to the main dashboard
  refresh           Force an immediate telemetry refresh
  reconnect <id>    Manually retry connecting to a machine
  clear             Clear the command output log
  back              Go back to the previous view
  quit / exit       Close REDC2
"""


class CommandError(Exception):
    """Raised for malformed input before dispatch (e.g. bad syntax)."""


@dataclass(frozen=True)
class ParsedCommand:
    """A tokenized command line: a verb plus its raw string arguments."""

    name: str
    args: tuple[str, ...]

    @property
    def raw(self) -> str:
        return " ".join((self.name, *self.args)).strip()


class ActionKind(Enum):
    """High-level UI actions the app layer may need to react to."""

    NONE = auto()
    SHOW_DASHBOARD = auto()
    SELECT_MACHINE = auto()
    SHOW_INFO = auto()
    REFRESH = auto()
    RECONNECT = auto()
    CLEAR = auto()
    BACK = auto()
    QUIT = auto()
    HELP = auto()
    LIST = auto()


@dataclass(frozen=True)
class CommandResult:
    """The outcome of dispatching a command."""

    action: ActionKind
    message: str
    is_error: bool = False
    machine_id: int | None = None


# Commands that take no arguments.
_ZERO_ARG_COMMANDS = {"help", "list", "dashboard", "refresh", "clear", "back", "quit", "exit"}
# Commands that take exactly one integer argument.
_ONE_INT_ARG_COMMANDS = {"select", "info", "reconnect"}


def parse_command(text: str) -> ParsedCommand:
    """Tokenize a raw command line into a :class:`ParsedCommand`.

    Raises:
        CommandError: if the text cannot be tokenized (e.g. unbalanced quotes).
    """
    stripped = text.strip()
    if not stripped:
        return ParsedCommand(name="", args=())
    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise CommandError(f"Could not parse command: {exc}") from exc
    if not tokens:
        return ParsedCommand(name="", args=())
    return ParsedCommand(name=tokens[0].lower(), args=tuple(tokens[1:]))


def _parse_machine_id(parsed: ParsedCommand) -> int:
    if len(parsed.args) != 1:
        raise CommandError(f"Usage: {parsed.name} <id>")
    try:
        return int(parsed.args[0])
    except ValueError as exc:
        raise CommandError(
            f"Invalid machine id '{parsed.args[0]}': expected an integer."
        ) from exc


class CommandDispatcher:
    """Executes :class:`ParsedCommand` objects against a :class:`MachineManager`."""

    def __init__(self, manager: MachineManager) -> None:
        self._manager = manager

    def dispatch(self, text: str) -> CommandResult:
        try:
            parsed = parse_command(text)
        except CommandError as exc:
            return CommandResult(ActionKind.NONE, str(exc), is_error=True)

        if not parsed.name:
            return CommandResult(ActionKind.NONE, "")

        handler_name = f"_cmd_{parsed.name}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            return CommandResult(
                ActionKind.NONE,
                f"Unknown command: '{parsed.name}'. Type 'help' for a list of commands.",
                is_error=True,
            )

        try:
            return handler(parsed)
        except CommandError as exc:
            return CommandResult(ActionKind.NONE, str(exc), is_error=True)

    # -- individual command handlers -------------------------------------

    def _cmd_help(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.HELP, HELP_TEXT)

    def _cmd_list(self, parsed: ParsedCommand) -> CommandResult:
        machines = self._manager.list_machines()
        if not machines:
            return CommandResult(ActionKind.LIST, "No machines configured.")
        lines = [f"{'ID':<4} {'NAME':<18} {'STATUS'}"]
        for machine in machines:
            lines.append(f"{machine.machine_id:<4} {machine.name:<18} {machine.state.value}")
        return CommandResult(ActionKind.LIST, "\n".join(lines))

    def _cmd_select(self, parsed: ParsedCommand) -> CommandResult:
        machine_id = _parse_machine_id(parsed)
        if not self._manager.exists(machine_id):
            return CommandResult(
                ActionKind.NONE,
                f"Error: machine {machine_id} does not exist.",
                is_error=True,
            )
        return CommandResult(
            ActionKind.SELECT_MACHINE, f"Selected machine {machine_id}.", machine_id=machine_id
        )

    def _cmd_info(self, parsed: ParsedCommand) -> CommandResult:
        machine_id = _parse_machine_id(parsed)
        try:
            machine = self._manager.get(machine_id)
        except MachineNotFoundError as exc:
            return CommandResult(ActionKind.NONE, f"Error: {exc}", is_error=True)
        snap = machine.latest
        lines = [
            f"Machine {machine.machine_id}: {machine.name} [{machine.state.value}]",
            f"  Host:         {machine.config.host}:{machine.config.port}",
            f"  Hostname:     {snap.hostname or 'N/A'}",
            f"  OS:           {snap.os_name or 'N/A'}",
            f"  Kernel:       {snap.kernel or 'N/A'}",
            f"  Architecture: {snap.architecture or 'N/A'}",
            f"  CPU:          {snap.cpu_model or 'N/A'} ({snap.format_cpu()})",
            f"  RAM:          {snap.format_ram()}",
            f"  Disk:         {snap.disk_percent if snap.disk_percent is not None else 'N/A'}",
            f"  Uptime:       {snap.format_uptime()}",
            f"  IP:           {snap.ip_address or 'N/A'}",
            f"  Temp:         {snap.format_temp()}",
        ]
        if machine.last_error:
            lines.append(f"  Last error:   {machine.last_error}")
        return CommandResult(ActionKind.SHOW_INFO, "\n".join(lines), machine_id=machine_id)

    def _cmd_dashboard(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.SHOW_DASHBOARD, "Returned to dashboard.")

    def _cmd_refresh(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.REFRESH, "Refreshing telemetry...")

    def _cmd_reconnect(self, parsed: ParsedCommand) -> CommandResult:
        machine_id = _parse_machine_id(parsed)
        if not self._manager.exists(machine_id):
            return CommandResult(
                ActionKind.NONE,
                f"Error: machine {machine_id} does not exist.",
                is_error=True,
            )
        return CommandResult(
            ActionKind.RECONNECT, f"Reconnecting to machine {machine_id}...", machine_id=machine_id
        )

    def _cmd_clear(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.CLEAR, "")

    def _cmd_back(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.BACK, "")

    def _cmd_quit(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.QUIT, "Goodbye.")

    def _cmd_exit(self, parsed: ParsedCommand) -> CommandResult:
        return CommandResult(ActionKind.QUIT, "Goodbye.")
