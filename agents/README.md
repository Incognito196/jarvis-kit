# Agents

One folder per skill. Drop it in, restart the bridge, and this Jarvis knows how to do
one more thing.

```
agents/<name>/
  agent.json     manifest: title, description, enabled, config   (required)
  soul.md        prompt fragment, appended to the system prompt   (optional)
  agent.py       panel() / soul() / routes() hooks                (optional)
```

Shipped here:

| agent | default | what it does |
|-------|---------|--------------|
| `system` | on | vitals for the machine Jarvis runs on |
| `nodes` | off | reachability for other machines you list in config |
| `androidtv` | off | drive a Google TV / Fire TV over ADB |
| `_template` | — | skeleton to copy; the leading underscore keeps it from loading |

Turn them on and off with the CLI, which writes `~/.jarvis/agents.json` instead of
editing tracked files — so `git pull` never clobbers your settings:

```bash
./jarvisctl agents              # what's installed, what's on
./jarvisctl enable nodes
./jarvisctl disable androidtv
./jarvisctl new grocery-list    # scaffold a new agent from _template
```

**Private agents.** Anything under `~/.jarvis/agents/` loads exactly the same way and is
outside this repo entirely. That's where your real life goes — your house, your business,
your credentials. A user agent overrides a shipped one with the same name. See
[docs/PRIVATE-AGENTS.md](../docs/PRIVATE-AGENTS.md).

Full contract, including what the hooks receive and return:
[docs/AGENTS.md](../docs/AGENTS.md).
