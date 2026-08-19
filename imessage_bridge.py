#!/usr/bin/env python3
"""Two-way iMessage bridge (macOS only): you text the Mac, it runs the message through
the SAME brain the face uses (bridge /think = same session, same memory) and texts back.

Only answers your OWN direct thread — never a group chat. Read-only on chat.db.

Requires Full Disk Access for whatever python3 runs this (System Settings -> Privacy &
Security -> Full Disk Access). Without it, reading chat.db fails silently-ish and the
bridge just never sees a message. Set owner_phone in config.json first."""
import os, time, json, sqlite3, subprocess, urllib.request

from jarvis_config import load_config, env

DB = os.path.expanduser("~/Library/Messages/chat.db")
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = load_config()
ASSISTANT = CONFIG["assistant_name"]
OWNER_HANDLE = CONFIG.get("owner_phone", "").strip()
if not OWNER_HANDLE:
    raise SystemExit('owner_phone missing from config.json (e.g. "+15551234567") — '
                     "the iMessage bridge has no idea who to listen to.")
# Handles are stored inconsistently (+1 prefix, dashes, bare). Match on the last 10
# digits so every stored form of your number hits the same thread.
OWNER_LIKE = "%" + "".join(c for c in OWNER_HANDLE if c.isdigit())[-10:]
PORT = os.environ.get("JARVIS_PORT", "8722")
THINK = f"http://127.0.0.1:{PORT}/think"
LOG_FILE = os.path.join(HERE, "logs", "imessage.log")
HELLO_MARKER = os.path.join(HERE, "logs", ".imessage_hello_sent")


JARVIS_TOKEN = env("JARVIS_TOKEN")


LOG_MAX_BYTES = 5 * 1024 * 1024  # rotate one .bak instead of growing forever


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        try:
            if os.path.getsize(LOG_FILE) > LOG_MAX_BYTES:
                os.replace(LOG_FILE, LOG_FILE + ".bak")
        except OSError:
            pass
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{msg}\n")
    except Exception:
        pass


def decode_attributed_body(blob):
    """Modern macOS stores many messages only in attributedBody (a typedstream blob) with
    m.text NULL. Best-effort extraction of the plain string so those aren't invisible."""
    if not blob:
        return ""
    try:
        data = bytes(blob)
        if b"NSString" not in data:
            return ""
        data = data.split(b"NSString", 1)[1][5:]   # skip class marker + header bytes
        if data[0:1] == b"\x81":                    # 2-byte little-endian length prefix
            length = int.from_bytes(data[1:3], "little"); data = data[3:]
        else:                                        # single-byte length
            length = data[0]; data = data[1:]
        return data[:length].decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def q(sql, args=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def latest_date():
    r = q("SELECT COALESCE(MAX(date),0) FROM message m JOIN handle h ON m.handle_id=h.ROWID "
          "WHERE h.id LIKE ?", (OWNER_LIKE,))
    return r[0][0] or 0


def new_msgs(after):
    # is_from_me=0 (his), direct thread only (cache_roomnames IS NULL => not a group).
    # No text-not-null filter: pull attributedBody too and decode it, or modern messages
    # (text NULL) are silently invisible. Skip tapbacks/reactions (associated_message_type!=0).
    rows = q("SELECT m.date, m.text, m.attributedBody FROM message m JOIN handle h ON m.handle_id=h.ROWID "
             "WHERE h.id LIKE ? AND m.is_from_me=0 AND m.date>? AND m.cache_roomnames IS NULL "
             "AND COALESCE(m.associated_message_type,0)=0 ORDER BY m.date ASC", (OWNER_LIKE, after))
    out = []
    for date, text, blob in rows:
        body = (text or "").strip() or decode_attributed_body(blob)
        if body:
            out.append((date, body))
    return out


def think(text):
    body = json.dumps({"text": text, "channel": "imessage"}).encode()
    req = urllib.request.Request(THINK, data=body,
                                  headers={"Content-Type": "application/json", "X-Jarvis-Token": JARVIS_TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r).get("reply", "")


def send(msg):
    env = dict(os.environ, JARVIS_MSG=msg)
    subprocess.run(["osascript", "-e",
        'tell application "Messages" to send (system attribute "JARVIS_MSG") to '
        'participant "' + OWNER_HANDLE + '" of (1st account whose service type = iMessage)'],
        env=env, timeout=30)


def main():
    after = latest_date()
    # Only greet on the FIRST ever launch — a launchd crash-loop must not spam you with hellos.
    if not os.path.exists(HELLO_MARKER):
        try:
            send(f"{ASSISTANT} here — text me and I'll answer from the Mac. Same brain, same memory as the face.")
            os.makedirs(os.path.dirname(HELLO_MARKER), exist_ok=True)
            open(HELLO_MARKER, "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            log(f"hello_failed {e}")
    while True:
        try:
            for date, text in new_msgs(after):
                after = max(after, date)
                reply = think(text)
                if reply:
                    send(reply)
        except Exception as e:
            log(f"poll_error {e}")
        time.sleep(4)


# Guard so `import imessage_bridge` (tests, debugging) can never start a duplicate poller.
if __name__ == "__main__":
    main()
