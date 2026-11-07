"""Background music and sound effects, synthesized: every video gets audio nobody has to license.

Music follows the video. Each scene gets one chord, the chord changes on the cut, and the
progression and tempo come from the scene's mood (`## fix ~bright` in script.md; a mood
carries forward until the next one). Each mood stretch starts on its home chord and the last
scene resolves there.

Sound effects come from the page: an animated element with `data-sfx="pop"` pops when its
animation starts, `data-sfx="type"` clicks once per typed character, and the build adds a
whoosh on every scene change.
"""
from __future__ import annotations

import functools
import math
import wave
import zlib
from pathlib import Path

import numpy as np

from .script import MOODS

SR = 48_000

# tempo, pad chords and bass roots as MIDI notes (A minor / C major, so moods change key smoothly),
# arpeggio octave shift, arpeggio notes per beat, drums
STYLE = {
    "calm": dict(bpm=80, chords=[[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]],
                 roots=[48, 45, 41, 43], arp=12, per_beat=1, kick=False, hats=False),
    "tense": dict(bpm=92, chords=[[57, 60, 64], [57, 60, 65], [55, 60, 64], [55, 59, 62]],
                  roots=[45, 41, 48, 43], arp=12, per_beat=2, kick=True, hats=False),
    "bright": dict(bpm=104, chords=[[60, 64, 67], [59, 62, 67], [60, 64, 69], [60, 65, 69]],
                   roots=[48, 43, 45, 41], arp=24, per_beat=2, kick=True, hats=True),
}
assert set(STYLE) == set(MOODS)

SFX = ("tick", "pop", "swish", "whoosh", "thud", "chime", "buzz", "type")
LEVEL_DB = {"tick": -22, "pop": -17, "swish": -20, "whoosh": -21, "thud": -13, "chime": -17, "buzz": -19, "click": -27}
MUSIC_RMS_DB = -26  # before ducking; the voice sits near -16 LUFS


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _add(y: np.ndarray, x: np.ndarray, at: float) -> None:
    i = int(round(at * SR))
    if i < 0:
        x, i = x[-i:], 0
    j = min(len(y), i + len(x))
    if j > i:
        y[i:j] += x[: j - i]


# ---- music -------------------------------------------------------------------------------

def _pad(notes: list[int], n: int, rng: np.random.Generator) -> np.ndarray:
    t, out = _t(n), np.zeros(n)
    for m in notes:
        for detune in (-0.0012, 0.0012):  # two slightly detuned voices per note: a soft chorus
            ph = rng.uniform(0, 2 * np.pi)
            for k, amp in ((1, 1.0), (2, 0.35), (3, 0.15), (4, 0.07)):
                out += amp * np.sin(2 * np.pi * hz(m) * (1 + detune) * k * t + ph * k)
    return out * (1 + 0.08 * np.sin(2 * np.pi * 0.25 * t)) / len(notes)


def _envelope(n: int, attack: float, release: float) -> np.ndarray:
    t = _t(n)
    return np.minimum(1, t / attack) * np.clip((n / SR - t) / release, 0, 1)


def _pluck(midi: int, vel: float) -> np.ndarray:
    t = _t(int(0.4 * SR))
    f = hz(midi)
    return vel * (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.14) * np.minimum(1, t / 0.004)


def _kick() -> np.ndarray:
    t = _t(int(0.3 * SR))
    f = 45 + 75 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.11)


def _hat(rng: np.random.Generator) -> np.ndarray:
    n = int(0.06 * SR)
    return np.diff(rng.standard_normal(n + 1)) * np.exp(-_t(n) / 0.012) * 0.5


def music(timeline: list[dict], total: float, seed: int = 7) -> np.ndarray:
    """timeline = [{"start", "dur", "mood"}]; returns mono float samples, `total` seconds long."""
    rng = np.random.default_rng(seed)
    n_total = int(total * SR) + 1
    y = {k: np.zeros(n_total + 3 * SR) for k in ("pad", "bass", "arp", "kick", "hats")}

    # moods carry forward; each mood stretch restarts its progression on the home chord
    mood, scenes, idx = "calm", [], 0
    for i, s in enumerate(timeline):
        if s.get("mood") and s["mood"] != mood:
            mood, idx = s["mood"], 0
        elif i:
            idx += 1
        scenes.append((s["start"], s["start"] + s["dur"], mood, idx))
    last = scenes[-1]
    scenes[-1] = (last[0], last[1], last[2], 0)  # the ending resolves home

    for start, end, mood, idx in scenes:
        st = STYLE[mood]
        chord, root = st["chords"][idx % 4], st["roots"][idx % 4]
        n = int((end - start + 1.0) * SR)  # +1 s release overlaps the next chord
        _add(y["pad"], _pad(chord, n, rng) * _envelope(n, 0.5, 1.0), start)
        tb = _t(n)
        bass = (np.sin(2 * np.pi * hz(root) * tb) + 0.25 * np.sin(4 * np.pi * hz(root) * tb)) * _envelope(n, 0.15, 1.0)
        _add(y["bass"], bass, start)

    # rhythm: one beat grid per mood stretch, so the pulse never stutters at a cut inside it
    stretches: list[list] = []
    for start, end, mood, idx in scenes:
        if stretches and stretches[-1][2] == mood:
            stretches[-1][1] = end
        else:
            stretches.append([start, end, mood])
    for start, end, mood in stretches:
        st = STYLE[mood]
        beat = 60 / st["bpm"]
        step = beat / st["per_beat"]
        k = 0
        while start + k * step < end:
            t = start + k * step
            chord = next(STYLE[m]["chords"][i % 4] for s0, s1, m, i in scenes if s0 <= t < s1 or s1 >= end)
            note = chord[k % len(chord)] + st["arp"]
            on_beat = k % st["per_beat"] == 0
            _add(y["arp"], _pluck(note, rng.uniform(0.75, 1.0) * (1.0 if on_beat else 0.7)), t)
            if st["kick"] and on_beat and (k // st["per_beat"]) % 2 == 0:
                _add(y["kick"], _kick(), t)
            if st["hats"] and not on_beat:
                _add(y["hats"], _hat(rng), t)
            k += 1

    mix = (0.30 * y["pad"] + 0.22 * y["bass"] + 0.12 * y["arp"] + 0.25 * y["kick"] + 0.05 * y["hats"])[:n_total]
    fade_in, fade_out = int(1.0 * SR), int(2.0 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)
    rms = math.sqrt(float(np.mean(mix ** 2))) or 1.0
    mix *= 10 ** (MUSIC_RMS_DB / 20) / rms
    return np.clip(mix, -0.98, 0.98)


# ---- sound effects -----------------------------------------------------------------------

def _bandpass(x: np.ndarray, fc: np.ndarray, q: float = 2.5) -> np.ndarray:
    """Chamberlin state-variable band-pass with a moving centre frequency."""
    y = np.empty_like(x)
    low = band = 0.0
    for i in range(len(x)):
        f = 2 * math.sin(math.pi * fc[i] / SR)
        high = x[i] - low - band / q
        band += f * high
        low += f * band
        y[i] = band
    return y


@functools.cache
def sfx(name: str) -> np.ndarray:
    """One effect, peak 1.0. Deterministic: the same name always sounds the same."""
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    if name == "tick":
        t = _t(int(0.03 * SR))
        x = np.sin(2 * np.pi * 2600 * t) * np.exp(-t / 0.006) + 0.15 * rng.standard_normal(len(t)) * np.exp(-t / 0.002)
    elif name == "pop":
        t = _t(int(0.12 * SR))
        ph = 2 * np.pi * np.cumsum(420 + 680 * np.exp(-t / 0.02)) / SR
        x = (np.sin(ph) + 0.2 * np.sin(2 * ph)) * np.minimum(1, t / 0.002) * np.exp(-t / 0.035)
    elif name in ("swish", "whoosh"):
        dur, lo, peak, end = (0.32, 600, 3200, 1400) if name == "swish" else (0.6, 350, 2600, 700)
        t = _t(int(dur * SR))
        u = t / dur
        fc = np.where(u < 0.55, lo + (peak - lo) * (u / 0.55) ** 2, peak + (end - peak) * ((u - 0.55) / 0.45))
        x = _bandpass(rng.standard_normal(len(t)), fc) * np.sin(np.pi * u ** 0.85) ** 2
    elif name == "thud":
        t = _t(int(0.45 * SR))
        body = np.sin(2 * np.pi * np.cumsum(40 + 60 * np.exp(-t / 0.05)) / SR) * np.exp(-t / 0.14)
        slap = np.convolve(rng.standard_normal(len(t)) * np.exp(-t / 0.004), np.ones(8) / 8, mode="same")
        x = body + 0.35 * slap
    elif name == "chime":
        t = _t(int(1.3 * SR))
        x = np.zeros(len(t))
        for f, at in ((1318.5, 0.0), (1975.5, 0.09)):  # E6 then B6
            tt = np.clip(t - at, 0, None)
            bell = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt / 0.15))
            x += np.where(t >= at, bell * np.exp(-tt / 0.45) * np.minimum(1, tt / 0.003), 0)
    elif name == "buzz":
        t = _t(int(0.32 * SR))
        x = np.zeros(len(t))
        for f, a, b in ((233.1, 0.0, 0.11), (196.0, 0.15, 0.29)):  # two falling square-ish tones
            gate = ((t >= a) & (t < b)).astype(float)
            tone = sum(np.sin(2 * np.pi * k * f * t) / k for k in (1, 3, 5, 7, 9))
            x += tone * gate * np.minimum(1, (t - a).clip(0) / 0.005) * np.minimum(1, (b - t).clip(0) / 0.02)
        x = np.convolve(x, np.ones(6) / 6, mode="same")
    elif name == "click":  # one keystroke of a "type" effect
        t = _t(int(0.018 * SR))
        x = np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t / 0.0018) + 0.3 * np.sin(2 * np.pi * 3200 * t) * np.exp(-t / 0.003)
    else:
        raise ValueError(f"unknown sound effect {name!r}, expected one of {SFX}")
    return x / (np.max(np.abs(x)) or 1.0)


def place(events: list[dict], total: float, seed: int = 3) -> np.ndarray:
    """events = [{"t", "sfx", "dur", "steps"}] -> mono float samples, `total` seconds long."""
    y = np.zeros(int(total * SR) + 1)
    rng = np.random.default_rng(seed)
    for e in events:
        if e["sfx"] == "type":  # a click per typed character, slightly uneven like real keys
            steps = max(int(e.get("steps") or 0), 1)
            every = (e.get("dur") or 0.03 * steps) / steps
            for k in range(steps):
                gain = 10 ** (LEVEL_DB["click"] / 20) * rng.uniform(0.55, 1.0)
                _add(y, sfx("click") * gain, e["t"] + k * every + rng.uniform(-0.004, 0.004))
        else:
            _add(y, sfx(e["sfx"]) * 10 ** (LEVEL_DB[e["sfx"]] / 20), e["t"])
    return np.clip(y, -0.98, 0.98)


def write_wav(path: Path, x: np.ndarray) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path
