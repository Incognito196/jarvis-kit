# Jarvis core

A voice you can talk to, running on your own computer, wired to a real terminal.

You speak. It thinks with [Claude Code](https://claude.com/claude-code) — the actual CLI,
on your machine, with your files and your shell. It answers out loud. When you ask it to
do something, it does it, then tells you what happened.

It ships knowing nothing about you. What it *can* do is whatever agents you give it.

```bash
git clone https://github.com/YOURNAME/jarvis-core.git ~/jarvis-core
cd ~/jarvis-core && ./install.sh
```

Then open `http://127.0.0.1:8722`, tap the mic, and talk.

Runs on macOS (launchd) and Linux (systemd --user). Stdlib Python only — no framework, no
database, no container. About 1,300 lines you can read in an afternoon.

---

## What you get

- **The bridge** — one local HTTP server. Holds one continuous Claude Code session,
  rotating it before it gets slow, with a memory log so continuity survives restarts.
- **The face** — one HTML file. Wake word, barge-in (talk over it and it stops),
  sentence-by-sentence speech so the voice starts before the reply is finished.
- **A free voice** — Microsoft's neural TTS, no API key. Offline options if you want them.
- **Model routing** — chat runs on a fast model; code, diagnosis and anything that *acts*
  escalates automatically and stays escalated for a couple of follow-ups. You never pick.
- **Agents** — the part that makes it yours.

## Agents

An agent is a folder that teaches your Jarvis one skill:

```
agents/thermostat/
  agent.json     what it is, and its settings
  soul.md        how the brain should use it, in plain prose
  agent.py       optional: a panel on the face, live facts, HTTP routes
```

```bash
./jarvisctl agents                    # what's installed, what's on
./jarvisctl enable nodes              # switch a shipped one on
./jarvisctl new thermostat --private  # scaffold your own, outside git
```

Three ship with it: `system` (vitals for this machine, on by default), `nodes`
(reachability for other machines you list), `androidtv` (drive a Google TV or Fire TV
over ADB — "put on the Bebop opening" works).

That is the whole idea. One person's Jarvis runs their media server and their
thermostat; another's runs a warehouse. Same core underneath, and you both `git pull`.

Write your own: **[docs/AGENTS.md](docs/AGENTS.md)**.
Keep your life out of the repo: **[docs/PRIVATE-AGENTS.md](docs/PRIVATE-AGENTS.md)**.

## Its character

`soul/SOUL.md` is the system prompt — who it is, how short to keep replies, what it must
confirm before doing. The installer writes you one from a template that already knows the
important part: it is being spoken aloud, so no markdown, no bullet lists, one to three
sentences. Edit it any time; it is re-read on every turn, no restart needed.

## Managing it

```bash
./jarvisctl status      # up? what model? last error?
./jarvisctl doctor      # check everything that commonly breaks
./jarvisctl soul        # the exact prompt the brain receives, agents included
./jarvisctl logs 40     # what it has been doing
./jarvisctl restart
```

## Understand this before you install it

This runs Claude Code with `--dangerously-skip-permissions`. That is what makes it useful
— it can actually fix the thing instead of asking twice — and it means **anything holding
the action token can run commands on your machine as you.**

So:

- The bridge binds `127.0.0.1` and will not bind anything else for you. To use it from
  your phone, put it behind a private tunnel (Tailscale Serve, Cloudflare Tunnel,
  WireGuard). Do not expose the port to the internet.
- `JARVIS_TOKEN` in `.env` is a password. The face page only receives it for a viewer the
  bridge can identify; everyone else gets a read-only page.
- `JARVIS_WORKDIR` (default `~`) is a real security boundary — file tools can read
  anything under it. Don't point it at a folder full of secrets.
- Your soul file should carry a **seatbelt rule**: confirm before anything that spends
  money, messages another person, deletes data, or touches a different machine. The
  shipped template has one. Keep it.
- Every turn is logged to `logs/actions.log` and `logs/conversation.jsonl`. Those logs are
  a transcript of your life. They stay local; keep them that way.

## Requirements

- Python 3.9+
- Claude Code CLI, logged in. A background service can't read your keychain, so if it
  reports auth errors run `claude setup-token` and put the token in `.env`.
- macOS or Linux. Chrome, Edge or Safari for the mic (Firefox has no speech recognition).
- Optional: `edge-tts` for the voice (the installer offers it), `ffmpeg` for the offline
  voices, `adb` for the TV agent.

## License

MIT. It's yours — rename it, restyle it, strip out half of it.
