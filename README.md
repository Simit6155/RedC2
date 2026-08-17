# REDC2

A terminal-based SSH remote-management dashboard for your own machines.
Point it at machines you have SSH access to and get a live TUI with
system telemetry and an interactive SSH shell.

## Install

```bash
pip install redc2
```

## Configure

Create a `machines.toml` file:

```bash
mkdir config
```

`config/machines.toml`:

```toml
[[machines]]
name = "My-Server"
host = "192.168.1.100"
port = 22
username = "user"
password = "yourpassword"
allow_password_auth = true
use_agent = false
strict_host_key_checking = false
```

Add as many `[[machines]]` blocks as you want, one per machine.

## Run

```bash
redc2
```

Or point it at a config file somewhere else:

```bash
redc2 --config /path/to/machines.toml
```

## Commands

```
help              Show available commands
list              List all configured machines
select <id>       Open the detail/terminal view for a machine
info <id>         Show detailed telemetry for a machine
dashboard         Return to the main dashboard
refresh           Force an immediate telemetry refresh
reconnect <id>    Manually retry connecting to a machine
quit / exit       Close REDC2
```

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh dashboard |
| `Esc` | Back |
| `Tab` | Switch panels |
| `↑` / `↓` | Navigate machine list |
| `Enter` | Select machine |

## License

MIT
