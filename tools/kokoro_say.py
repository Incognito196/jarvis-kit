#!/usr/bin/env python3
"""Kokoro TTS helper: reads text on stdin, writes a wav to argv[1].

Only used when JARVIS_VOICE=kokoro. Needs two things the repo does not ship:
    pip install kokoro-onnx soundfile
    voices/kokoro-v1.0.onnx and voices/voices-v1.0.bin   (~350 MB, from the Kokoro release)
Voice name via KOKORO_VOICE (default am_michael).
"""
import os, sys

try:
    import soundfile as sf
    from kokoro_onnx import Kokoro
except ImportError:
    sys.exit("kokoro voice needs: pip install kokoro-onnx soundfile")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model = os.environ.get("KOKORO_MODEL", os.path.join(ROOT, "voices", "kokoro-v1.0.onnx"))
voices = os.path.join(os.path.dirname(model), "voices-v1.0.bin")
if not (os.path.exists(model) and os.path.exists(voices)):
    sys.exit(f"missing kokoro model files under {os.path.dirname(model)}")

k = Kokoro(model, voices)
samples, sr = k.create(sys.stdin.read().strip(), voice=os.environ.get("KOKORO_VOICE", "am_michael"),
                       speed=1.0, lang="en-us")
sf.write(sys.argv[1], samples, sr)
