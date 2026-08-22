from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ListItem, ListView, Static

from redc2.core.manager import MachineManager

class MachineListItem(ListItem):
    def __init__(self, machine_id: int, label: str) -> None:
        super().__init__(Static(label))
        self.machine_id = machine_id

class MachineList(Vertical):
    DEFAULT_CSS = """
    MachineList {
        width: 28;
        border: solid $primary-darken-2;
    }
    MachineList > #machine-list-title {
        height: 1;
        background: $primary-darken-2;
        padding: 0 1;
    }
    MachineList ListView {
        height: 1fr;
    }
    """

    def __init__(self, manager: MachineManager, active_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._manager = manager
        self._active_id = active_id

    def compose(self) -> ComposeResult:
        yield Static("MACHINES", id="machine-list-title")
        yield ListView(*self._build_items(), id="machine-listview")

    def _build_items(self) -> list[MachineListItem]:
        items = []
        for machine in self._manager.list_machines():
            marker = ">" if machine.machine_id == self._active_id else " "
            label = f"{marker} {machine.machine_id} {machine.name}"
            items.append(MachineListItem(machine.machine_id, label))
        return items

    def refresh_list(self, active_id: int) -> None:
        self._active_id = active_id
        listview = self.query_one("#machine-listview", ListView)
        listview.clear()
        for item in self._build_items():
            listview.append(item)
