# REDC2

REDC2 is a terminal based dashboard written in Python, it lets you manage your machines using Secure Shell (SSH).

## Requirements on the managed machine

For the dashboard to show live **CPU, RAM, and temperature** numbers
instead of `N/A`, each managed machine needs:

- **Python 3** installed on the target machines
- The **`psutil`** package installed for that Python:

  ```bash
  pip3 install psutil
  # or, on Debian/Ubuntu/Raspberry Pi OS:
  sudo apt install python3-psutil
  ```


## Quick start for Windows users:

1. Download the redc2.exe and the machines.toml.example file from the [Releases](../../releases) tab
2. Make sure they are in the same exact folder
3. Open machines.toml.example file, edit it with the real credentials and rename it to machines.toml
4. Run the exe file

# Please note that you should not use SSH key-file auth, use a normal SSH password

## Setting up the machines.toml (replace the credentials)

```toml
[[machines]]
name = "my-server"
host = "192.168.1.113"
port = 22
username = "myuser"
password = "mypassword_DONT_USE_SSH_KEY_FILE_AUTH"
allow_password_auth = true
use_agent = false
strict_host_key_checking = false
```

To add more machines simply copy paste the [[machines]] block, change the credentials though

## How to use it

When you type help in the mini terminal, the first terminal you see when you launch the program simply type 'help' to see the commands



