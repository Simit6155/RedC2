# REDC2

**REDC2** is a terminal-based SSH remote-management dashboard for your own
machines. It's built for personal / home-lab use: point it at a couple of
boxes you own (a Debian laptop, a Raspberry Pi, whatever), and get a live,
keyboard-driven TUI with system telemetry, history graphs, and an
interactive SSH shell — all in one screen.

REDC2 talks to your machines using standard, authenticated **SSH** (via
[Paramiko](https://www.paramiko.org/)). It does not implement a custom
remote-access protocol, persistence, stealth, or anything designed to look
or behave like malware. It's an admin dashboard, not a C2 framework —
the name is a nod to "remote deployment/control," not an implication of
anything offensive.

---

## 1. What REDC2 is

- A single Textual application that runs in your terminal.
- A dashboard listing every configured machine with live status, CPU,
  RAM, and temperature.
- A per-machine detail view with history graphs and an interactive SSH
  terminal.
- A small command language (`list`, `select`, `info`, `reconnect`, ...)
  you type into the built-in command bar.

It is **not**:

- A reverse shell or C2 framework.
- A vulnerability scanner or exploitation tool.
- A tool for accessing machines you don't own or control.

## 2. Features

- Live dashboard: machine ID, name, connection status, CPU %, RAM %, temp.
- Per-machine detail screen: stats panel, CPU/RAM/temperature sparkline
  graphs (last 60 samples), and an interactive SSH terminal.
- Command bar with `help`, `list`, `select`, `info`, `dashboard`,
  `refresh`, `reconnect`, `clear`, `back`, `quit` / `exit`.
- Keyboard shortcuts: `q` quit, `r` refresh, `Esc` back, `Tab` switch
  panels, arrow keys to navigate machine lists.
- Reusable SSH connections — REDC2 does not open a new connection per
  command or per telemetry poll.
- Background telemetry polling and automatic reconnection with capped
  exponential backoff; you can also force `reconnect <id>` manually.
- One offline/broken machine never blocks or crashes the rest of the UI.
- SSH key, SSH agent, and (optional, off by default) interactive password
  authentication. No plaintext passwords in configuration, ever.
- Host key verification is on by default — REDC2 does not silently trust
  unknown hosts.
- File-based logging (never logs credentials).

## 3. Architecture

```
UI (Textual)
   ↓
Command layer (redc2/commands/parser.py)
   ↓
MachineManager (redc2/core/manager.py)
   ↓
SSHSession (redc2/core/ssh.py, Paramiko)
   ↓
Remote machine
```

- **UI never touches Paramiko directly.** Widgets call into
  `MachineManager`, which owns one `SSHSession` per machine.
- **`MachineManager`** is the single source of truth for machine state
  (`OFFLINE` / `CONNECTING` / `ONLINE` / `ERROR`), owns the reconnect/
  backoff logic, and drives telemetry polling.
- **`SSHSession`** is the only module that imports Paramiko. It handles
  authentication (key → agent → optional password), host key
  verification, running one-off commands, and opening interactive shell
  channels.
- **Telemetry** is collected by running a small, dependency-light Python
  probe over the existing SSH connection (uses `psutil` on the remote
  side if present, falls back to `/proc` and `/sys` otherwise) — no new
  connection is opened per poll.

```
redc2/
├── redc2/
│   ├── __main__.py        CLI entry point
│   ├── app.py              Textual App: wiring, background workers
│   │
│   ├── core/
│   │   ├── manager.py       MachineManager: connect/reconnect/telemetry
│   │   ├── machine.py       Machine, ConnectionState, TelemetrySnapshot
│   │   ├── ssh.py           SSHSession (Paramiko)
│   │   ├── telemetry.py     Remote system-stat collection & parsing
│   │   └── config.py        TOML config loading & validation
│   │
│   ├── commands/
│   │   └── parser.py        Command parsing/dispatch (UI-agnostic)
│   │
│   └── ui/
│       ├── dashboard.py     Main machine table
│       ├── machine_list.py  Sidebar machine list (detail screen)
│       ├── machine_view.py  Detail screen (stats + graphs + terminal)
│       ├── telemetry.py     Sparkline graphs
│       └── terminal.py      Interactive SSH terminal widget
│
├── config/
│   └── machines.toml.example
├── tests/
├── README.md
├── pyproject.toml
└── LICENSE
```

## 4. Installation

Requires Python 3.11+.

```bash
git clone <this-repo> redc2
cd redc2
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -e .
```

## 5. Installing dependencies

`pip install -e .` pulls in the runtime dependencies declared in
`pyproject.toml`: `textual`, `rich`, `paramiko`, `psutil`, `tomli-w`.

For running the test suite:

```bash
pip install -e ".[dev]"
```

## 6. Setting up SSH on Debian

On the Debian machine you want to manage:

```bash
sudo apt update
sudo apt install openssh-server
sudo systemctl enable --now ssh
```

Confirm it's listening: `sudo ss -tlnp | grep :22`.

## 7. Setting up SSH on Raspberry Pi OS

```bash
sudo apt update
sudo apt install openssh-server
sudo systemctl enable --now ssh
```

Or, when flashing the SD card with Raspberry Pi Imager, enable SSH in the
imager's advanced options before first boot.

## 8. Creating SSH keys

On the machine running REDC2 (your controller):

```bash
ssh-keygen -t ed25519 -C "redc2" -f ~/.ssh/id_ed25519
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@192.168.1.100
```

Repeat `ssh-copy-id` for each managed machine. Test manually once with
plain `ssh` before pointing REDC2 at a new machine — this is also how the
host key gets added to your `known_hosts` file, which REDC2 relies on for
verification.

## 9. Configuring `machines.toml`

Copy the example config and edit it:

```bash
mkdir -p config
cp config/machines.toml.example config/machines.toml
```

```toml
[settings]
log_file = "~/.redc2/redc2.log"
refresh_interval = 2.0
connection_timeout = 8.0
max_reconnect_attempts = 5
reconnect_backoff_base = 2.0
reconnect_backoff_max = 60.0

[[machines]]
name = "Debian-Laptop"
host = "192.168.1.100"
port = 22
username = "user"
key_file = "~/.ssh/id_ed25519"
use_agent = true
allow_password_auth = false
strict_host_key_checking = true

[[machines]]
name = "Raspberry-Pi"
host = "192.168.1.101"
port = 22
username = "pi"
key_file = "~/.ssh/id_ed25519"
use_agent = true
allow_password_auth = false
strict_host_key_checking = true
```

Machine IDs are assigned by position, starting at **0**.

REDC2 looks for a config file in this order: `--config <path>`,
`./config/machines.toml`, `./machines.toml`, `~/.redc2/machines.toml`.

**Never put a plaintext password in this file.** Authentication order is:
explicit `key_file` → SSH agent (if `use_agent = true`) → interactive
password prompt (only if `allow_password_auth = true`).

## 10. Running REDC2

```bash
python -m redc2
# or, after `pip install -e .`:
redc2
# or with an explicit config path:
redc2 --config /path/to/machines.toml
```

## 11. Keyboard controls

| Key      | Action                          |
|----------|----------------------------------|
| `q`      | Quit                             |
| `r`      | Refresh dashboard                |
| `Esc`    | Back (pop the detail screen)     |
| `Tab`    | Switch focus between panels      |
| `↑` / `↓`| Navigate machine list            |
| `Enter`  | Select highlighted machine       |

Inside the SSH terminal panel, keystrokes go straight to the remote shell
(including `Ctrl+C` and `Ctrl+D`) rather than triggering app shortcuts.

## 12. Commands

Typed into the command bar at the bottom of the dashboard:

```
help              Show available commands
list              List all configured machines
select <id>       Open the detail/terminal view for a machine
info <id>         Show detailed telemetry for a machine
dashboard         Return to the main dashboard
refresh           Force an immediate telemetry refresh
reconnect <id>    Manually retry connecting to a machine
clear             Clear the command output log
back              Go back to the previous view
quit / exit       Close REDC2
```

Example session:

```
redc2> list
ID   NAME               STATUS
0    Debian-Laptop      ONLINE
1    Raspberry-Pi       ONLINE

redc2> select 0
redc2> info 0
redc2> reconnect 1
redc2> quit
```

## 13. Security considerations

- REDC2 uses plain authenticated SSH — no custom protocol, no reverse
  shells, no callbacks.
- **No plaintext passwords in config.** Prefer SSH keys or an agent.
  Interactive password auth is opt-in per machine and is never logged.
- **Host key verification is on by default** (`strict_host_key_checking =
  true`). REDC2 will not silently trust an unknown host key; you'll see a
  clear error telling you to verify and add it (e.g. via one manual `ssh`
  connection or `ssh-keyscan`). Only disable this if you understand the
  risk (e.g. an isolated lab network).
- Logs never contain passwords, private key material, or other
  authentication secrets.
- Reconnection attempts are capped (`max_reconnect_attempts`) with
  exponential backoff — REDC2 will not hammer a machine that's down.
- REDC2 does not scan networks, does not attempt privilege escalation,
  and does not deploy payloads. It only does what an authenticated SSH
  session already allows you to do by hand.

## 14. Project structure

See [Architecture](#3-architecture) above for the full tree.

## 15. Development / testing

```bash
pip install -e ".[dev]"
pytest
```

Tests cover command parsing, machine indexing/manager behavior,
configuration loading and validation, telemetry JSON parsing, connection
state transitions, and the SSH authentication flow — all with mocked
Paramiko objects, so no real SSH server is required to run the suite.

```bash
pytest -q          # quiet run
pytest -k ssh       # just the SSH-layer tests
```

---

## License

MIT — see [LICENSE](LICENSE).
