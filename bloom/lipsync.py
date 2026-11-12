"""The voice, read as a mouth: one mouth shape per video frame, from the clips on the timeline.

A character whose mouth flaps on a loop talks through every pause and keeps talking after the
line ends. This reads the voice instead: per frame, how loud it is against the voice's own
speaking level, sorted into closed / half / open. The renderer hands each frame's shape to the
page as `<html data-mouth>` and the level as `--voice` (see bloom/render.py).

Two touches make it read as speech rather than a level meter: a long open vowel closes to half
for a frame now and then, as a real jaw moves through a held sound, and a single closed frame
between two open ones becomes half, so the mouth never flickers shut mid-word.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

SR = 48_000
OPEN_DB = 8.0    # within this many dB of the voice's speaking level: open
HALF_DB = 22.0   # within this: half open; quieter is closed (breaths, room tone)
HELD = 4         # an open mouth held this many frames closes to half on the next one
RELEASE = 0.8    # --voice falls by this much a frame at most


def _samples(wav: Path) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32)


def levels(clips: list[tuple[Path, float]], total: float, fps: int = 30) -> np.ndarray:
    """dB of the voice per video frame (clips = [(wav, start_seconds)]), -120 where nothing speaks."""
    y = np.zeros(int(total * SR) + SR)
    for wav, start in clips:
        x = _samples(wav)
        i = int(round(start * SR))
        j = min(len(y), i + len(x))
        y[i:j] += x[: j - i]
    n = int(round(total * fps))
    hop = SR / fps
    out = np.full(n, -120.0)
    for k in range(n):
        seg = y[int(k * hop): int((k + 1) * hop)]
        if len(seg):
            out[k] = 10 * np.log10(float(np.mean(seg ** 2)) + 1e-12)
    return out


def shapes(db: np.ndarray) -> list[tuple[int, float]]:
    """[(state, level)] per frame: state 0 closed, 1 half, 2 open; level 0..1 for scale or glow."""
    speech = db[db > -60]
    if not len(speech):
        return [(0, 0.0)] * len(db)
    ref = float(np.percentile(speech, 90))  # the voice's speaking level, whatever its loudness
    state = np.where(db > ref - OPEN_DB, 2, np.where(db > ref - HALF_DB, 1, 0))
    run = 0
    for k in range(len(state)):  # a jaw moves through a held vowel
        run = run + 1 if state[k] == 2 else 0
        if run > HELD:
            state[k], run = 1, 0
    for k in range(1, len(state) - 1):  # no one-frame blink of a shut mouth inside a word
        if state[k] == 0 and state[k - 1] and state[k + 1]:
            state[k] = 1
    level = np.clip((db - (ref - 30)) / 30, 0, 1)
    for k in range(1, len(level)):  # rises at once, falls away gently: a swell, not a jitter
        level[k] = max(level[k], level[k - 1] * RELEASE)
    return [(int(s), round(float(v), 3)) for s, v in zip(state, level)]


def track(clips: list[tuple[Path, float]], total: float, fps: int = 30) -> list[tuple[int, float]]:
    return shapes(levels(clips, total, fps))
