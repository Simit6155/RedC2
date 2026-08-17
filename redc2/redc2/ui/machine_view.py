"""Machine detail screen: sidebar + stats/graphs + interactive terminal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from redc2.core.manager import MachineManager
from redc2.ui.machine_list import MachineList
from redc2.ui.telemetry import TelemetryGraphs
from redc2.ui.terminal import SSHTerminal


class MachineDetailScreen(Screen):
    """Detail/terminal view for a single selected machine."""

    DEFAULT_CSS = """
    MachineDetailScreen {
        layout: horizontal;
    }
    #detail-right {
        width: 1fr;
        height: 1fr;
    }
    #stats-panel {
        height: auto;
        border: solid $primary-darken-2;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("tab", "focus_next", "Switch panel"),
    ]

    def __init__(self, manager: MachineManager, machine_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._manager = manager
        self._machine_id = machine_id

    def compose(self) -> ComposeResult:
        machine = self._manager.get(self._machine_id)
        yield Header(show_clock=True)
        yield MachineList(self._manager, self._machine_id, id="machine-list")
        with Vertical(id="detail-right"):
            yield Static(self._stats_text(), id="stats-panel")
            yield TelemetryGraphs(machine, id="telemetry-graphs")
            yield SSHTerminal(self._manager, self._machine_id, id="ssh-terminal")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._manager.get(self._machine_id).name
        self.set_interval(2.0, self.refresh_panels)
        # Without this, Textual's default auto-focus lands on the machine
        # sidebar (mounted first) instead of the terminal, so keystrokes
        # go nowhere and it looks like typing does nothing.
        self.set_focus(self.query_one("#ssh-terminal", SSHTerminal))

    def _stats_text(self) -> str:
        machine = self._manager.get(self._machine_id)
        snap = machine.latest
        lines = [
            f"[bold]{machine.name}[/bold]  [dim]{machine.state.value}[/dim]",
            f"CPU       {snap.format_cpu()}",
            f"RAM       {snap.ram_used_gb:.1f} / {snap.ram_total_gb:.1f} GB"
            if snap.ram_used_gb is not None and snap.ram_total_gb is not None
            else "RAM       N/A",
            f"TEMP      {snap.format_temp()}",
            f"UPTIME    {snap.format_uptime()}",
        ]
        if machine.last_error:
            lines.append(f"[red]LAST ERROR: {machine.last_error}[/red]")
        return "\n".join(lines)

    def refresh_panels(self) -> None:
        try:
            stats = self.query_one("#stats-panel", Static)
            stats.update(self._stats_text())
            self.query_one(TelemetryGraphs).refresh_graphs()
        except Exception:  # noqa: BLE001 - screen may be transitioning away
            pass
