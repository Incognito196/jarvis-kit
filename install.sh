#!/usr/bin/env bash
# Jarvis core installer. Sets up .env, writes your soul file, installs the background
# service, starts it, and tells you where to point a browser.
#
#   ./install.sh              interactive
#   ./install.sh --yes        accept every default, ask nothing
#
# Safe to re-run: it never overwrites an existing .env or soul/SOUL.md without asking.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.jarvis.core"
SERVICE="jarvis-core"
ASSUME_YES=0
[[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && ASSUME_YES=1

bold(){ printf '\033[1m%s\033[0m\n' "$1"; }
ok(){   printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn(){ printf '  \033[33m!\033[0m %s\n' "$1"; }
die(){  printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }

ask(){ # ask <prompt> <default>
  local prompt="$1" def="$2" reply
  if [[ $ASSUME_YES == 1 ]]; then echo "$def"; return; fi
  read -r -p "$prompt [$def]: " reply </dev/tty || reply=""
  echo "${reply:-$def}"
}

bold "Jarvis core — install"
echo

# ---- 1. dependencies -------------------------------------------------------
PYTHON="$(command -v python3 || true)"
[[ -n "$PYTHON" ]] || die "python3 not found. Install Python 3.9 or newer."
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' \
  || die "python3 is too old ($($PYTHON -V)). Need 3.9+."
ok "python3 $("$PYTHON" -V | cut -d' ' -f2) at $PYTHON"

CLAUDE="$(command -v claude || true)"
if [[ -z "$CLAUDE" ]]; then
  warn "claude CLI not on PATH."
  echo "     Jarvis has no brain without it: https://claude.com/claude-code"
  CLAUDE="$(ask '     Path to the claude binary (blank to set later)' '')"
fi
[[ -n "$CLAUDE" ]] && ok "claude CLI at $CLAUDE"

if "$PYTHON" -m edge_tts --help >/dev/null 2>&1; then
  ok "edge-tts installed (free neural voice)"
else
  if [[ "$(ask 'Install edge-tts for the voice? (y/n)' 'y')" == "y" ]]; then
    "$PYTHON" -m pip install --quiet --user edge-tts 2>/dev/null \
      || "$PYTHON" -m pip install --quiet --break-system-packages edge-tts 2>/dev/null \
      || warn "pip install edge-tts failed — Jarvis will fall back to the browser voice"
    "$PYTHON" -m edge_tts --help >/dev/null 2>&1 && ok "edge-tts installed"
  else
    warn "no edge-tts: the face will use the browser's own voice"
  fi
fi
command -v ffmpeg >/dev/null 2>&1 && ok "ffmpeg present" \
  || warn "no ffmpeg (only needed for the say/piper/kokoro voices)"
echo

# ---- 2. identity + .env ----------------------------------------------------
if [[ -f "$ROOT/.env" ]]; then
  ok ".env already exists — leaving it alone"
else
  NAME="$(ask 'What should it be called?' 'Jarvis')"
  OWNER="$(ask 'What should it call you? (blank for nothing)' '')"
  PORT="$(ask 'Port' '8722')"
  VOICE="$(ask 'Voice engine (edge/say/kokoro/piper/browser)' 'edge')"
  TOKEN="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')"

  sed -e "s|^JARVIS_NAME=.*|JARVIS_NAME=$NAME|" \
      -e "s|^JARVIS_OWNER=.*|JARVIS_OWNER=$OWNER|" \
      -e "s|^JARVIS_PORT=.*|JARVIS_PORT=$PORT|" \
      -e "s|^JARVIS_VOICE=.*|JARVIS_VOICE=$VOICE|" \
      "$ROOT/.env.example" > "$ROOT/.env"
  {
    echo ""
    echo "JARVIS_TOKEN=$TOKEN"
    [[ -n "$CLAUDE" ]] && echo "CLAUDE_BIN=$CLAUDE"
  } >> "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  ok "wrote .env (0600) with a fresh action token"
fi

# read back whatever is authoritative now
NAME="$(grep -E '^JARVIS_NAME=' "$ROOT/.env" | cut -d= -f2- || echo Jarvis)"
PORT="$(grep -E '^JARVIS_PORT=' "$ROOT/.env" | cut -d= -f2- || echo 8722)"
NAME="${NAME:-Jarvis}"; PORT="${PORT:-8722}"

# ---- 3. the soul -----------------------------------------------------------
if [[ -f "$ROOT/soul/SOUL.md" ]]; then
  ok "soul/SOUL.md already exists — leaving it alone"
else
  TONE="$(ask 'Describe its personality in one line' 'Calm, capable, a little wry. A competent right hand, not a hype machine.')"
  sed -e "s|{{NAME}}|$NAME|g" \
      -e "s|{{HOST}}|$(hostname -s)|g" \
      -e "s|{{ROOT}}|$ROOT|g" \
      -e "s|{{TONE}}|$TONE|g" \
      "$ROOT/soul/SOUL.template.md" > "$ROOT/soul/SOUL.md"
  ok "wrote soul/SOUL.md — edit it any time, no restart needed"
fi
mkdir -p "$ROOT/logs"

# ---- 4. the service --------------------------------------------------------
echo
if [[ "$(uname -s)" == "Darwin" ]]; then
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  mkdir -p "$(dirname "$PLIST")"
  sed -e "s|__LABEL__|$LABEL|g" -e "s|__PYTHON__|$PYTHON|g" \
      -e "s|__ROOT__|$ROOT|g" -e "s|__HOME__|$HOME|g" \
      -e "s|__PATH__|$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin|g" \
      "$ROOT/packaging/launchd.plist.template" > "$PLIST"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  ok "launchd agent installed and started ($LABEL)"
  RESTART="launchctl kickstart -k gui/$(id -u)/$LABEL"
else
  UNIT="$HOME/.config/systemd/user/$SERVICE.service"
  mkdir -p "$(dirname "$UNIT")"
  sed -e "s|__PYTHON__|$PYTHON|g" -e "s|__ROOT__|$ROOT|g" \
      -e "s|__PATH__|$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin|g" \
      "$ROOT/packaging/systemd.service.template" > "$UNIT"
  systemctl --user daemon-reload
  systemctl --user enable --now "$SERVICE"
  # Without this, the service dies the moment you log out of your SSH session.
  loginctl enable-linger "$USER" 2>/dev/null || warn "could not enable linger — it will stop when you log out"
  ok "systemd user service installed and started ($SERVICE)"
  RESTART="systemctl --user restart $SERVICE"
fi

# ---- 5. did it actually come up? -------------------------------------------
echo
printf '  waiting for the bridge'
UP=0
for _ in $(seq 1 20); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then UP=1; break; fi
  printf '.'; sleep 0.5
done
echo
if [[ $UP == 1 ]]; then
  ok "$NAME is up at http://127.0.0.1:$PORT"
else
  warn "nothing answered on port $PORT yet"
  echo "     check: tail -20 $ROOT/logs/bridge.err"
fi

echo
bold "Next"
cat <<EOF
  Open            http://127.0.0.1:$PORT   (tap the mic, or just type)
  Check it        ./jarvisctl doctor
  See its skills  ./jarvisctl agents
  Teach it one    ./jarvisctl new my-skill --private
  Its character   edit soul/SOUL.md  (no restart needed)
  After changes   $RESTART

  To reach it from your phone, put it behind a private tunnel — Tailscale Serve or
  Cloudflare Tunnel. Do not bind it to 0.0.0.0: anything that can reach the port and
  holds the token can run commands on this machine.
EOF
