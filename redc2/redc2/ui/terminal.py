"""Interactive SSH terminal widget.

Wraps a Paramiko shell channel inside a Textual widget. Reading from the
channel happens in a background thread (channel.recv is blocking even in
non-blocking mode without a select loop, so we poll it off the event
loop); output is pushed back into the widget via `call_from_thread`.

The remote shell echoes keystrokes and redraws prompts using raw VT100/
ANSI control sequences (cursor moves, line clears, colors, etc.). Naively
appending each network chunk as its own RichLog line breaks this badly -
a single echoed keystroke can arrive in its own TCP segment, so typing
"whoami" can end up rendered as one character per line. To display it
correctly we feed the raw byte stream into a `pyte` virtual screen, which
interprets those control sequences the same way a real terminal emulator
would, and render pyte's resulting screen buffer into the RichLog.
"""

from __future__ import annotations

import logging
import threading
import time

import pyte
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from redc2.core.machine import Machine
from redc2.core.manager import MachineManager
from redc2.core.ssh import SSHConnectionError

logger = logging.getLogger("redc2.terminal")

# Control characters we translate into channel bytes.
_CTRL_C = b"\x03"
_CTRL_D = b"\x04"

# Default PTY size used until the widget is mounted and we know its real
# size; kept in sync with resize_pty() below.
_DEFAULT_COLS = 80
_DEFAULT_ROWS = 24

# How often (seconds) we re-render the pyte screen into the RichLog.
# Coalescing bursts of output (e.g. a fast `cat` of a big file) into a
# single redraw keeps the UI responsive instead of re-rendering per byte.
_REDRAW_INTERVAL = 0.03


def _pyte_char_style(char) -> Style:
    """Convert a pyte screen cell's attributes into a Rich style."""
    fg = None if char.fg == "default" else char.fg
    bg = None if char.bg == "default" else char.bg
    return Style(
        color=fg,
        bgcolor=bg,
        bold=char.bold,
        italic=char.italics,
        underline=char.underscore,
        reverse=char.reverse,
        strike=char.strikethrough,
    )


class SSHTerminal(Vertical):
    """An interactive remote shell backed by a Paramiko channel."""

    DEFAULT_CSS = """
    SSHTerminal {
        height: 1fr;
        border: solid $primary-darken-2;
    }
    SSHTerminal > #terminal-title {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }
    SSHTerminal > RichLog {
        height: 1fr;
        background: $surface-darken-2;
    }
    """

    can_focus = True
    connected = reactive(False)

    def __init__(self, manager: MachineManager, machine_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._manager = manager
        self._machine_id = machine_id
        self._channel = None
        self._reader_thread: threading.Thread | None = None
        self._stop_reading = threading.Event()
        self._has_focus = False
        self._warned_not_connected = False

        # Virtual screen that interprets the remote shell's VT100/ANSI
        # output the way a real terminal would.
        self._cols = _DEFAULT_COLS
        self._rows = _DEFAULT_ROWS
        self._screen = pyte.HistoryScreen(self._cols, self._rows, history=2000)
        self._stream = pyte.ByteStream(self._screen)
        self._stream_lock = threading.Lock()

        self._last_redraw = 0.0
        self._redraw_pending = False

    @property
    def machine(self) -> Machine:
        return self._manager.get(self._machine_id)

    def compose(self) -> ComposeResult:
        yield Static(f"SSH TERMINAL — {self.machine.name}", id="terminal-title")
        yield RichLog(id="terminal-log", markup=False, wrap=False, max_lines=5000)

    def on_mount(self) -> None:
        self.start_shell()
        # Size the PTY (and our virtual screen) to match the actual widget
        # once it's laid out, instead of leaving it hardcoded at 80x24.
        self.call_after_refresh(self._sync_size_to_widget)

    def on_unmount(self) -> None:
        self.stop_shell()

    def on_resize(self, event: events.Resize) -> None:
        self._sync_size_to_widget()

    def on_focus(self) -> None:
        """Terminal gained focus."""
        self._has_focus = True

    def on_blur(self) -> None:
        """Terminal lost focus."""
        self._has_focus = False

    def start_shell(self) -> None:
        """Open the interactive shell channel and start the reader thread."""
        log = self.query_one("#terminal-log", RichLog)
        session = self._manager.get_session(self._machine_id)
        if not session.is_connected:
            log.write("[not connected — use 'reconnect' first]")
            self.connected = False
            return
        try:
            self._channel = session.open_shell(width=self._cols, height=self._rows)
        except SSHConnectionError as exc:
            log.write(f"[error opening shell: {exc}]")
            self.connected = False
            return

        self.connected = True
        self._stop_reading.clear()
        self._reader_thread = threading.Thread(
            target=self._read_loop, name=f"ssh-reader-{self._machine_id}", daemon=True
        )
        self._reader_thread.start()

    def stop_shell(self) -> None:
        self._stop_reading.set()
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:  # noqa: BLE001
                pass
            self._channel = None
        self.connected = False

    def _sync_size_to_widget(self) -> None:
        """Resize the pyte screen and the remote PTY to match our size."""
        log = self.query_one("#terminal-log", RichLog)
        cols = max(log.size.width, 10)
        rows = max(log.size.height, 5)
        if cols == self._cols and rows == self._rows:
            return
        self._cols, self._rows = cols, rows
        with self._stream_lock:
            self._screen.resize(rows, cols)
        self.resize_pty(cols, rows)
        self._redraw()

    def _read_loop(self) -> None:
        """Background thread: poll the channel and forward output to the UI."""
        channel = self._channel
        if channel is None:
            return
        while not self._stop_reading.is_set():
            try:
                if channel.closed:
                    break
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    self.app.call_from_thread(self._feed, data)
                elif channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096)
                    self.app.call_from_thread(self._feed, data)
                else:
                    time.sleep(0.02)
            except OSError:
                break
            except Exception:  # noqa: BLE001
                logger.exception("Terminal reader error for machine %d", self._machine_id)
                break
        self.app.call_from_thread(self._on_disconnected)

    def _feed(self, data: bytes) -> None:
        """Feed raw bytes into the virtual screen and schedule a redraw.

        Runs on the UI thread (via call_from_thread), so it's safe to touch
        Textual widgets here; the pyte screen itself is also guarded by a
        lock since _sync_size_to_widget can resize it concurrently.
        """
        with self._stream_lock:
            self._stream.feed(data)

        now = time.monotonic()
        if now - self._last_redraw >= _REDRAW_INTERVAL:
            self._redraw()
        elif not self._redraw_pending:
            # Coalesce a fast burst of chunks into a single redraw shortly
            # after the last one, instead of redrawing on every chunk.
            self._redraw_pending = True
            delay = max(_REDRAW_INTERVAL - (now - self._last_redraw), 0.0)
            self.set_timer(delay, self._redraw)

    def _redraw(self) -> None:
        """Render the current pyte screen buffer into the RichLog."""
        self._redraw_pending = False
        self._last_redraw = time.monotonic()
        try:
            log = self.query_one("#terminal-log", RichLog)
        except Exception:  # noqa: BLE001 - widget may not be mounted yet
            return

        with self._stream_lock:
            lines = list(self._screen.display)
            buffer = self._screen.buffer
            cursor = self._screen.cursor
            self._screen.dirty.clear()

        log.clear()
        for y, line in enumerate(lines):
            row = buffer[y]
            text = Text()
            for x, ch in enumerate(line):
                cell = row[x]
                text.append(ch, style=_pyte_char_style(cell))
            if not cursor.hidden and y == cursor.y and cursor.x < len(line):
                text.stylize(Style(reverse=True), cursor.x, cursor.x + 1)
            log.write(text, scroll_end=True)

    def _on_disconnected(self) -> None:
        self.connected = False
        log = self.query_one("#terminal-log", RichLog)
        log.write("\n[connection to remote shell closed]")
        self.machine.mark_offline()

    def send_text(self, text: str) -> None:
        if self._channel is None or self._channel.closed:
            return
        try:
            self._channel.send(text.encode("utf-8", errors="replace"))
        except OSError:
            self._on_disconnected()

    def on_key(self, event: events.Key) -> None:
        """Forward keystrokes directly to the remote shell."""
        if self._channel is None or self._channel.closed or not self.connected:
            # Give visible feedback instead of silently swallowing the
            # keystroke - otherwise it looks like typing does nothing.
            if not self._warned_not_connected:
                self._warned_not_connected = True
                try:
                    log = self.query_one("#terminal-log", RichLog)
                    log.write("[not connected yet - keystrokes are ignored until the shell opens]")
                except Exception:  # noqa: BLE001
                    pass
            return
        self._warned_not_connected = False

        # Always prevent default to ensure we handle all keys
        event.stop()
        event.prevent_default()

        # Handle special keys
        try:
            if event.key == "enter":
                self.send_text("\r")
            elif event.key == "ctrl+c":
                self._channel.send(_CTRL_C)
            elif event.key == "ctrl+d":
                self._channel.send(_CTRL_D)
            elif event.key == "backspace":
                self.send_text("\x7f")
            elif event.key == "tab":
                self.send_text("\t")
            elif event.key == "escape":
                self.send_text("\x1b")
            elif event.key in ("up", "down", "left", "right"):
                arrows = {"up": "A", "down": "B", "right": "C", "left": "D"}
                self.send_text(f"\x1b[{arrows[event.key]}")
            elif event.character:
                # Send all printable characters, including special ones
                self.send_text(event.character)
        except Exception as exc:
            logger.warning("Failed to send key %s: %s", event.key, exc)

    def resize_pty(self, width: int, height: int) -> None:
        if self._channel is not None and not self._channel.closed:
            try:
                self._channel.resize_pty(width=max(width, 10), height=max(height, 5))
            except Exception:  # noqa: BLE001
                pass
