"""Vitals for the machine Jarvis runs on. Works on macOS and Linux, stdlib only."""

import os, re, shutil, subprocess, time

PANEL_TTL = 10          # the face polls every 10s; never compute more often than that
_BOOT = time.time()


def _run(cmd, timeout=3):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _mem_mac():
    """Used fraction from vm_stat page counts. Compressed + wired + active is what
    actually hurts on a small Mac, so count those as used."""
    txt = _run(["vm_stat"])
    if not txt:
        return None
    pages = {k.strip(): int(v.strip().rstrip(".")) for k, v in
             (l.split(":", 1) for l in txt.splitlines() if ":" in l and l.split(":", 1)[1].strip().rstrip(".").isdigit())}
    size = 16384
    m = re.search(r"page size of (\d+)", txt)
    if m:
        size = int(m.group(1))
    used_keys = ("Pages active", "Pages wired down", "Pages occupied by compressor")
    used = sum(pages.get(k, 0) for k in used_keys) * size
    free = (pages.get("Pages free", 0) + pages.get("Pages inactive", 0)) * size
    total = used + free
    return {"used_gb": round(used / 1e9, 1), "total_gb": round(total / 1e9, 1),
            "frac": round(used / total, 3) if total else 0}


def _mem_linux():
    try:
        info = {}
        for line in open("/proc/meminfo"):
            k, _, v = line.partition(":")
            info[k] = int(v.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return None
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    used = total - avail
    return {"used_gb": round(used / 1e9, 1), "total_gb": round(total / 1e9, 1),
            "frac": round(used / total, 3) if total else 0}


def panel(cfg):
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    cpus = os.cpu_count() or 1
    mem = _mem_mac() if os.uname().sysname == "Darwin" else _mem_linux()
    path = cfg.get("disk_path", "/")
    try:
        du = shutil.disk_usage(path)
        disk = {"free_gb": round(du.free / 1e9, 1), "total_gb": round(du.total / 1e9, 1),
                "frac": round(du.used / du.total, 3) if du.total else 0}
    except OSError:
        disk = None
    return {
        "host": os.uname().nodename,
        "os": f"{os.uname().sysname} {os.uname().release}",
        "load1": round(load1, 2),
        "cpu_frac": round(min(load1 / cpus, 1.0), 3),
        "cpus": cpus,
        "mem": mem,
        "disk": disk,
        "bridge_uptime_sec": int(time.time() - _BOOT),
    }


def soul(cfg):
    """A one-line live summary so the brain knows the state without polling a route."""
    p = panel(cfg)
    mem = p.get("mem") or {}
    disk = p.get("disk") or {}
    return (f"Right now: host {p['host']}, {p['os']}, load {p['load1']} across {p['cpus']} cores, "
            f"memory {mem.get('used_gb','?')} of {mem.get('total_gb','?')} GB used, "
            f"{disk.get('free_gb','?')} GB free on {cfg.get('disk_path','/')}.")
