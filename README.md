# REDC2

A terminal dashboard for managing your home-lab machines over SSH. See all your machines' status, get live telemetry, and open an SSH terminal to any of them -- all from one screen.

## Quick Start (Windows)

1. Download `redc2.exe` and `machines.toml.example` from [Releases](../../releases)
2. Put both files in the same folder
3. Rename `machines.toml.example` to `machines.toml` and edit it with your machine's info (see below)
4. Double-click `redc2.exe`

## Setting up machines.toml

```toml
[[machines]]
name = "my-server"
host = "192.168.1.113"
port = 22
username = "myuser"
key_file = "~/.ssh/id_ed25519"
```

Add more machines by copy-pasting another `[[machines]]` block. That's it.

If you'd rather log in with a password instead of an SSH key, add:
```toml
allow_password_auth = true
password = "yourpassword"
```

## Controls

- `Ctrl+T` — open terminal for selected machine
- `r` — refresh
- `q` — quit

## Install via pip instead

```bash
pip install redc2
redc2 --config machines.toml
```

## License

MIT
