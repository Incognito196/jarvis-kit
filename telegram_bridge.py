#!/usr/bin/env python3
"""Telegram bridge. You DM the bot -> same brain the face uses (bridge /think, so the
same session and the same memory) -> reply comes back in Telegram.

Trust-on-first-use: the FIRST chat that ever messages the bot becomes the owner and is
written to telegram_owner.txt. Everyone after that is refused. Message it yourself the
moment you start it — before you hand the bot's @name to anyone."""
import os, json, time, threading, urllib.request, urllib.parse

from jarvis_config import load_config, env

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = load_config()
OWNER = CONFIG["owner_name"]
ASSISTANT = CONFIG["assistant_name"]
MACHINE = CONFIG["machine_label"]
PORT = os.environ.get("JARVIS_PORT", "8722")
THINK = f"http://127.0.0.1:{PORT}/think"
OWNER_FILE = os.path.join(HERE, "telegram_owner.txt")
LOG_FILE = os.path.join(HERE, "logs", "telegram.log")


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


TOKEN = env("TELEGRAM_BOT_TOKEN")
JARVIS_TOKEN = env("JARVIS_TOKEN")
if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN missing from .env — talk to @BotFather, then add it.")
API = f"https://api.telegram.org/bot{TOKEN}"


def api(method, **params):
    url = f"{API}/{method}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _chunks(text, size=4000):
    # Telegram hard-caps sendMessage at 4096 chars; anything longer 400s and the whole
    # reply is lost. Split on paragraph/line/space boundaries so we never drop the answer.
    text = text or ""
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = text.rfind(" ", 0, size)
        if cut <= 0:
            cut = size
        yield text[:cut]
        text = text[cut:].lstrip()
    if text:
        yield text


def send(chat_id, text):
    for part in _chunks(text):
        try:
            api("sendMessage", chat_id=chat_id, text=part)
        except Exception as e:
            log(f"send_failed chat={chat_id} len={len(part)} err={e}")


def send_typing(chat_id):
    try:
        api("sendChatAction", chat_id=chat_id, action="typing")
    except Exception as e:
        log(f"typing_failed chat={chat_id} err={e}")


def think(text, chat_id):
    # Telegram's "typing…" bubble expires after ~5s, so keep re-poking it while
    # /think (up to 600s) is still working — otherwise it flashes once and disappears.
    stop = threading.Event()

    def keep_typing():
        while not stop.is_set():
            send_typing(chat_id)
            stop.wait(4)

    t = threading.Thread(target=keep_typing, daemon=True)
    t.start()
    try:
        body = json.dumps({"text": text, "channel": "telegram"}).encode()
        req = urllib.request.Request(THINK, data=body,
                                      headers={"Content-Type": "application/json", "X-Jarvis-Token": JARVIS_TOKEN})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r).get("reply", "")
    finally:
        stop.set()


INBOX = os.path.join(HERE, "inbox")


def save_incoming_file(msg):
    """Owner sends a photo/document/voice note -> save it to inbox/ and return the path.
    Without this the bridge silently dropped every attachment (it only read text)."""
    file_id = name = None
    if msg.get("photo"):                                   # biggest rendition last
        file_id = msg["photo"][-1]["file_id"]
        name = f"photo_{int(time.time())}.jpg"
    elif msg.get("document"):
        file_id = msg["document"]["file_id"]
        name = msg["document"].get("file_name") or f"file_{int(time.time())}"
    elif msg.get("voice"):
        file_id = msg["voice"]["file_id"]
        name = f"voice_{int(time.time())}.oga"
    if not file_id:
        return None
    try:
        info = api("getFile", file_id=file_id)["result"]
        os.makedirs(INBOX, exist_ok=True)
        safe = "".join(c for c in name if c.isalnum() or c in "._- ")[:80] or "file"
        dest = os.path.join(INBOX, f"{time.strftime('%Y%m%d-%H%M%S')}_{safe}")
        url = f"https://api.telegram.org/file/bot{TOKEN}/{info['file_path']}"
        with urllib.request.urlopen(url, timeout=90) as r, open(dest, "wb") as f:
            f.write(r.read())
        log(f"saved_file {dest}")
        return dest
    except Exception as e:
        log(f"file_failed {e}")
        return None


_whisper_model = None


def transcribe(path):
    """Local speech-to-text (faster-whisper, base model, CPU/int8 — light enough for
    8GB RAM). Lazy-loaded on first voice note so the bridge stays cheap when idle."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        log("loading whisper model (first voice note)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = _whisper_model.transcribe(path, language=None)
    return " ".join(seg.text.strip() for seg in segments).strip()


def owner():
    return open(OWNER_FILE).read().strip() if os.path.exists(OWNER_FILE) else None


def set_owner(cid):
    open(OWNER_FILE, "w").write(str(cid))


def main():
    offset = 0
    while True:
        try:
            updates = api("getUpdates", offset=offset, timeout=30)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or msg.get("caption") or "").strip()
                has_file = bool(msg.get("photo") or msg.get("document"))
                has_voice = bool(msg.get("voice"))
                if not chat or (not text and not has_file and not has_voice):
                    continue
                own = owner()
                if own is None:                      # first messenger becomes the owner
                    set_owner(chat); own = str(chat)
                    send(chat, f"{ASSISTANT} online. This channel is now locked to you — same brain, same memory as the face.")
                    if text in ("/start", "/hello"):
                        continue
                if str(chat) != own:                 # anyone else: refuse
                    send(chat, "This is a private assistant. Access denied.")
                    continue
                if text in ("/start", "/hello"):
                    send(chat, f"Here, {OWNER}. Talk to me.")
                    continue
                if has_voice:
                    path = save_incoming_file(msg)
                    if not path:
                        send(chat, "That voice note didn't come through — try sending it again.")
                        continue
                    send_typing(chat)
                    try:
                        transcript = transcribe(path)
                    except Exception as e:
                        log(f"transcribe_failed {e}")
                        send(chat, "Couldn't transcribe that voice note — try again or type it out.")
                        continue
                    if not transcript:
                        send(chat, "Didn't catch anything in that voice note.")
                        continue
                    send(chat, f'Heard: "{transcript}"')
                    text = transcript
                elif has_file:
                    path = save_incoming_file(msg)
                    if not path:
                        send(chat, "That file didn't come through — try sending it again.")
                        continue
                    # Tell the brain a file landed so it can act on it in the same turn.
                    text = (f"[{OWNER} sent a file, saved on {MACHINE} at {path}]"
                            + (f" They said: {text}" if text else ""))
                    send(chat, f"Got it — saved to {path}")
                reply = think(text, chat)
                if reply:
                    send(chat, reply)
        except Exception as e:
            log(f"poll_error {e}")
            # 409 = another poller holds getUpdates (duplicate process). Back way off
            # so two pollers can't flood the log at 3s intervals for weeks.
            time.sleep(30 if "409" in str(e) else 3)


# Guard so `import telegram_bridge` (tests, debugging) can NEVER start a second
# poller — a stray import once ran a duplicate loop for 23 days of 409 conflicts.
if __name__ == "__main__":
    main()
