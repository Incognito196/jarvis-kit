"""Skeleton agent. Copy this folder to agents/<yourname>/ (or ~/.jarvis/agents/<yourname>/
for something private), rename it in agent.json, and delete whatever you don't need.

Every hook is optional. An agent with only a soul.md and no agent.py is perfectly valid —
that alone is enough to teach the brain a new habit.
"""

PANEL_TTL = 15          # seconds the bridge caches panel() output


def soul(cfg):
    """Dynamic prompt text, appended after soul.md. Use it for live facts the brain
    should know without having to go look: today's numbers, what's currently on, who's
    working. Keep it to a couple of lines — this runs on every single turn."""
    return f"Example setting is currently: {cfg.get('example_setting')}"


def panel(cfg):
    """JSON for the face. Return anything you like; the face renders unknown agents
    generically as label/value rows, so a flat dict of short strings and numbers looks
    best. Raise or return {"error": ...} and it shows as a problem instead."""
    return {"hello": "world", "setting": cfg.get("example_setting")}


def routes(cfg):
    """Extra HTTP endpoints, mounted at /agents/<name>/<key>. These require the action
    token, because anything reachable here can act on your machine.

    handler(method, query, body, cfg) -> (status_code, json_serializable_object)
    """
    def ping(method, query, body, cfg):
        return 200, {"ok": True, "method": method, "got": body}
    return {"ping": ping}
