"""SSH Terminal widget for interactive SSH sessions."""

from __future__ import annotations

import asyncio
import logging
import paramiko
from typing import Callable

from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static
from textual.app import ComposeResult
from textual.reactive import reactive

logger = logging.getLogger("redc2.terminal")


class SSHTerminalWidget(Container):
    """An embedded SSH terminal widget."""
    
    DEFAULT_CSS = """
    SSHTerminalWidget {
        height: 12;
        border: solid $primary-darken-1;
        background: $surface-darken-2;
    }
    
    SSHTerminalWidget > #terminal-header {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        dock: top;
        text-align: left;
    }
    
    SSHTerminalWidget > #terminal-output {
        height: 1fr;
        overflow-y: auto;
    }
    
    SSHTerminalWidget > #terminal-input {
        height: 1;
        dock: bottom;
    }
    """
    
    def __init__(self, machine_config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.machine_config = machine_config
        self.ssh_client: paramiko.SSHClient | None = None
        self.channel = None
        self._output_log: RichLog | None = None
        self._input: Input | None = None
        self._read_task: asyncio.Task | None = None
        self.connected = False
    
    def compose(self) -> ComposeResult:
        yield Static(f"⊟ SSH TERMINAL - {self.machine_config.name}", id="terminal-header")
        yield RichLog(id="terminal-output", markup=True, wrap=True)
        yield Input(placeholder="type command and press Enter...", id="terminal-input")
    
    def on_mount(self) -> None:
        self._output_log = self.query_one("#terminal-output", RichLog)
        self._input = self.query_one("#terminal-input", Input)
        self._output_log.write("[yellow]Connecting...[/yellow]\n")
        self.run_worker(self._connect_ssh(), exclusive=True)
    
    async def _connect_ssh(self) -> None:
        """Connect to SSH server."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with configured credentials
            if self.machine_config.key_file:
                self.ssh_client.connect(
                    self.machine_config.host,
                    port=self.machine_config.port,
                    username=self.machine_config.username,
                    key_filename=self.machine_config.key_file,
                    timeout=self.machine_config.connection_timeout or 8.0,
                    look_for_keys=True,
                    allow_agent=self.machine_config.use_agent,
                )
            else:
                self.ssh_client.connect(
                    self.machine_config.host,
                    port=self.machine_config.port,
                    username=self.machine_config.username,
                    password=self.machine_config.password,
                    timeout=self.machine_config.connection_timeout or 8.0,
                    allow_agent=self.machine_config.use_agent,
                )
            
            # Open interactive shell
            self.channel = self.ssh_client.invoke_shell(term_type="xterm-256color")
            self.channel.settimeout(0.1)
            self.connected = True
            
            if self._output_log:
                self._output_log.write("[green]✓ Connected[/green]\n")
            
            # Start reading from channel
            self._read_task = asyncio.create_task(self._read_ssh_output())
            
            if self._input:
                self._input.focus()
        
        except Exception as e:
            self.connected = False
            if self._output_log:
                self._output_log.write(f"[red]✗ Connection failed: {str(e)}[/red]\n")
            logger.error(f"SSH connection failed: {e}")
    
    async def _read_ssh_output(self) -> None:
        """Continuously read output from SSH channel."""
        while self.connected and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096)
                    if data:
                        # Decode and display output
                        text = data.decode("utf-8", errors="replace")
                        if self._output_log:
                            # Remove terminal control sequences for cleaner display
                            clean_text = text.replace("\r", "")
                            self._output_log.write(clean_text)
                
                await asyncio.sleep(0.05)  # Non-blocking read
            
            except Exception as e:
                if self.connected:
                    logger.debug(f"SSH read error: {e}")
                await asyncio.sleep(0.1)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        if event.input.id != "terminal-input":
            return
        
        command = event.value
        
        if not self.connected or not self.channel:
            if self._output_log:
                self._output_log.write("[red]✗ Not connected[/red]\n")
            event.input.value = ""
            return
        
        if not command.strip():
            event.input.value = ""
            return
        
        try:
            # Show what user is typing
            if self._output_log:
                self._output_log.write(f"[cyan]$ {command}[/cyan]\n")
            
            # Send command to SSH channel
            self.channel.send(command + "\n")
            event.input.value = ""  # Clear input after sending
        except Exception as e:
            if self._output_log:
                self._output_log.write(f"[red]✗ Error: {e}[/red]\n")
            event.input.value = ""
            logger.error(f"SSH send error: {e}")
    
    def disconnect(self) -> None:
        """Disconnect SSH session."""
        self.connected = False
        if self._read_task:
            self._read_task.cancel()
        if self.channel:
            self.channel.close()
        if self.ssh_client:
            self.ssh_client.close()
