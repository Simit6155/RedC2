#REDC2 a terminal SSH based remote manager.

import subprocess
import sys
import platform
from colorama import Fore, init
init()

# CONFIG
MACHINES = [
    {"name": "Ubuntu-Server", "host": "192.123.123.12", "user": "jarvis"},
    {"name": "pinas", "host": "192.123.123.12", "user": "root"},
]


def list_machines():
    print(f"{'ID':<4} {'NAME':<18} {'HOST'}")
    for i, m in enumerate(MACHINES):
        print(f"{i:<4} {m['name']:<18} {m['user']}@{m['host']}")


def ssh(machine_id: int):
    if machine_id < 0 or machine_id >= len(MACHINES):
        print(Fore.RED + f"Invalid machine id: {machine_id}")
        return

    m = MACHINES[machine_id]
    target = f"{m['user']}@{m['host']}"
    print(Fore.GREEN + f"Connecting to {m['name']} ({target}) ...")

    try:  # hands everything to the SSH
        subprocess.run(["ssh", target])
    except FileNotFoundError:
        os_name = platform.system()
        if os_name == "Linux":
            with open("/etc/os-release") as f:
                distro = next(
                    (line.split("=")[1].strip().strip('"')
                     for line in f if line.startswith("PRETTY_NAME=")),
                    "Linux"
                )
            os_name = distro

        print(
            Fore.RED +
            f"ERROR: ssh was not found on this system.\n"
            f"Detected OS: {os_name}\n"
            f"Press Y to install SSH or N to abort."
        )
        choice = input("> ").strip().lower()
        if choice == "y":
            if platform.system() == "Windows":
                subprocess.run([
                    "winget", "install",
                    "--id", "Microsoft.OpenSSH.Beta",
                    "--accept-source-agreements",
                    "--accept-package-agreements"
                ])
            elif "Arch" in os_name:
                subprocess.run(["sudo", "pacman", "-S", "--needed", "openssh"])
            elif any(x in os_name for x in ["Ubuntu", "Debian", "Mint"]):
                subprocess.run(["sudo", "apt", "install", "-y", "openssh-client"])
            else:
                print(Fore.RED + "Automatic installation is not supported on this OS.")
        else:
            print(Fore.YELLOW + "Aborted.")

    except KeyboardInterrupt:
        print("\n[connection interrupted]")


def main():
    print("REDC2 type 'help' for commands.\n")
    list_machines()

    while True:
        try:
            raw = input("\nredc2> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            print("Commands: list, select <id>, quit / exit")
        elif cmd == "list":
            list_machines()
        elif cmd == "select":
            if len(args) != 1 or not args[0].isdigit():
                print("Usage: select <id>")
                continue
            ssh(int(args[0]))
        elif cmd in ("quit", "exit"):
            print("Goodbye.")
            break
        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for a list of commands.")


if __name__ == "__main__":
    main()