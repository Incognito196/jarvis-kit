#!/usr/bin/env python3
"""Model-routing tests. No network, no claude CLI — pure logic.

    python3 tests/test_routing.py

Routing is the thing that quietly costs money when it breaks: if everything escalates
you burn the expensive model on "what time is it", and if nothing escalates the fast
model tries to run your infrastructure. Both failures are silent. Hence these.
"""
import importlib.util, os, sys, json, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_bridge(config):
    """Import bridge.py against a throwaway config so tests don't read your real one."""
    tmp = tempfile.mkdtemp()
    for f in ("bridge.py", "jarvis_config.py"):
        shutil.copy(os.path.join(ROOT, f), tmp)
    with open(os.path.join(tmp, "config.json"), "w") as fh:
        json.dump(config, fh)
    open(os.path.join(tmp, ".env"), "w").write("JARVIS_TOKEN=test\n")
    for var in ("JARVIS_MODEL", "JARVIS_FAST_MODEL", "JARVIS_MIDDLE_MODEL"):
        os.environ.pop(var, None)
    sys.path.insert(0, tmp)
    spec = importlib.util.spec_from_file_location("bridge_under_test",
                                                  os.path.join(tmp, "bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONFIG = {
    "assistant_name": "TESTBOT", "owner_name": "chief",
    "self_node": "test-node",
    "nodes": [{"name": "test-node", "ip": "100.64.0.1"},
              {"name": "vps", "ip": "100.64.0.2"}],
    "watch_service": "com.example.hubbot",
    "extra_act_words": ["portainer"],
}

CASES = [
    # (input, expect_escalation, why)
    ("hey, how's it going?",                       False, "small talk stays cheap"),
    ("what time is it",                            False, "trivia stays cheap"),
    ("thanks, that's perfect",                     False, "acknowledgement stays cheap"),
    ("fix the python script that keeps crashing",  True,  "code work escalates"),
    ("restart the bridge",                         True,  "action word escalates"),
    ("check on test-node",                         True,  "a node name from config escalates"),
    ("is portainer up?",                           True,  "extra_act_words escalates"),
    ("how's hubbot doing",                         True,  "the watched service name escalates"),
    ("reinicia el contenedor",                     True,  "spanish action word escalates"),
    ("text Leo and tell him I'm running late",     True,  "sending a message escalates"),
    ("x" * 300,                                    True,  "a long turn escalates"),
]


def main():
    b = load_bridge(CONFIG)
    fails = []
    for text, want_heavy, why in CASES:
        b._SESSION_STATE["heavy_turns"] = 0          # isolate from turn stickiness
        got = b.pick_model(text)
        want = b.MIDDLE_MODEL if want_heavy else b.FAST_MODEL
        if got != want:
            fails.append(f"{why}: {text[:40]!r} -> {got}, wanted {want}")

    # Stickiness: after escalating, a terse follow-up must NOT drop back mid-task.
    # This is the bug that made an assistant read a text message aloud instead of sending it.
    b._SESSION_STATE["heavy_turns"] = 0
    b.pick_model("ssh into vps and check the disk")
    if b.pick_model("yes do it") != b.MIDDLE_MODEL:
        fails.append("follow-up turn dropped back to the fast model mid-task")

    # A pinned model must beat routing entirely.
    os.environ["JARVIS_MODEL"] = "claude-opus-4-8"
    b2 = load_bridge(CONFIG)
    if b2.pick_model("hi") != "claude-opus-4-8":
        fails.append("JARVIS_MODEL pin did not override routing")
    os.environ.pop("JARVIS_MODEL", None)

    for f in fails:
        print(f"FAIL  {f}")
    print(f"\n{len(CASES) + 2 - len(fails)}/{len(CASES) + 2} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
