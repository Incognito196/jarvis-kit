#!/bin/bash
# JARVIS installer. Interactive, idempotent, and it never overwrites your answers:
# run it again after an upgrade and it keeps your existing config.json / .env / soul.md.
#
#   ./install.sh            interactive setup + load the launchd jobs
#   ./install.sh --no-start configure everything but don't load anything
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
NO_START=0
[[ "${1:-}" == "--no-start" ]] && NO_START=1

bold(){ printf "\033[1m%s\033[0m\n" "$*"; }
ok(){   printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn(){ printf "  \033[33m!\033[0m %s\n" "$*"; }
die(){  printf "  \033[31m✗\033[0m %s\n" "$*" >&2; exit 1; }

# ask VAR "Prompt" "default"  — keeps the default on an empty answer
ask(){ local __v=$1 __p=$2 __d=${3:-} __r
       read -r -p "  $__p${__d:+ [$__d]}: " __r </dev/tty || true
       printf -v "$__v" '%s' "${__r:-$__d}"; }

bold "JARVIS — install"
echo

# ---------- 1. prerequisites -------------------------------------------------
bold "1. Checking prerequisites"
[[ "$(uname)" == "Darwin" ]] || warn "Not macOS. The bridge and voice mostly work; launchd + iMessage do not."

PYTHON="$(command -v python3 || true)"
[[ -n "$PYTHON" ]] || die "python3 not found. Install it (brew install python) and re-run."
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' \
  || die "python3 is $("$PYTHON" -V) — need 3.9+."
ok "python3: $PYTHON ($("$PYTHON" -V 2>&1))"

# The brain. Everything else is decoration without it.
CLAUDE_BIN="$(command -v claude || true)"
[[ -z "$CLAUDE_BIN" && -x "$HOME/.local/bin/claude" ]] && CLAUDE_BIN="$HOME/.local/bin/claude"
if [[ -n "$CLAUDE_BIN" ]]; then
  ok "claude CLI: $CLAUDE_BIN"
else
  warn "claude CLI not found. Install it (https://claude.com/claude-code) — the bridge needs it to think."
  ask CLAUDE_BIN "Path to the claude binary (or leave blank to fix later)" ""
fi

TAILSCALE_BIN="$(command -v tailscale || true)"
[[ -z "$TAILSCALE_BIN" && -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]] \
  && TAILSCALE_BIN=/Applications/Tailscale.app/Contents/MacOS/Tailscale
if [[ -n "$TAILSCALE_BIN" ]]; then ok "tailscale: $TAILSCALE_BIN"
else warn "tailscale not found — the fleet panel will just sit empty. That's fine."; TAILSCALE_BIN="/usr/local/bin/tailscale"; fi
echo

# ---------- 2. identity ------------------------------------------------------
bold "2. Who is this?"
if [[ -f config.json ]]; then
  ok "config.json already exists — keeping it. Delete it and re-run to start over."
else
  ask ASSISTANT_NAME "Assistant name (one word, also the wake word)" "JARVIS"
  ask OWNER_NAME     "What should it call you"                        "boss"
  ask MACHINE_LABEL  "Label for this machine (shown on the face)"     "$(scutil --get ComputerName 2>/dev/null || hostname)"
  ask SELF_NODE      "This machine's name in your fleet list"         "$(hostname -s)"
  ask TIMEZONE       "Timezone"                                        "$(readlink /etc/localtime 2>/dev/null | sed 's|.*zoneinfo/||' || echo America/New_York)"
  ask WLAT           "Weather latitude"                                "40.7128"
  ask WLON           "Weather longitude"                               "-74.006"
  ask OWNER_PHONE    "Your phone in E.164 for the iMessage bridge (blank to skip)" ""

  # Fuzzy wake pattern: speech recognition doubles letters constantly, so we accept
  # repeats of each letter. "jarvis" -> \bj+a+r+v+i+s+\b, which also catches "jarrvis".
  WAKE_LOWER="$(printf '%s' "$ASSISTANT_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
  WAKE_BODY="$("$PYTHON" -c 'import sys; print("".join(c+"+" for c in sys.argv[1]))' "$WAKE_LOWER")"
  WAKE_REGEX="\\\\b${WAKE_BODY}\\\\b"

  ASSISTANT_NAME="$ASSISTANT_NAME" OWNER_NAME="$OWNER_NAME" MACHINE_LABEL="$MACHINE_LABEL" \
  SELF_NODE="$SELF_NODE" TIMEZONE="$TIMEZONE" WLAT="$WLAT" WLON="$WLON" \
  OWNER_PHONE="$OWNER_PHONE" TAILSCALE_BIN="$TAILSCALE_BIN" WAKE_REGEX="$WAKE_REGEX" \
  "$PYTHON" - <<'PYEOF'
import json, os
cfg = {
    "assistant_name": os.environ["ASSISTANT_NAME"],
    "owner_name":     os.environ["OWNER_NAME"],
    "machine_label":  os.environ["MACHINE_LABEL"],
    "wake_regex":     os.environ["WAKE_REGEX"].replace("\\\\", "\\"),
    "timezone":       os.environ["TIMEZONE"],
    "weather_lat":    float(os.environ["WLAT"] or 40.7128),
    "weather_lon":    float(os.environ["WLON"] or -74.006),
    "tailscale_bin":  os.environ["TAILSCALE_BIN"],
    "self_node":      os.environ["SELF_NODE"],
    "nodes":          [{"name": os.environ["SELF_NODE"], "ip": ""}],
    "watch_service":  "",
    "extra_act_words": [],
    "owner_phone":    os.environ["OWNER_PHONE"],
}
with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PYEOF
  ok "wrote config.json"
  warn "Add your other machines to the \"nodes\" list in config.json to light up the fleet panel."
fi
echo

# ---------- 3. secrets -------------------------------------------------------
bold "3. Secrets"
if [[ -f .env ]]; then
  ok ".env already exists — keeping it."
else
  cp .env.example .env
  # The bridge auto-generates a token on first boot, but doing it here means the
  # Telegram/iMessage bridges can read the same one even if they start first.
  TOKEN="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')"
  "$PYTHON" - "$TOKEN" <<'PYEOF'
import sys
tok = sys.argv[1]
s = open(".env").read().replace("JARVIS_TOKEN=\n", f"JARVIS_TOKEN={tok}\n", 1)
open(".env", "w").write(s)
PYEOF
  ok "wrote .env with a fresh JARVIS_TOKEN"
fi
chmod 600 .env
ok ".env is chmod 600"

ask TG_TOKEN "Telegram bot token from @BotFather (blank to skip Telegram)" ""
if [[ -n "$TG_TOKEN" ]]; then
  "$PYTHON" - "$TG_TOKEN" <<'PYEOF'
import re, sys
tok = sys.argv[1]
s = open(".env").read()
s = re.sub(r"(?m)^TELEGRAM_BOT_TOKEN=.*$", f"TELEGRAM_BOT_TOKEN={tok}", s)
open(".env", "w").write(s)
PYEOF
  ok "Telegram token saved"
fi
echo

# ---------- 4. soul ----------------------------------------------------------
bold "4. Soul"
if [[ -f soul.md ]]; then
  ok "soul.md already exists — keeping it."
else
  ASSIST="$("$PYTHON" -c 'import json;print(json.load(open("config.json"))["assistant_name"])')"
  OWNR="$("$PYTHON"   -c 'import json;print(json.load(open("config.json"))["owner_name"])')"
  MACH="$("$PYTHON"   -c 'import json;print(json.load(open("config.json"))["machine_label"])')"
  PREFIX_GUESS="$(id -un)"
  sed -e "s|{{ASSISTANT_NAME}}|$ASSIST|g" \
      -e "s|{{OWNER_NAME}}|$OWNR|g" \
      -e "s|{{MACHINE_NAME}}|$MACH|g" \
      -e "s|{{INSTALL_DIR}}|$HERE|g" \
      -e "s|{{LAUNCHD_LABEL}}|com.$PREFIX_GUESS.jarvis|g" \
      -e "s|{{VOICE}}|edge|g" \
      -e "s|{{TONE}}|Calm, capable, a little wry — a competent right hand, not a hype machine.|g" \
      soul.template.md > soul.md
  ok "wrote soul.md from the template — EDIT IT. It's what makes this yours."
fi
echo

# ---------- 5. voice ---------------------------------------------------------
bold "5. Voice"
if "$PYTHON" -c 'import edge_tts' 2>/dev/null; then
  ok "edge-tts installed (free Microsoft neural voices)"
else
  warn "edge-tts not installed — falling back to the macOS 'say' voice."
  echo "     Install the good voice with:  $PYTHON -m pip install --user edge-tts"
fi
command -v ffmpeg >/dev/null && ok "ffmpeg present" || warn "ffmpeg missing (brew install ffmpeg) — some voice engines need it."
echo

# ---------- 6. launchd -------------------------------------------------------
bold "6. Services"
mkdir -p logs inbox
ask PREFIX "launchd label prefix (jobs become com.PREFIX.jarvis)" "$(id -un)"
LA="$HOME/Library/LaunchAgents"
mkdir -p "$LA"
SHELL_PATH="$(dirname "${CLAUDE_BIN:-/usr/bin/true}"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

install_job(){
  local name=$1 tmpl="launchd/com.__PREFIX__.$1.plist.template" dest="$LA/com.$PREFIX.$1.plist"
  sed -e "s|__PREFIX__|$PREFIX|g" \
      -e "s|__PYTHON__|$PYTHON|g" \
      -e "s|__INSTALL_DIR__|$HERE|g" \
      -e "s|__HOME__|$HOME|g" \
      -e "s|__PATH__|$SHELL_PATH|g" \
      -e "s|__VOICE__|edge|g" \
      -e "s|__EDGE_VOICE__|en-US-AndrewMultilingualNeural|g" \
      "$tmpl" > "$dest"
  plutil -lint "$dest" >/dev/null || die "generated a malformed plist: $dest"
  ok "wrote $dest"
  if [[ $NO_START -eq 0 ]]; then
    # bootout first so re-running the installer reloads cleanly instead of erroring.
    launchctl bootout "gui/$(id -u)/com.$PREFIX.$1" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$dest" && ok "loaded com.$PREFIX.$1"
  fi
}

install_job jarvis
[[ -n "$TG_TOKEN" || -n "$(grep -m1 '^TELEGRAM_BOT_TOKEN=.\+' .env || true)" ]] && install_job jarvis-telegram
OWNER_PHONE_SET="$("$PYTHON" -c 'import json;print(json.load(open("config.json")).get("owner_phone",""))')"
if [[ -n "$OWNER_PHONE_SET" ]]; then
  install_job jarvis-imessage
  warn "iMessage needs Full Disk Access for $PYTHON:"
  warn "  System Settings → Privacy & Security → Full Disk Access → add that binary."
fi
echo

# ---------- done -------------------------------------------------------------
PORT="$(grep -m1 '^JARVIS_PORT=' .env | cut -d= -f2 || true)"; PORT="${PORT:-8722}"
bold "Done."
echo
echo "  Face:       http://localhost:$PORT/"
echo "  Dashboard:  http://localhost:$PORT/dashboard"
echo "  Health:     curl -s http://localhost:$PORT/health"
echo
echo "  Next, in order:"
echo "    1. Edit soul.md — it's the difference between a toy and an assistant."
echo "    2. Add your machines to \"nodes\" in config.json."
echo "    3. Open the face in Chrome (mic needs localhost or https) and say the wake word."
if [[ -n "$TG_TOKEN" ]]; then
echo "    4. DM your Telegram bot NOW — the first chat to message it becomes the owner."
fi
echo
echo "  Restart after a change:  launchctl kickstart -k gui/$(id -u)/com.$PREFIX.jarvis"
