from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Sparkline

from redc2.core.machine import Machine

class TelemetryGraphs(Vertical):
    DEFAULT_CSS = """
    TelemetryGraphs {
        height: auto;
        border: solid $primary-darken-2;
        padding: 0 1;
    }
    TelemetryGraphs Label {
        color: $text-muted;
    }
    TelemetryGraphs Sparkline {
        height: 3;
        margin-bottom: 1;
    }
    """

    def __init__(self, machine: Machine, **kwargs) -> None:
        super().__init__(**kwargs)
        self._machine = machine

    def compose(self) -> ComposeResult:
        yield Label("CPU HISTORY")
        yield Sparkline([], id="cpu-spark", summary_function=max)
        yield Label("RAM HISTORY")
        yield Sparkline([], id="ram-spark", summary_function=max)
        yield Label("TEMPERATURE HISTORY")
        yield Sparkline([], id="temp-spark", summary_function=max)

    def refresh_graphs(self) -> None:
        cpu = self.query_one("#cpu-spark", Sparkline)
        ram = self.query_one("#ram-spark", Sparkline)
        temp = self.query_one("#temp-spark", Sparkline)
        cpu.data = list(self._machine.cpu_history) or [0.0]
        ram.data = list(self._machine.ram_history) or [0.0]
        temp.data = list(self._machine.temperature_history) or [0.0]
