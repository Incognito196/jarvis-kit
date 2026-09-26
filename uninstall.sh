#!/usr/bin/env bash
# Removes the background service. Leaves your .env, soul, agents and logs alone —
# delete the folder yourself if you want those gone too.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.jarvis.core"; SERVICE="jarvis-core"

if [[ "$(uname -s)" == "Darwin" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
  echo "launchd agent removed."
else
  systemctl --user disable --now "$SERVICE" 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/$SERVICE.service"
  systemctl --user daemon-reload
  echo "systemd service removed."
fi
echo "Kept: $ROOT/.env, soul/, agents/, logs/, and ~/.jarvis/"
