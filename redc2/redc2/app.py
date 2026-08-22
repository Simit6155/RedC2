from __future__ import annotations

import asyncio
import logging

from textual.app import App, ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Footer, Header, Input, RichLog, Static
from textual.reactive import reactive

from redc2.commands.parser import ActionKind, CommandDispatcher, CommandResult
from redc2.core.config import AppConfig
from redc2.core.machine import ConnectionState
from redc2.core.manager import MachineManager
from redc2.ui.dashboard import DashboardView
from redc2.ui.machine_view import MachineDetailScreen
from redc2.terminal.ssh_terminal import SSHTerminalWidget

logger = logging.getLogger("redc2.app")

class REDC2App(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #dashboard-container {
        height: 1fr;
    }

    #output-log {
        height: 8;
        border-top: solid $primary-darken-1;
        background: $surface-darken-1;
    }

    #command-input {
        dock: bottom;
        height: 1;
        border: none;
        padding: 0 1;
    }

    #terminal-container {
        display: none;
        height: 13;
        border-top: solid $primary-darken-2;
    }

    #terminal-container.visible {
        display: block;
    }
    """

    TITLE = "REDC2 - SSH Dashboard & Terminal"
    SUB_TITLE = "Press Ctrl+T for terminal"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "do_refresh", "Refresh"),
        ("escape", "go_back", "Back"),
        ("ctrl+t", "toggle_terminal", "Terminal"),
        ("ctrl+c", "quit", "Exit"),
    ]

    def __init__(self, config: AppConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_data = config
        self.manager = MachineManager(config)
        self.dispatcher = CommandDispatcher(self.manager)
        self._telemetry_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._terminal_widget: SSHTerminalWidget | None = None
        self._terminal_visible = False
        self._current_machine_id: int | None = None
        self._terminal_seq = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            with Vertical(id="dashboard-container"):
                yield DashboardView(self.manager, id="dashboard-view")
                yield RichLog(id="output-log", markup=True, wrap=True)

            yield Container(id="terminal-container")

            yield Input(placeholder="redc2> type 'help' for commands", id="command-input")

        yield Footer()

    def on_mount(self) -> None:
        try:
            count = self.manager.count()
            self.sub_title = f"{count} machine(s) configured | Press Ctrl+T for terminal"

            log = self.query_one("#output-log", RichLog)
            log.write("[bold cyan]╔════════════════════════════════════╗[/bold cyan]")
            log.write("[bold cyan]║           REDC2 STARTED            ║[/bold cyan]")
            log.write("[bold cyan]╚════════════════════════════════════╝[/bold cyan]")
            log.write("[green]✓[/green] Dashboard ready")
            log.write("[cyan]→[/cyan] Select a machine from the list")
            log.write("[cyan]→[/cyan] Press [bold]Ctrl+T[/bold] to open SSH terminal")
            log.write("[dim]Type 'help' for available commands[/dim]")

            self.query_one("#command-input", Input).focus()

            for machine in self.manager.list_machines():
                self.run_worker(
                    self._connect_and_log(machine.machine_id),
                    exclusive=False,
                    group="connect",
                )
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

        except Exception as e:
            logger.error(f"Failed to mount REDC2App: {e}")
            raise

    async def on_unmount(self) -> None:
        if self._telemetry_task:
            self._telemetry_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._terminal_widget:
            self._terminal_widget.disconnect()
        await self.manager.shutdown()

    async def _connect_and_log(self, machine_id: int) -> None:
        await self.manager.connect(machine_id)
        machine = self.manager.get(machine_id)
        if machine.state == ConnectionState.ONLINE:
            self._log(f"[green]✓ {machine.name} connected[/green]")
        elif machine.last_error:
            self._log(f"[red]✗ {machine.name}: {machine.last_error}[/red]")
        self._refresh_dashboard_safe()

    async def _telemetry_loop(self) -> None:
        interval = self.config_data.refresh_interval
        while True:
            try:
                await asyncio.sleep(interval)
                for machine in self.manager.list_machines():
                    if machine.state == ConnectionState.ONLINE:
                        await self.manager.poll_telemetry(machine.machine_id)
                self._refresh_dashboard_safe()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Telemetry loop error")

    async def _reconnect_loop(self) -> None:
        next_attempt_at: dict[int, float] = {}
        loop = asyncio.get_event_loop()
        while True:
            try:
                await asyncio.sleep(1.0)
                now = loop.time()
                for machine in self.manager.list_machines():
                    if machine.state not in (ConnectionState.OFFLINE, ConnectionState.ERROR):
                        continue
                    if machine.reconnect_attempts >= self.config_data.max_reconnect_attempts:
                        continue
                    ready_at = next_attempt_at.get(machine.machine_id, 0.0)
                    if now < ready_at:
                        continue
                    delay = self.manager.next_backoff_delay(machine.machine_id)
                    next_attempt_at[machine.machine_id] = now + delay
                    await self.manager.reconnect_with_backoff(machine.machine_id)
                    self._refresh_dashboard_safe()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Reconnect loop error")

    def _refresh_dashboard_safe(self) -> None:
        try:
            self.query_one(DashboardView).refresh_table()
        except Exception:
            pass

    def _log(self, message: str) -> None:
        try:
            self.query_one("#output-log", RichLog).write(message)
        except Exception:
            logger.warning(f"Failed to log message: {message}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        text = event.value
        if not text.strip():
            event.input.value = ""
            return

        self._log(f"[dim]redc2>[/dim] {text}")
        event.input.value = ""
        result = self.dispatcher.dispatch(text)
        self._handle_result(text, result)

    def _handle_result(self, raw_text: str, result: CommandResult) -> None:
        log = self.query_one("#output-log", RichLog)

        if result.message:
            style = "bold red" if result.is_error else "green"
            msg = f"[{style}]{result.message}[/{style}]"
            log.write(msg)

        if result.action is ActionKind.QUIT:
            self.exit()
        elif result.action is ActionKind.CLEAR:
            log.clear()
        elif result.action in (ActionKind.SHOW_DASHBOARD,):
            if isinstance(self.screen, MachineDetailScreen):
                self.pop_screen()
            self._refresh_dashboard_safe()
        elif result.action is ActionKind.REFRESH:
            self._refresh_dashboard_safe()
        elif result.action is ActionKind.SELECT_MACHINE and result.machine_id is not None:
            self._current_machine_id = result.machine_id
            self._create_terminal_widget()
            self._log(f"[cyan]→ Selected machine ID {result.machine_id}[/cyan]")
            self.push_screen(MachineDetailScreen(self.manager, result.machine_id))
        elif result.action is ActionKind.RECONNECT and result.machine_id is not None:
            self.run_worker(
                self._manual_reconnect(result.machine_id), group="connect", exclusive=False
            )
        elif result.action is ActionKind.BACK:
            if isinstance(self.screen, MachineDetailScreen):
                self.pop_screen()

    async def _manual_reconnect(self, machine_id: int) -> None:
        machine = self.manager.get(machine_id)
        machine.reconnect_attempts = 0
        await self.manager.connect(machine_id)
        if machine.state == ConnectionState.ONLINE:
            self._log(f"[green]✓ {machine.name} reconnected[/green]")
        elif machine.last_error:
            self._log(f"[red]✗ {machine.name}: {machine.last_error}[/red]")
        self._refresh_dashboard_safe()

    def _create_terminal_widget(self) -> None:
        if self._current_machine_id is None:
            return

        machine = self.manager.get(self._current_machine_id)
        if machine is None:
            return

        if self._terminal_widget:
            self._terminal_widget.disconnect()

        container = self.query_one("#terminal-container", Container)

        for child in list(container.children):
            child.remove()

        self._terminal_seq += 1
        self._terminal_widget = SSHTerminalWidget(machine, id=f"ssh-terminal-{self._terminal_seq}")
        container.mount(self._terminal_widget)

    def action_quit(self) -> None:
        if self._terminal_widget:
            self._terminal_widget.disconnect()
        self.exit()

    def action_do_refresh(self) -> None:
        self._refresh_dashboard_safe()

    def action_toggle_terminal(self) -> None:
        container = self.query_one("#terminal-container", Container)

        if self._current_machine_id is None:
            self._log("[yellow]⚠ Please select a machine first[/yellow]")
            return

        if not self._terminal_visible:
            if not self._terminal_widget:
                self._create_terminal_widget()
            container.add_class("visible")
            self._terminal_visible = True
            self._log("[green]✓ Terminal opened[/green]")
            if self._terminal_widget and self._terminal_widget._input:
                self._terminal_widget._input.focus()
        else:
            container.remove_class("visible")
            self._terminal_visible = False
            self._log("[cyan]→ Terminal hidden[/cyan]")
            self.query_one("#command-input", Input).focus()

    def action_go_back(self) -> None:
        if isinstance(self.screen, MachineDetailScreen):
            self.pop_screen()
        else:
            self.query_one("#command-input", Input).focus()
