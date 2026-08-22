# REDC2

REDC2 is a terminal based dashboard written in Python, it lets you manage your machines using Secure Shell (SSH).

## Quick start for Windows users:

1. Download the redc2.exe and the machines.toml.example file from the [Releases](../../releases) tab
2. Make sure they are in the same exact folder
3. Open machines.toml.example file, edit it with the real credentials and rename it to machines.toml
4. Run the exe file



## Setting up the machines.toml (replace the credentials)
# Do not use SSH key-file auth this function was removed !

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

To add more machines simply copy paste the [[machines]] block, change the credentials though

## How to use it

When you type help in the mini terminal, the first terminal you see when you launch the program simply type 'help' to see the commands



