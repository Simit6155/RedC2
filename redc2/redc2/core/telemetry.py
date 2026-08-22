from __future__ import annotations

import logging
import re

from redc2.core.machine import TelemetrySnapshot
from redc2.core.ssh import SSHConnectionError, SSHSession

logger = logging.getLogger("redc2.telemetry")

_REMOTE_PROBE = r"""
python3 - <<'REDC2_PY'
import json, os, platform, socket, time

data = {}
try:
    data["hostname"] = socket.gethostname()
except Exception:
    data["hostname"] = None

try:
    uname = platform.uname()
    data["os_name"] = f"{uname.system} {uname.release}"
    data["kernel"] = uname.release
    data["architecture"] = uname.machine
except Exception:
    data["os_name"] = data["kernel"] = data["architecture"] = None

try:
    import psutil
    data["cpu_percent"] = psutil.cpu_percent(interval=0.3)
    data["cpu_cores"] = psutil.cpu_count(logical=True)
    vm = psutil.virtual_memory()
    data["ram_total_gb"] = vm.total / (1024**3)
    data["ram_used_gb"] = (vm.total - vm.available) / (1024**3)
    data["ram_percent"] = vm.percent
    du = psutil.disk_usage("/")
    data["disk_total_gb"] = du.total / (1024**3)
    data["disk_used_gb"] = du.used / (1024**3)
    data["disk_percent"] = du.percent
    data["uptime_seconds"] = time.time() - psutil.boot_time()
    net = psutil.net_io_counters()
    data["net_sent_mb"] = net.bytes_sent / (1024**2)
    data["net_recv_mb"] = net.bytes_recv / (1024**2)
    temp = None
    try:
        temps = psutil.sensors_temperatures()
        for entries in temps.values():
            if entries:
                temp = entries[0].current
                break
    except Exception:
        temp = None
    data["temperature_c"] = temp
except ImportError:
    data["cpu_percent"] = None
    data["cpu_cores"] = os.cpu_count()
    data["ram_total_gb"] = data["ram_used_gb"] = data["ram_percent"] = None
    data["disk_total_gb"] = data["disk_used_gb"] = data["disk_percent"] = None
    data["uptime_seconds"] = None
    data["net_sent_mb"] = data["net_recv_mb"] = None
    data["temperature_c"] = None

if data.get("temperature_c") is None:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as fh:
            data["temperature_c"] = int(fh.read().strip()) / 1000.0
    except Exception:
        pass

try:
    with open("/proc/cpuinfo") as fh:
        for line in fh:
            if line.lower().startswith("model name"):
                data["cpu_model"] = line.split(":", 1)[1].strip()
                break
        else:
            data["cpu_model"] = None
except Exception:
    data["cpu_model"] = None

print(json.dumps(data))
REDC2_PY
""".strip()

_IP_FALLBACK_CMD = "hostname -I 2>/dev/null || ip route get 1 2>/dev/null | awk '{print $7; exit}'"

def collect_snapshot(session: SSHSession) -> TelemetrySnapshot:
    result = session.run_command(_REMOTE_PROBE, timeout=15.0)
    snapshot = TelemetrySnapshot()

    if result.exit_status != 0 or not result.stdout.strip():
        logger.warning(
            "Telemetry probe failed (exit=%s): %s", result.exit_status, result.stderr.strip()
        )
        return snapshot

    import json

    try:
        raw = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        logger.warning("Could not parse telemetry JSON: %s", exc)
        return snapshot

    def _get_float(key: str) -> float | None:
        value = raw.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _get_int(key: str) -> int | None:
        value = raw.get(key)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    snapshot.hostname = raw.get("hostname")
    snapshot.os_name = raw.get("os_name")
    snapshot.kernel = raw.get("kernel")
    snapshot.architecture = raw.get("architecture")
    snapshot.cpu_model = raw.get("cpu_model")
    snapshot.cpu_percent = _get_float("cpu_percent")
    snapshot.cpu_cores = _get_int("cpu_cores")
    snapshot.ram_total_gb = _get_float("ram_total_gb")
    snapshot.ram_used_gb = _get_float("ram_used_gb")
    snapshot.ram_percent = _get_float("ram_percent")
    snapshot.disk_total_gb = _get_float("disk_total_gb")
    snapshot.disk_used_gb = _get_float("disk_used_gb")
    snapshot.disk_percent = _get_float("disk_percent")
    snapshot.uptime_seconds = _get_float("uptime_seconds")
    snapshot.net_sent_mb = _get_float("net_sent_mb")
    snapshot.net_recv_mb = _get_float("net_recv_mb")
    snapshot.temperature_c = _get_float("temperature_c")

    try:
        ip_result = session.run_command(_IP_FALLBACK_CMD, timeout=5.0)
        ip_text = ip_result.stdout.strip().split()
        if ip_text:
            snapshot.ip_address = ip_text[0]
    except SSHConnectionError:
        pass

    return snapshot

_JSON_LINE_RE = re.compile(r"^\{.*\}$")

def parse_telemetry_json(raw_line: str) -> dict:
    import json

    if not _JSON_LINE_RE.match(raw_line.strip()):
        raise ValueError("Not a JSON object line")
    return json.loads(raw_line)
