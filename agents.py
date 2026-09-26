#!/usr/bin/env python3
"""
The agent manager.

An "agent" is a folder that teaches this Jarvis one new skill. It can do three things:

  1. add to the soul   -> text appended to the system prompt, so the brain knows the
                          skill exists and how to use it
  2. publish a panel   -> JSON served at /agents/<name>/panel, drawn on the face
  3. add HTTP routes   -> anything else you want to expose

Nothing else in the tree knows what your agents do. The core stays generic; the
personality and the local knowledge live in agents/ and soul/.

Layout of one agent:

    agents/weather/
      agent.json     required — manifest (name, title, description, enabled, config)
      soul.md        optional — static prompt fragment
      agent.py       optional — Python hooks (see below)

agent.py may define any of:

    PANEL_TTL = 30                  # seconds to cache panel() output (default 15)
    def soul(cfg) -> str            # dynamic prompt fragment, appended after soul.md
    def panel(cfg) -> dict          # data for the face
    def routes(cfg) -> dict         # {"do": handler}  ->  /agents/<name>/do
                                    # handler(method, query, body, cfg) -> (code, obj)

`cfg` is the agent's own config dict: agent.json "config", overlaid with the user's
~/.jarvis/agents.json so a `git pull` never clobbers local settings.

Failure is contained. A broken agent is reported on /agents with its error and
skipped; it can never take the bridge down with it.
"""

import os, json, time, importlib.util, threading, traceback

USER_DIR = os.path.join(os.path.expanduser("~"), ".jarvis")
USER_CONFIG = os.path.join(USER_DIR, "agents.json")     # {"<name>": {"enabled":bool,"config":{}}}
USER_AGENTS = os.path.join(USER_DIR, "agents")          # private agents live here, outside git

_lock = threading.Lock()
_loaded = {}            # name -> record
_panel_cache = {}       # name -> {"t": monotonic, "data": {}}
_log = lambda kind, detail: None   # bridge injects its logger via set_logger()


def set_logger(fn):
    """Let the bridge route agent problems into its own action log."""
    global _log
    _log = fn


# ---- user config overlay ----------------------------------------------------
def _user_config():
    try:
        with open(USER_CONFIG, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_user_config(data):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = USER_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, USER_CONFIG)


def set_enabled(name, enabled):
    """Flip an agent on or off for this machine. Takes effect on the next bridge start."""
    data = _user_config()
    entry = data.get(name) or {}
    entry["enabled"] = bool(enabled)
    data[name] = entry
    save_user_config(data)


# ---- discovery + loading ----------------------------------------------------
def _agent_dirs(base_dir):
    """Every candidate agent folder: the ones that ship with the repo, then the user's
    private ones. A user agent with the same name wins, so you can override a shipped
    agent without editing tracked files."""
    roots = [os.path.join(base_dir, "agents"), USER_AGENTS]
    found = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for entry in sorted(os.listdir(root)):
            if entry.startswith((".", "_")):
                continue                        # _template and friends are not agents
            path = os.path.join(root, entry)
            if os.path.isfile(os.path.join(path, "agent.json")):
                found[entry] = path
    return found


def _import(path, name):
    spec = importlib.util.spec_from_file_location(f"jarvis_agent_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load(base_dir):
    """Read every agent, merge config, import modules. Safe to call again to reload."""
    overlay = _user_config()
    records = {}
    for name, path in _agent_dirs(base_dir).items():
        rec = {"name": name, "dir": path, "title": name, "description": "",
               "enabled": True, "version": "", "soul_text": "", "module": None,
               "config": {}, "error": "", "routes": {}, "act_words": []}
        try:
            with open(os.path.join(path, "agent.json"), "r", encoding="utf-8") as fh:
                man = json.load(fh)
        except (OSError, ValueError) as e:
            rec["error"] = f"bad agent.json ({e.__class__.__name__})"
            records[name] = rec
            _log("agent_error", f"{name}: {rec['error']}")
            continue

        rec["title"] = str(man.get("title") or name)
        rec["description"] = str(man.get("description") or "")
        rec["version"] = str(man.get("version") or "")
        rec["enabled"] = bool(man.get("enabled", True))
        rec["config"] = dict(man.get("config") or {})
        # Words that should push a turn onto the better model, because acting on this
        # skill needs tool-use judgment. "put on the bebop opening" is not small talk.
        rec["act_words"] = [str(w) for w in (man.get("act_words") or []) if str(w).strip()]

        user = overlay.get(name) or {}
        if "enabled" in user:
            rec["enabled"] = bool(user["enabled"])
        rec["config"].update(user.get("config") or {})

        soul_file = man.get("soul", "soul.md")
        soul_path = os.path.join(path, soul_file) if soul_file else ""
        if soul_path and os.path.isfile(soul_path):
            try:
                with open(soul_path, "r", encoding="utf-8") as fh:
                    rec["soul_text"] = fh.read().strip()
            except OSError as e:
                rec["error"] = f"unreadable {soul_file} ({e.__class__.__name__})"

        mod_file = man.get("module", "agent.py")
        mod_path = os.path.join(path, mod_file) if mod_file else ""
        if rec["enabled"] and mod_path and os.path.isfile(mod_path):
            try:
                rec["module"] = _import(mod_path, name)
            except Exception:
                rec["error"] = "import failed: " + traceback.format_exc(limit=1).strip().splitlines()[-1][:180]
                _log("agent_error", f"{name}: {rec['error']}")
        if rec["module"] is not None and hasattr(rec["module"], "routes"):
            try:
                rec["routes"] = dict(rec["module"].routes(rec["config"]) or {})
            except Exception as e:
                rec["error"] = f"routes() failed: {str(e)[:160]}"
                _log("agent_error", f"{name}: {rec['error']}")
        records[name] = rec

    with _lock:
        _loaded.clear()
        _loaded.update(records)
        _panel_cache.clear()
    on = [n for n, r in records.items() if r["enabled"]]
    _log("agents_loaded", f"{len(on)} enabled of {len(records)}: {','.join(sorted(on)) or 'none'}")
    return records


def enabled():
    with _lock:
        return [r for r in _loaded.values() if r["enabled"] and not r["error"].startswith("bad ")]


def listing():
    """Summary for /agents and the CLI."""
    with _lock:
        recs = sorted(_loaded.values(), key=lambda r: r["name"])
    return [{
        "name": r["name"], "title": r["title"], "description": r["description"],
        "version": r["version"], "enabled": r["enabled"], "error": r["error"],
        "private": r["dir"].startswith(USER_AGENTS),
        "panel": bool(r["module"] is not None and hasattr(r["module"], "panel")),
        "routes": sorted(r["routes"].keys()),
    } for r in recs]


# ---- the three things an agent can do ---------------------------------------
def souls():
    """Every enabled agent's prompt fragment, static then dynamic, in name order."""
    out = []
    for rec in sorted(enabled(), key=lambda r: r["name"]):
        parts = []
        if rec["soul_text"]:
            parts.append(rec["soul_text"])
        mod = rec["module"]
        if mod is not None and hasattr(mod, "soul"):
            try:
                text = (mod.soul(rec["config"]) or "").strip()
                if text:
                    parts.append(text)
            except Exception as e:
                _log("agent_error", f"{rec['name']} soul(): {str(e)[:160]}")
        if parts:
            out.append(f"## Agent: {rec['title']}\n" + "\n\n".join(parts))
    return out


def act_words():
    """Every enabled agent's escalation words, merged and de-duplicated."""
    words = []
    for rec in enabled():
        for w in rec["act_words"]:
            if w.lower() not in (x.lower() for x in words):
                words.append(w)
    return words


def soul_block():
    blocks = souls()
    if not blocks:
        return ""
    return ("# Installed agents\n"
            "These are the skills this machine has been given. Use them when they fit;\n"
            "do not claim a skill that is not listed here.\n\n" + "\n\n".join(blocks))


def panel(name):
    """One agent's panel data, cached per its PANEL_TTL."""
    with _lock:
        rec = _loaded.get(name)
    if not rec or not rec["enabled"] or rec["module"] is None:
        return None
    mod = rec["module"]
    if not hasattr(mod, "panel"):
        return None
    ttl = float(getattr(mod, "PANEL_TTL", 15))
    hit = _panel_cache.get(name)
    if hit and time.monotonic() - hit["t"] < ttl:
        return hit["data"]
    try:
        data = mod.panel(rec["config"])
    except Exception as e:
        data = {"error": str(e)[:200]}
        _log("agent_error", f"{name} panel(): {str(e)[:160]}")
    _panel_cache[name] = {"t": time.monotonic(), "data": data}
    return data


def panels():
    """Every enabled agent that publishes a panel, for one cheap poll from the face."""
    out = {}
    for rec in enabled():
        data = panel(rec["name"])
        if data is not None:
            out[rec["name"]] = {"title": rec["title"], "data": data}
    return out


def route(name, subpath, method, query, body):
    """Dispatch /agents/<name>/<subpath>. Returns (code, obj) or None if unclaimed."""
    with _lock:
        rec = _loaded.get(name)
    if not rec or not rec["enabled"]:
        return None
    handler = rec["routes"].get(subpath.strip("/"))
    if handler is None:
        return None
    try:
        return handler(method, query, body, rec["config"])
    except Exception as e:
        _log("agent_error", f"{name} route {subpath}: {str(e)[:160]}")
        return 500, {"error": str(e)[:200]}
