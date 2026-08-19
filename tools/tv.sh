#!/bin/bash
# Android TV control over ADB (Google TV / Sony Bravia / Shield / Fire TV).
#
# Setup, once: enable Developer options on the TV, turn on "USB/Network debugging",
# then `adb connect <tv-ip>:5555` and ACCEPT the prompt on the TV screen. The
# authorization survives reboots; the socket does not survive the TV sleeping, so
# every call below re-connects first (idempotent, ~100ms).
#
# Set TV_HOST in config (or export it) to your TV's address.
TV="${TV_HOST:-192.168.1.50:5555}"
ADB="${ADB_BIN:-$(command -v adb || echo /opt/homebrew/bin/adb)}"
$ADB connect $TV >/dev/null 2>&1
A(){ $ADB -s $TV "$@"; }

case "$1" in
  status)
    st=$(A shell "dumpsys power | grep -m1 mWakefulness=; dumpsys window | grep -m1 mCurrentFocus" 2>/dev/null)
    [ -z "$st" ] && { echo "TV unreachable (asleep too deep or off tailnet)"; exit 1; }
    echo "$st" | sed 's/^ *//' ;;
  on)        A shell input keyevent KEYCODE_WAKEUP ;;
  off)       A shell input keyevent KEYCODE_SLEEP ;;   # standby, not full power-off
  home)      A shell input keyevent KEYCODE_HOME ;;
  back)      A shell input keyevent KEYCODE_BACK ;;
  ok)        A shell input keyevent KEYCODE_DPAD_CENTER ;;
  up|down|left|right) A shell input keyevent KEYCODE_DPAD_${1^^} ;;
  pause)     A shell input keyevent KEYCODE_MEDIA_PLAY_PAUSE ;;   # toggle
  stop)      A shell input keyevent KEYCODE_MEDIA_STOP ;;
  volup)     A shell input keyevent KEYCODE_VOLUME_UP ;;
  voldown)   A shell input keyevent KEYCODE_VOLUME_DOWN ;;
  mute)      A shell input keyevent KEYCODE_VOLUME_MUTE ;;
  play)
    # One-shot "put something on": search YouTube, play the top result. This is the
    # fast path for the brain — one tool call instead of improvising a scrape.
    shift; q="$*"
    [ -z "$q" ] && { echo "usage: tv.sh play <search terms>"; exit 1; }
    enc=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $q)
    vid=$(curl -s -m 8 "https://www.youtube.com/results?search_query=$enc" -H "User-Agent: Mozilla/5.0" | grep -o '"videoId":"[A-Za-z0-9_-]\{11\}"' | head -1 | cut -d'"' -f4)
    [ -z "$vid" ] && { echo "no result for: $q"; exit 1; }
    A shell am start -a android.intent.action.VIEW -d "https://www.youtube.com/watch?v=$vid" com.google.android.youtube.tv >/dev/null 2>&1
    echo "playing top YouTube result ($vid) for: $q" ;;
  youtube)
    if [ -n "$2" ]; then   # tv.sh youtube <video-url-or-id> plays it directly
      case "$2" in http*) url="$2" ;; *) url="https://www.youtube.com/watch?v=$2" ;; esac
      A shell am start -a android.intent.action.VIEW -d "$url" com.google.android.youtube.tv
    else
      A shell monkey -p com.google.android.youtube.tv 1 >/dev/null 2>&1 && echo "YouTube launched"
    fi ;;
  netflix)   A shell monkey -p com.netflix.ninja 1 >/dev/null 2>&1 && echo "Netflix launched" ;;
  prime)     A shell monkey -p com.amazon.amazonvideo.livingroom 1 >/dev/null 2>&1 && echo "Prime Video launched" ;;
  music)     A shell monkey -p com.google.android.youtube.tvmusic 1 >/dev/null 2>&1 && echo "YouTube Music launched" ;;
  # monkey injects ONE RANDOM input event along with the launch — fine for launching
  # streaming apps, never use it for our own app (it scrambles the OK-toggle state).
  app)       A shell monkey -p "$2" 1 >/dev/null 2>&1 && echo "launched $2" ;;
  type)      shift; A shell input text "$(printf '%s' "$*" | sed 's/ /%s/g')" ;;
  screenshot)
    f="/tmp/tv-$(date +%H%M%S).png"
    A exec-out screencap -p > "$f" 2>/dev/null && echo "$f" ;;
  install)   A install -r "$2" && echo "installed $(basename "$2")" ;;
  uninstall) A uninstall "$2" ;;
  apps)      A shell pm list packages "${2:+-3}" 2>/dev/null | sed 's/^package://' | grep -i "${2:-.}" ;;
  reconnect) $ADB disconnect $TV >/dev/null 2>&1; $ADB connect $TV ;;
  *) echo "usage: tv.sh status|on|off|home|back|ok|up|down|left|right|play <search>|pause|stop|volup|voldown|mute|youtube [url]|netflix|prime|music|app <pkg>|type <text>|screenshot|install <apk>|uninstall <pkg>|apps [filter]|reconnect" ;;
esac
