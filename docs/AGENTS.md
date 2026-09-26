# Writing an agent

An agent is a folder. It teaches your Jarvis one skill and can do three things:

1. **Add to the soul** — text appended to the system prompt, so the brain knows the skill
   exists and how to use it.
2. **Publish a panel** — JSON served at `/agents/<name>/panel`, drawn on the face.
3. **Add HTTP routes** — anything else you want to expose.

Nothing in the core knows what your agents do. That is the whole point: you pull updates
to the bridge without ever touching your own stuff.

## Layout

```
agents/my-thing/
  agent.json     manifest                                    (required)
  soul.md        static prompt fragment                      (optional)
  agent.py       soul() / panel() / routes() hooks            (optional)
```

Scaffold one instead of typing it out:

```bash
./jarvisctl new my-thing              # into the repo
./jarvisctl new my-thing --private    # into ~/.jarvis/agents, outside git
```

## agent.json

```json
{
  "name": "my-thing",
  "title": "My thing",
  "description": "One sentence, shown by ./jarvisctl agents.",
  "version": "1.0.0",
  "enabled": true,
  "config": { "any": "settings your code needs" }
}
```

### act_words

```json
{ "act_words": ["put on", "netflix", "volume"] }
```

Optional. Words in a turn that should push it onto the better model, because acting on
this skill needs tool-use judgment. Without it, "put on the Bebop opening" reads as small
talk and gets answered by the fast model — the one that improvises an answer instead of
calling your tool. Add the nouns and verbs people will actually say, in every language you
use.

`config` is yours. It arrives as the `cfg` argument to every hook. Users override it in
`~/.jarvis/agents.json` rather than editing your file:

```json
{
  "my-thing": { "enabled": true, "config": { "any": "their value" } }
}
```

Keys are merged, so a user overriding one setting keeps your defaults for the rest.
This is also how `./jarvisctl enable` and `disable` work, which is why a `git pull`
never resets someone's machine.

## soul.md

Plain prose, appended verbatim to the system prompt. Write it like briefing a person on
their first day: what the skill does, the exact command with an example, and the rules —
what to confirm first, what never to touch, how to verify it worked.

Keep it short. Every line is weighed on every turn, and a page of rules makes the brain
slower and vaguer, not smarter.

## agent.py

Every hook is optional. An agent with only a `soul.md` is completely valid.

```python
PANEL_TTL = 15          # seconds the bridge caches panel() output (default 15)

def soul(cfg):
    """Live facts, appended after soul.md. Runs on EVERY turn — keep it to a few
    lines and never let it block. A slow soul() is a slow assistant."""
    return "Today's total is 412 units."

def panel(cfg):
    """Data for the face. Return a flat-ish dict. The face renders unknown agents
    generically, with two conventions it understands:
        {"frac": 0.0-1.0, "used_gb": .., "total_gb": ..}  -> a meter
        [{"name": "...", "up": true}]                      -> status dots
    Return {"error": "..."} to show a problem."""
    return {"total": 412, "load": {"frac": 0.62}}

def routes(cfg):
    """Extra endpoints, mounted at /agents/<name>/<key>. These REQUIRE the action
    token, because anything reachable here can act on the machine.
    handler(method, query, body, cfg) -> (status_code, json_object)"""
    def start(method, query, body, cfg):
        return 200, {"ok": True}
    return {"start": start}
```

### Two ways to let the brain act

**Through a route.** Good for one specific, well-defined action you want to be able to
trigger from anything, including a phone shortcut or a cron job.

**Through the shell, described in soul.md.** Often better. Ship a small script in your
agent folder, tell the brain in `soul.md` how to call it, and let it chain calls,
read output and decide what to do next — that is what the brain is for. The `androidtv`
agent works this way: `tv.py` does one thing per invocation, and `soul.md` teaches the
rest.

## Failure is contained

A broken agent is reported on `/agents` and by `./jarvisctl agents`, with its error, and
then skipped. It cannot take the bridge down with it. If `panel()` throws, the panel
shows the error; if `soul()` throws, the fragment is dropped and logged. Check
`./jarvisctl logs` for `agent_error` lines.

## Changes need a restart

Agents are loaded once at boot. After editing `agent.py` or `agent.json`:

```bash
./jarvisctl restart
```

`soul/SOUL.md` and any `soul.md` are read fresh on **every turn**, so pure wording
changes are live immediately.
