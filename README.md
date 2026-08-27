# REDC2

REDC2 is a terminal-based dashboard, written in Python, for managing multiple machines over SSH.

## Features

- **Multi-machine dashboard** — see all your configured machines and their connection status (connected / disconnected / error) at a glance
- **Live telemetry per machine** — CPU usage, RAM usage, disk usage, temperature, uptime, IP address, OS, kernel, and architecture
- **Built-in SSH terminal** — open a real terminal session to any machine directly from the dashboard, no need to alt-tab to another SSH client
- **Command-driven navigation** — a small command interface (`list`, `select`, `info`, `refresh`, `reconnect`, etc.) for moving between machines and views without touching the mouse
- **Auto-reconnect handling** — manually or automatically retry connections to machines that drop
- **Simple TOML config** — machines are defined in a single `machines.toml` file, no database or setup wizard required
- **Cross-platform client** — runs from source with Python, or as a standalone `.exe` on Windows via the Releases page

## Demo video
[▶ Click here to download the demo video](https://github.com/Simit6155/RedC2/blob/main/2026-08-24%2017-04-27.mkv)

## Requirements on the managed machine

**The managed machine must be Linux.**

For the dashboard to show live CPU, RAM, and temperature numbers instead of `N/A`, each managed machine needs:

- Python 3 installed
- The `psutil` package installed:

```bash
pip3 install psutil
# or, on Debian/Ubuntu/Raspberry Pi OS:
sudo apt install python3-psutil
```

**Still showing `N/A` after installing psutil?**
Your machine likely has more than one `python3` installed, and SSH isn't using the one you installed psutil into. REDC2 tries a few common python paths automatically, but if it still fails, check manually:

```bash
ssh user@host 'which python3; python3 -c "import psutil"'
```

If that fails, install psutil directly for that exact python path shown above, e.g.:

```bash
sudo /usr/bin/python3 -m pip install psutil
```

## Installation

### From PyPI

```bash
pip install redc2
redc2
```

### Windows (prebuilt executable)

1. Download `redc2.exe` and `machines.toml.example` from the [Releases](https://github.com/Simit6155/RedC2/releases) page
2. Put them in the same folder
3. Open `machines.toml.example`, fill in your real credentials, and rename it to `machines.toml`
4. Run `redc2.exe`

## Configuration

Machines are defined in `machines.toml`. Use a normal SSH password, not a key file — key-file auth is not supported.

```toml
[[machines]]
name = "my-server"
host = "192.168.1.113"
port = 22
username = "myuser"
password = "mypassword"
allow_password_auth = true
use_agent = false
strict_host_key_checking = false
```

To add more machines, copy the `[[machines]]` block again with new credentials.

## Usage

Launch REDC2 and you'll land on the mini terminal. Type `help` to see the available commands:

| Command          | Description                              |
|------------------|-------------------------------------------|
| `help`           | Show the list of commands                 |
| `list`           | List all configured machines              |
| `select <id>`    | Open the detail/terminal view for a machine |
| `info <id>`      | Show detailed telemetry for a machine     |
| `dashboard`      | Return to the main dashboard              |
| `refresh`        | Force an immediate telemetry refresh      |
| `reconnect <id>` | Manually retry connecting to a machine    |
| `clear`          | Clear the command output log              |
| `back`           | Go back to the previous view              |
| `quit` / `exit`  | Close REDC2                               |
