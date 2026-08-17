"""Dashboard widget: the main machine-overview table."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from redc2.core.machine import ConnectionState, Machine
from redc2.core.manager import MachineManager

_STATE_STYLE = {
    ConnectionState.ONLINE: "bold green",
    ConnectionState.OFFLINE: "dim white",
    ConnectionState.CONNECTING: "bold yellow",
    ConnectionState.ERROR: "bold red",
}


def _status_cell(machine: Machine) -> str:
    style = _STATE_STYLE.get(machine.state, "white")
    return f"[{style}]{machine.state.indicator} {machine.state.value}[/{style}]"


class DashboardView(Vertical):
    """Shows a summary table of every configured machine."""

    DEFAULT_CSS = """
    DashboardView {
        height: 1fr;
    }
    DashboardView DataTable {
        height: 1fr;
    }
    """

    machine_count = reactive(0)
    online_count = reactive(0)

    def __init__(self, manager: MachineManager, **kwargs) -> None:
        super().__init__(**kwargs)
        self._manager = manager

    def compose(self) -> ComposeResult:
        yield Static(self._summary_text(), id="dashboard-summary")
        yield DataTable(id="machine-table", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one("#machine-table", DataTable)
        table.add_columns("ID", "MACHINE", "STATUS", "CPU", "RAM", "TEMP")
        self.refresh_table()

    def _summary_text(self) -> str:
        total = self._manager.count()
        online = self._manager.online_count()
        return f"{online}/{total} MACHINES ONLINE"

    def refresh_table(self) -> None:
        """Rebuild the table contents from current manager state."""
        table = self.query_one("#machine-table", DataTable)
        table.clear()
        for machine in self._manager.list_machines():
            snap = machine.latest
            table.add_row(
                str(machine.machine_id),
                machine.name,
                _status_cell(machine),
                snap.format_cpu(),
                snap.format_ram(),
                snap.format_temp(),
                key=str(machine.machine_id),
            )
        summary = self.query_one("#dashboard-summary", Static)
        summary.update(self._summary_text())
