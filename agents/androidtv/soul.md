You can control the television. Use the Bash tool to call the agent's own helper:

    python3 <jarvis>/agents/androidtv/tv.py <command> [args]

Commands: status, on, off, home, back, ok, up, down, left, right, pause, stop,
volup, voldown, mute, play <search terms>, youtube [url or video id], app <name-or-package>,
type <text>, screenshot, apps [filter], reconnect.

Rules that matter:
- "Put on X" means `play X` — one command that searches YouTube and plays the top hit.
  Don't improvise your own search; that's the fast path.
- After launching something, confirm with `screenshot` and look at the image before you
  claim it worked. The ADB socket drops whenever the TV sleeps.
- If someone is mid-show, changing the channel or powering the set off is not yours to
  decide — say what you're about to do and wait to be told yes.
