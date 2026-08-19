#!/usr/bin/env python3
"""Shared config + secret loading for every JARVIS process.

Two files, both gitignored, both sitting next to this one:

  config.json  — who you are, what your fleet is. Not secret, but personal.
  .env         — API keys and the shared bridge token. Secret. chmod 600.

Every key has a default, so a missing or half-filled config still boots.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "config.json")
ENV_FILE = os.path.join(HERE, ".env")

DEFAULTS = {
    "assistant_name": "JARVIS",     # what it calls itself
    "owner_name": "boss",           # what it calls you
    "machine_label": "this machine",  # shown under the name on the face
    "timezone": "America/New_York",
    "fleet_label": "The Fleet",     # heading over the node list on the dashboard
    "weather_label": "Weather",     # heading over the weather panel
    "weather_lat": 40.7,
    "weather_lon": -74.0,
    "tailscale_bin": "/usr/local/bin/tailscale",
    "self_node": "",                # this machine's name inside "nodes"
    "nodes": [],                    # [{"name": "vps", "ip": "100.x.y.z"}, ...]
    "watch_service": "",            # optional launchd label to show on the vitals panel
    "extra_act_words": [],          # extra words that should escalate to the smarter model
    "owner_phone": "",              # E.164, for the iMessage bridge: "+15551234567"
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"WARNING: config.json unreadable ({e}) — using defaults", file=sys.stderr)
    return cfg


def load_env():
    """Read .env into os.environ WITHOUT clobbering anything already set.

    setdefault matters: launchd plists set JARVIS_VOICE etc. in the job's environment,
    and those must win over a stale line in .env.
    """
    try:
        for line in open(ENV_FILE):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


def env(name, default=""):
    """One secret, from the process environment or .env."""
    load_env()
    return os.environ.get(name, default)
