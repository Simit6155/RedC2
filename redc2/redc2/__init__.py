"""REDC2 — a terminal-based SSH remote management dashboard.

REDC2 is a personal/home-lab administration tool. It connects to machines
you own over standard authenticated SSH (via Paramiko) and presents a
Textual-based terminal dashboard with live telemetry, an interactive
remote shell, and simple machine management commands.

It intentionally does NOT implement any reverse-shell, C2, persistence,
stealth, or credential-harvesting functionality. All remote access is
plain, auditable SSH.
"""

__version__ = "0.1.0"
