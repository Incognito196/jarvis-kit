#!/usr/bin/env bash
# Pre-push paranoia check: looks for things that should never be in a public repo.
# Run it before you commit, especially after copying an agent out of a private setup.
#
#   ./tools/check_private.sh
#
# It greps TRACKED files only, and it is deliberately noisy — a hit is not automatically
# a leak (an example IP in docs is fine), it is something for you to eyeball.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

hits=0
scan(){ # scan <label> <pattern>
  local label="$1" pat="$2" out
  out="$(git grep -nIE --untracked -- "$pat" -- . ':!tools/check_private.sh' ':!docs/*' 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    printf '\033[33m%s\033[0m\n%s\n\n' "$label" "$out"
    hits=$((hits+1))
  fi
}

echo "Scanning tracked files for private data…"
echo
scan "API keys / tokens"        '(sk-[A-Za-z0-9_-]{20,}|xoxb-|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})'
scan "Email addresses"          '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
scan "Private/VPN IP addresses" '\b(100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3})\b'
scan "Phone numbers"            '\+?1?[ .-]?\(?[0-9]{3}\)?[ .-][0-9]{3}[ .-][0-9]{4}'
scan "Home directory paths"     '/(Users|home)/[a-z][a-z0-9_-]+/'

if [[ $hits == 0 ]]; then
  printf '\033[32mClean.\033[0m Nothing that looks private in tracked files.\n'
else
  printf 'Review the %d category(ies) above. Examples in docs are fine; real values are not.\n' "$hits"
fi

# .env must never be tracked, full stop.
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  printf '\033[31mSTOP: .env is tracked by git.\033[0m  Run: git rm --cached .env\n'
  exit 1
fi
