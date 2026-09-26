#!/usr/bin/env python3
"""Android TV remote over ADB, driven from the command line.

    tv.py status | on | off | home | back | ok | up | down | left | right
    tv.py pause | stop | volup | voldown | mute
    tv.py play <search terms>        # search YouTube, play the top result
    tv.py youtube [url or video id]  # exact video, or just launch the app
    tv.py app <name-or-package>      # anything in the agent's "apps" config
    tv.py type <text> | screenshot | apps [filter] | reconnect

Reads its host list from agent.json (overlaid with ~/.jarvis/agents.json), so pairing a
different TV is a config edit, not a code edit. First run needs a one-time pairing: put
the TV in developer mode, enable network debugging, run `adb connect <ip>:5555` and
accept the prompt on screen. Auth survives reboots; the socket does not survive sleep,
so every call reconnects first (idempotent, ~100ms).
"""

import json, os, re, subprocess, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
USER_CONFIG = os.path.join(os.path.expanduser("~"), ".jarvis", "agents.json")

KEYS = {"on": "KEYCODE_WAKEUP", "off": "KEYCODE_SLEEP", "home": "KEYCODE_HOME",
        "back": "KEYCODE_BACK", "ok": "KEYCODE_DPAD_CENTER", "up": "KEYCODE_DPAD_UP",
        "down": "KEYCODE_DPAD_DOWN", "left": "KEYCODE_DPAD_LEFT",
        "right": "KEYCODE_DPAD_RIGHT", "pause": "KEYCODE_MEDIA_PLAY_PAUSE",
        "stop": "KEYCODE_MEDIA_STOP", "volup": "KEYCODE_VOLUME_UP",
        "voldown": "KEYCODE_VOLUME_DOWN", "mute": "KEYCODE_VOLUME_MUTE"}


def config():
    cfg = {}
    try:
        with open(os.path.join(HERE, "agent.json"), encoding="utf-8") as fh:
            cfg = json.load(fh).get("config") or {}
    except (OSError, ValueError):
        pass
    try:
        with open(USER_CONFIG, encoding="utf-8") as fh:
            cfg.update((json.load(fh).get("androidtv") or {}).get("config") or {})
    except (OSError, ValueError):
        pass
    return cfg


CFG = config()
ADB = CFG.get("adb") or "adb"
PORT = int(CFG.get("port", 5555))
HOSTS = [h for h in (CFG.get("hosts") or []) if h]


def _adb(target, *args, timeout=30, binary=False):
    argv = [ADB] + (["-s", target] if target else []) + list(args)
    return subprocess.run(argv, capture_output=not binary, stdout=subprocess.PIPE if binary else None,
                          text=not binary, timeout=timeout)


def pick_tv():
    """First configured host that answers. Multiple entries let you list the same set
    twice — once on a VPN address, once on the LAN — and use whichever is alive."""
    for host in HOSTS:
        target = f"{host}:{PORT}"
        try:
            subprocess.run([ADB, "connect", target], capture_output=True, text=True, timeout=6)
            state = subprocess.run([ADB, "-s", target, "get-state"], capture_output=True,
                                   text=True, timeout=6)
            if state.stdout.strip() == "device":
                return target
        except (OSError, subprocess.SubprocessError):
            continue
    return ""


def shell(target, cmd, timeout=30):
    out = _adb(target, "shell", cmd, timeout=timeout)
    return (out.stdout or "").strip()


def youtube_top(query):
    """Scrape the first videoId out of a YouTube results page."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        body = r.read().decode(errors="replace")
    m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', body)
    return m.group(1) if m else ""


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 1
    cmd, args = argv[0], argv[1:]
    if not HOSTS:
        print("No TV configured. Add its IP to the androidtv agent's config.hosts "
              "(agents/androidtv/agent.json, or ~/.jarvis/agents.json).")
        return 1
    if cmd == "reconnect":
        for host in HOSTS:
            subprocess.run([ADB, "disconnect", f"{host}:{PORT}"], capture_output=True)
        target = pick_tv()
        print(f"reconnected on {target}" if target else "TV unreachable on every configured address")
        return 0 if target else 1

    target = pick_tv()
    if not target:
        print("TV unreachable — asleep too deep, powered off, or not on the network")
        return 1

    if cmd == "status":
        out = shell(target, "dumpsys power | grep -m1 mWakefulness=; dumpsys window | grep -m1 mCurrentFocus")
        print(out or "TV answered but told us nothing")
        print(f"(via {target})")
        return 0
    if cmd in KEYS:
        shell(target, f"input keyevent {KEYS[cmd]}")
        print(f"sent {cmd}")
        return 0
    if cmd == "play":
        query = " ".join(args)
        if not query:
            print("usage: tv.py play <search terms>")
            return 1
        vid = youtube_top(query)
        if not vid:
            print(f"no YouTube result for: {query}")
            return 1
        pkg = (CFG.get("apps") or {}).get("youtube", "com.google.android.youtube.tv")
        shell(target, f"am start -a android.intent.action.VIEW -d "
                      f"'https://www.youtube.com/watch?v={vid}' {pkg}")
        print(f"playing top YouTube result ({vid}) for: {query}")
        return 0
    if cmd == "youtube":
        pkg = (CFG.get("apps") or {}).get("youtube", "com.google.android.youtube.tv")
        if args:
            ref = args[0]
            url = ref if ref.startswith("http") else f"https://www.youtube.com/watch?v={ref}"
            shell(target, f"am start -a android.intent.action.VIEW -d '{url}' {pkg}")
            print(f"opening {url}")
        else:
            shell(target, f"monkey -p {pkg} 1")
            print("YouTube launched")
        return 0
    if cmd == "app":
        if not args:
            print("usage: tv.py app <name-or-package>")
            return 1
        want = args[0]
        pkg = (CFG.get("apps") or {}).get(want, want)
        # monkey injects one random input event with the launch — fine for streaming
        # apps, never use it on an app whose own key handling matters.
        shell(target, f"monkey -p {pkg} 1")
        print(f"launched {pkg}")
        return 0
    if cmd == "type":
        text = " ".join(args).replace(" ", "%s")
        shell(target, f"input text '{text}'")
        print("typed")
        return 0
    if cmd == "apps":
        flt = args[0].lower() if args else ""
        out = shell(target, "pm list packages -3")
        names = sorted(l.replace("package:", "") for l in out.splitlines() if l.startswith("package:"))
        print("\n".join(n for n in names if flt in n.lower()) or "(none)")
        return 0
    if cmd == "screenshot":
        path = f"/tmp/tv-{time.strftime('%H%M%S')}.png"
        with open(path, "wb") as fh:
            proc = subprocess.run([ADB, "-s", target, "exec-out", "screencap", "-p"],
                                  stdout=fh, timeout=30)
        if proc.returncode == 0 and os.path.getsize(path) > 1000:
            print(path)
            return 0
        print("screenshot failed")
        return 1
    print(f"unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
