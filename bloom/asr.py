"""Whisper round trip: transcribe a clip with whisper.cpp and score it against the text it should say.

Used by the voice benchmark and by `bloom voice check`. Needs `whisper-cli` (brew install whisper-cpp)
and the large-v3-turbo model (1.6 GB, downloaded once by ensure_model()).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from . import thainum

MODEL = Path.home() / ".cache/bloom/ggml-large-v3-turbo.bin"
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"


def available() -> bool:
    return bool(shutil.which("whisper-cli")) and MODEL.exists()


def ensure_model() -> None:
    if not shutil.which("whisper-cli"):
        raise RuntimeError("whisper-cli not found: brew install whisper-cpp")
    if not MODEL.exists():
        print(f"downloading {MODEL_URL} (1.6 GB, once)…")
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        part = MODEL.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URL, part)
        part.rename(MODEL)


def transcribe(wav: Path, language: str = "th") -> str:
    with tempfile.TemporaryDirectory() as d:
        w16 = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ar", "16000", "-ac", "1", str(w16)], check=True)
        r = subprocess.run(["whisper-cli", "-m", str(MODEL), "-l", language, "-nt", "-np", "-f", str(w16)],
                           check=True, capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


def normalize(text: str) -> str:
    """Compare what was said, not how it was typed: numbers spelled out, no spaces or punctuation."""
    return re.sub(r"[^฀-๿a-z]", "", thainum.spell(text).lower())


def cer(ref: str, hyp: str) -> float:
    """Character error rate of `hyp` against `ref` (edit distance / reference length)."""
    a, b = normalize(ref), normalize(hyp)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), 1)
