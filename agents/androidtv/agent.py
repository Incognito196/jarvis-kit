"""Android TV over ADB. The panel shows whether the set is awake and what's on screen;
the brain drives it through tv.py (see soul.md) so a turn can chain commands freely."""

import os, subprocess

PANEL_TTL = 30          # asking a TV what it's doing wakes the socket; don't hammer it
HERE = os.path.dirname(os.path.abspath(__file__))
TV_PY = os.path.join(HERE, "tv.py")


def panel(cfg):
    try:
        out = subprocess.run(["python3", TV_PY, "status"], capture_output=True,
                             text=True, timeout=15)
        text = (out.stdout or out.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as e:
        return {"reachable": False, "error": str(e)[:160]}
    awake = "Awake" in text
    app = ""
    for line in text.splitlines():
        if "mCurrentFocus" in line and "/" in line:
            app = line.split("u0 ")[-1].strip("}")
    return {"reachable": bool(text) and "unreachable" not in text.lower(),
            "awake": awake, "showing": app, "raw": text[:300]}


def routes(cfg):
    def run(method, query, body, cfg):
        """POST /agents/androidtv/cmd  {"cmd": "play", "args": "cowboy bebop opening"}"""
        body = body or {}
        cmd = str(body.get("cmd") or "").strip()
        allowed = {"status", "on", "off", "home", "back", "ok", "up", "down", "left", "right",
                   "pause", "stop", "volup", "voldown", "mute", "play", "youtube", "app",
                   "type", "screenshot", "apps", "reconnect"}
        if cmd not in allowed:
            return 400, {"error": f"cmd must be one of: {', '.join(sorted(allowed))}"}
        args = str(body.get("args") or "")
        argv = ["python3", TV_PY, cmd] + ([args] if args else [])
        try:
            out = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            return 200, {"ok": out.returncode == 0,
                         "output": (out.stdout or out.stderr).strip()[:2000]}
        except subprocess.SubprocessError as e:
            return 504, {"error": str(e)[:200]}
    return {"cmd": run}
