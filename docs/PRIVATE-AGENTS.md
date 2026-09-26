# Keeping your own life out of the repo

The interesting agents are the ones nobody else should see: your house, your business,
your credentials, your family. There is a place for them that is not this repo.

## ~/.jarvis/agents/

Anything under `~/.jarvis/agents/<name>/` loads exactly like a shipped agent — same
manifest, same hooks, same panels. It is simply outside the checkout, so it cannot be
committed by accident.

```bash
./jarvisctl new my-business --private     # scaffolds into ~/.jarvis/agents/
```

A private agent with the same name as a shipped one **wins**, so you can override any
default without editing a tracked file and creating a merge conflict on the next pull.

## Two repos, not one

The setup that works:

```
~/jarvis-core/          public: the bridge, the face, generic agents.  git pull updates it.
~/.jarvis/
  agents.json           what's on, what's configured, on THIS machine
  agents/               your private agents  <- make this its own private git repo
```

Your private folder can be a repo too:

```bash
cd ~/.jarvis && git init && git remote add origin git@github.com:you/jarvis-private.git
```

Now you can move your whole assistant to a new machine in two clones, and share the
public half with a friend without sharing a single thing about your life.

## What belongs where

| Thing | Where |
|-------|-------|
| bridge, face, installer | the public repo |
| an agent anyone could use | the public repo, config-driven, with example values |
| your machine names, IPs, hostnames | `config` in `~/.jarvis/agents.json` |
| API keys, tokens, passwords | `.env` (gitignored) or your OS keychain |
| your personality file | `soul/SOUL.md` (gitignored; the template is what ships) |
| anything about a real person | `~/.jarvis/agents/` |

## Before you push

```bash
./tools/check_private.sh
```

It greps tracked files for keys, emails, phone numbers, VPN and LAN addresses, and home
directory paths. It is deliberately noisy: a hit is something to eyeball, not
automatically a leak.

And remember what a scan cannot fix: **git history is public too.** If a secret was ever
committed, rotating it is the only real remedy. Scrubbing history after the fact is
unreliable and assumes nobody cloned in between.
