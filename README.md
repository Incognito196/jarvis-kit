# JARVIS Kit

Give Claude a voice, a face, and hands on your machine.

JARVIS Kit turns a Mac (best) or any Unix box (mostly) into a personal AI operations
agent: you talk to it out loud through an animated face in the browser, or text it
over Telegram or iMessage, and it answers — and *acts*. Because the brain is a real
[Claude Code](https://claude.com/claude-code) session, it can run commands, read
files, SSH into your other machines, and fix things, not just chat about them.

This is the generalized, installable version of the JARVIS that runs in the
author's setup. Nothing personal ships in this repo — the installer asks who you
are and writes your identity locally.

## What you get

- **The face** — an animated assistant face with a live system panel (CPU, RAM,
  your machines' status) served at `http://localhost:8722`. Open it in Chrome,
  say the wake word, talk.
- **The brain** — your local `claude` CLI run headless with a persistent session:
  one continuous conversation across voice, Telegram, and iMessage. A built-in
  router answers small talk on a fast model and escalates real work to a
  stronger one, automatically.
- **The voice** — free Microsoft Edge neural TTS (bilingual, near-zero CPU),
  spoken sentence-by-sentence so replies start fast. Falls back to the macOS
  `say` voice, or offline Kokoro if you install it.
- **The channels** — optional Telegram bridge (any @BotFather bot) and optional
  iMessage bridge (macOS only; reads and sends real texts).
- **The hands** — whatever your machine can do, the agent can do: shell, files,
  and any SSH access the install user already has. The fleet panel lights up if
  Tailscale is present.
- **The seatbelt** — the soul template ships with confirmation rules for
  anything irreversible (spending, sending, deleting, writing to remote hosts),
  and the bridge authenticates every request with a local token.

## Requirements

- **Claude Code CLI**, logged in (a Claude subscription). This is the brain;
  nothing works without it.
- **python3** ≥ 3.9 (stdlib only — no pip packages required; `edge-tts` is an
  optional install for the good voice, `ffmpeg` for some engines).
- **macOS** for the full experience (launchd services, iMessage). The bridge and
  face run on Linux too; you supervise the process yourself.
- Optional: Tailscale (fleet panel + remote access), a Telegram bot token.

## Install

```bash
git clone <this-repo> jarvis && cd jarvis
./install.sh
```

The installer is interactive and idempotent — re-run it after upgrades and it
keeps your `config.json`, `.env`, and `soul.md`. It will:

1. Check prerequisites (and tell you exactly what's missing).
2. Ask who the assistant is (name = wake word), who you are, and where this
   machine sits in your world → writes `config.json`.
3. Generate a fresh local auth token → writes `.env` (chmod 600).
4. Render `soul.template.md` → `soul.md`, the assistant's personality and rules.
5. Install and start the launchd services (`--no-start` to skip starting).

Then, in order:

1. **Edit `soul.md`.** It's the difference between a toy and an assistant —
   who you are, what machines you own, what it may and may not do.
2. Add your other machines to `"nodes"` in `config.json` to light the fleet panel.
3. Open `http://localhost:8722` in Chrome (mic requires localhost or HTTPS) and
   say the wake word.
4. If you set up Telegram: DM your bot **now** — the first chat to message it
   becomes the owner and everyone else is ignored.
5. If you enabled iMessage: grant Full Disk Access to your `python3` binary
   (System Settings → Privacy & Security), and re-grant it whenever Homebrew
   upgrades Python — the grant is pinned to the exact binary.

## Day-2 operations

| Thing | How |
|---|---|
| Health check | `curl -s http://localhost:8722/health` |
| Dashboard | `http://localhost:8722/dashboard` |
| Restart after a code/env change | `launchctl kickstart -k gui/$(id -u)/com.<prefix>.jarvis` |
| Logs | `logs/actions.log` (what it did), `logs/conversation.jsonl` (what was said) |
| Change the voice | `JARVIS_VOICE` / `EDGE_VOICE` in `.env` — voice hot-reloads |
| Pin one model | `JARVIS_MODEL` in `.env` + restart (disables the router) |

## Security model, honestly

This gives an AI agent shell access as your user. Treat it accordingly:

- The bridge binds to **localhost** and requires a token on every acting
  endpoint. Exposing it beyond the machine is your call — if you do, use
  something authenticated end-to-end (e.g. `tailscale serve`), never a raw
  port-forward.
- The agent can do anything *you* can do in a terminal, including using your
  SSH keys. Give this machine only the reach you want the agent to have.
- The soul's seatbelt rules are behavioral, not a sandbox. For hard guarantees,
  add OS-level controls (a dedicated user account, Claude Code permission
  settings, hooks).
- `.gitignore` already excludes everything identity-bearing: `.env`,
  `config.json`, `soul.md`, session state, logs.

## Layout

```
bridge.py              the switchboard: HTTP server, brain runner, model router, TTS
index.html             the face
dashboard.html         status dashboard
telegram_bridge.py     optional Telegram relay
imessage_bridge.py     optional iMessage relay (macOS)
jarvis_config.py       loads config.json, shared by all three
soul.template.md       personality/rules template → your private soul.md
launchd/               service templates the installer renders
install.sh             the only command you run
tools/tv.sh            example "hands": an ADB Android-TV remote
tests/                 router tests: python3 -m pytest tests/
```
