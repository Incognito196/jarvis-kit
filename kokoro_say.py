#!/usr/bin/env python3
"""Kokoro TTS helper: reads text from stdin, writes a wav to argv[1]. Voice via KOKORO_VOICE env."""
import os, sys, soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
k = Kokoro(os.path.join(HERE, "voices/kokoro-v1.0.onnx"),
           os.path.join(HERE, "voices/voices-v1.0.bin"))
text = sys.stdin.read().strip()
out = sys.argv[1]
voice = os.environ.get("KOKORO_VOICE", "am_michael")
samples, sr = k.create(text, voice=voice, speed=1.0, lang="en-us")
sf.write(out, samples, sr)
