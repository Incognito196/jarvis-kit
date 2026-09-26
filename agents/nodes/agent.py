"""Reachability for a list of machines you configure. A TCP connect, not ICMP, so it
needs no root and no ping binary — point it at any port the host actually answers on
(22 for SSH, 80 for a web box, 3389 for Windows)."""

import socket, concurrent.futures as futures

PANEL_TTL = 12          # a little longer than the face's poll, so one poll = one check


def _check(host, port, timeout):
    t0 = socket.getdefaulttimeout()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False
    finally:
        socket.setdefaulttimeout(t0)


def panel(cfg):
    hosts = cfg.get("hosts") or []
    port = int(cfg.get("port", 22))
    timeout = float(cfg.get("timeout", 1.5))
    if not hosts:
        return {"nodes": [], "note": "no hosts configured yet"}
    # Checked in parallel: 8 hosts at a 1.5s timeout should cost 1.5s, not 12.
    with futures.ThreadPoolExecutor(max_workers=min(8, len(hosts))) as pool:
        jobs = {pool.submit(_check, h.get("host", ""), int(h.get("port", port)), timeout): h
                for h in hosts if h.get("host")}
        out = []
        for job in futures.as_completed(jobs):
            h = jobs[job]
            out.append({"name": h.get("name") or h["host"], "host": h["host"], "up": job.result()})
    out.sort(key=lambda r: r["name"])
    return {"nodes": out, "up": sum(1 for r in out if r["up"]), "total": len(out)}


def soul(cfg):
    hosts = cfg.get("hosts") or []
    if not hosts:
        return ""
    lines = [f"- {h.get('name') or h['host']} at {h['host']}" for h in hosts if h.get("host")]
    return "Machines this setup watches:\n" + "\n".join(lines)
