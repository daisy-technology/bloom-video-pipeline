"""Background music and sound effects, synthesized: every video gets audio nobody has to license.

Music follows the video. Each scene gets one chord, the chord changes on the cut, and the
progression and tempo come from the scene's mood (`## fix ~bright` in script.md; a mood
carries forward until the next one). Each mood stretch starts on its home chord and the last
scene resolves there.

Sound effects come from the page: an animated element with `data-sfx="pop"` pops when its
animation starts, `data-sfx="type"` clicks once per typed character, and the build adds a
whoosh on every scene change. `data-sfx` takes several effects, each with its own moment:
`data-sfx="riser hit@end"` builds over the animation and hits as it lands; `zip@.2` plays
0.2 s into it (see bloom/render.py).

The effects are one synthesized family, sized by role, as a sound designer would: the
structural ones (hit, sting, thud) are loud, the decorative ones (tick, blip, sparkle) far
quieter, so a film's biggest moment is also its loudest. The music bed makes room for them
(`automation`): it dips for a breath before a hit, ducks under a riser and a sting's tail.
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
# arpeggio octave shift, arpeggio notes per beat, drums. The styles after the first three dress the
# same skeleton differently: the lead's sound, a bass that pulses instead of holding, a snare on
# 2 and 4, swing, a darker tone, vinyl crackle, and their own balance of the parts.
STYLE = {
    "calm": dict(bpm=80, chords=[[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]],
                 roots=[48, 45, 41, 43], arp=12, per_beat=1, kick=False, hats=False),
    "tense": dict(bpm=92, chords=[[57, 60, 64], [57, 60, 65], [55, 60, 64], [55, 59, 62]],
                  roots=[45, 41, 48, 43], arp=12, per_beat=2, kick=True, hats=False),
    "bright": dict(bpm=104, chords=[[60, 64, 67], [59, 62, 67], [60, 64, 69], [60, 65, 69]],
                   roots=[48, 43, 45, 41], arp=24, per_beat=2, kick=True, hats=True),
    # 8-bit: fast square-wave arpeggios over a bouncing triangle bass, like a handheld game
    "chip": dict(bpm=132, chords=[[60, 64, 67], [59, 62, 67], [57, 60, 64], [57, 60, 65]],
                 roots=[48, 43, 45, 41], arp=12, per_beat=4, kick=True, hats=True, snare=True,
                 lead="square", bass="bounce", mix=dict(pad=0.0, bass=0.30, arp=0.16, kick=0.22, hats=0.05, snare=0.10)),
    # bouncy and cheerful: marimba on a swung beat, a staccato bass, hand claps
    "playful": dict(bpm=112, chords=[[60, 64, 67], [57, 60, 64], [57, 60, 65], [59, 62, 67]],
                    roots=[48, 45, 41, 43], arp=12, per_beat=2, kick=True, hats=True, snare=True, swing=0.16,
                    lead="marimba", bass="staccato", mix=dict(pad=0.12, bass=0.28, arp=0.22, kick=0.22, hats=0.04, snare=0.09)),
    # lo-fi: soft electric-piano sevenths, lazy swung drums, a darker tone and vinyl crackle
    "lofi": dict(bpm=78, chords=[[60, 64, 67, 71], [57, 60, 64, 67], [57, 60, 62, 65], [55, 59, 62, 65]],
                 roots=[48, 45, 38, 43], arp=12, per_beat=2, kick=True, hats=True, snare=True, swing=0.22,
                 lead="keys", tone=3200, crackle=True, mix=dict(pad=0.26, bass=0.24, arp=0.14, kick=0.24, hats=0.04, snare=0.08)),
}
MIX = dict(pad=0.30, bass=0.22, arp=0.12, kick=0.25, hats=0.05, snare=0.0)
assert set(STYLE) == set(MOODS)

SFX = ("tick", "pop", "swish", "whoosh", "thud", "chime", "buzz",
       "hit", "riser", "sting", "sparkle", "boing", "zip", "drop", "blip", "type")
# peak level of each effect against a voice near -18 LUFS: structural hits loud, decoration quiet,
# and a riser under the hit it leads to (the drop is louder than the build)
LEVEL_DB = {"tick": -22, "pop": -17, "swish": -20, "whoosh": -21, "thud": -13, "chime": -17, "buzz": -19, "click": -27,
            "hit": -11, "riser": -21, "sting": -14, "sparkle": -21, "boing": -18, "zip": -21, "drop": -20, "blip": -24}
STRETCH = ("riser",)  # effects made to the length of their animation: a riser ends exactly as it lands
# not sounds but how the video ends: the music stops with the picture, at once on a cut to black,
# over its animation on a fade, and stays silent after (the strongest beat is the silence after a hook)
ENDINGS = ("cut", "fade")
RISER_DUR = 1.0       # a riser on an element with no animation length
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


def _lead(kind: str, midi: int, vel: float, step: float) -> np.ndarray:
    """One note of a style's lead: pluck (the original), square (8-bit), marimba, keys (electric piano)."""
    if kind == "pluck":
        return _pluck(midi, vel)
    f = hz(midi)
    if kind == "square":  # a 25% pulse, held just under its step so fast runs stay distinct
        t = _t(int(max(0.05, step * 0.85) * SR))
        x = np.where((f * t) % 1 < 0.25, 1.0, -0.33) * np.exp(-t / 0.25)
        return vel * 0.6 * x * np.minimum(1, t / 0.002) * np.clip((len(t) / SR - t) / 0.005, 0, 1)
    if kind == "marimba":  # a wooden bar: the fourth partial rings briefly over the fundamental
        t = _t(int(0.5 * SR))
        x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.18) + 0.5 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / 0.03)
        return vel * x * np.minimum(1, t / 0.002)
    if kind == "keys":  # a soft electric piano with a slow tremolo
        t = _t(int(0.9 * SR))
        x = (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.2)) * np.exp(-t / 0.45)
        return vel * x * (1 + 0.15 * np.sin(2 * np.pi * 5 * t)) * np.minimum(1, t / 0.006)
    raise ValueError(f"unknown lead {kind!r}")


def _bass_note(kind: str, midi: int, dur: float) -> np.ndarray:
    """A short bass note: a triangle for 8-bit, a round sine otherwise."""
    t = _t(int(dur * SR))
    f = hz(midi)
    x = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t)) if kind == "bounce" else \
        np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
    return x * np.minimum(1, t / 0.004) * np.clip((dur - t) / 0.02, 0, 1)


def _snare(rng: np.random.Generator, kind: str) -> np.ndarray:
    """A snare or clap: noise with a short body; an 8-bit one is bare noise."""
    t = _t(int(0.18 * SR))
    noise = rng.standard_normal(len(t))
    if kind == "square":
        return noise * np.exp(-t / 0.04) * 0.6
    if kind == "marimba":  # a clap: three quick bursts, then the tail
        gate = sum(np.exp(-np.clip(t - d, 0, None) / 0.006) * (t >= d) for d in (0.0, 0.012, 0.024))
        return np.diff(noise, prepend=0) * (gate + np.exp(-t / 0.05)) * 0.35
    return np.diff(noise, prepend=0) * np.exp(-t / 0.06) * 0.5 + np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.03) * 0.5


def _darken(x: np.ndarray, cutoff: float) -> np.ndarray:
    """A gentle low-pass (first order), for an older, softer tone."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / cutoff) ** 2), len(x))


def _crackle(n: int, seed: int) -> np.ndarray:
    """Vinyl: sparse clicks of random size over a faint hiss."""
    rng = np.random.default_rng(seed)
    y = rng.standard_normal(n) * 0.002
    for at in rng.integers(0, n, n // SR * 9):
        k = np.arange(min(40, n - at))
        y[at:at + len(k)] += rng.uniform(0.02, 0.08) * rng.choice([-1, 1]) * np.exp(-k / 6)
    return y


def music(timeline: list[dict], total: float, seed: int = 7) -> np.ndarray:
    """timeline = [{"start", "dur", "mood"}]; returns mono float samples, `total` seconds long."""
    rng = np.random.default_rng(seed)
    n_total = int(total * SR) + 1
    y = {k: np.zeros(n_total + 3 * SR) for k in ("pad", "bass", "arp", "kick", "hats", "snare")}

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
        if st.get("bass", "drone") != "drone":
            continue  # this style plays its bass on the beat (below)
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
        lead, bass = st.get("lead", "pluck"), st.get("bass", "drone")
        while start + k * step < end:
            t = start + k * step
            at = next((s0, m, i) for s0, s1, m, i in scenes if s0 <= t < s1 or s1 >= end)
            chord, root = STYLE[at[1]]["chords"][at[2] % 4], STYLE[at[1]]["roots"][at[2] % 4]
            note = chord[k % len(chord)] + st["arp"]
            on_beat = k % st["per_beat"] == 0
            n_beat = k // st["per_beat"]
            if not on_beat and st.get("swing"):  # the off-beats lean late
                t += st["swing"] * step
            _add(y["arp"], _lead(lead, note, rng.uniform(0.75, 1.0) * (1.0 if on_beat else 0.7), step), t)
            if st["kick"] and on_beat and n_beat % 2 == 0:
                _add(y["kick"], _kick(), t)
            if st["hats"] and not on_beat:
                _add(y["hats"], _hat(rng), t)
            if st.get("snare") and on_beat and n_beat % 2 == 1:
                _add(y["snare"], _snare(rng, lead), t)
            if bass == "bounce" and k % max(1, st["per_beat"] // 2) == 0:  # root, octave, root, octave: eighths
                _add(y["bass"], _bass_note(bass, root + 12 * ((k // max(1, st["per_beat"] // 2)) % 2), step * 1.6), t)
            elif bass == "staccato" and on_beat:  # root on the beat, the fifth on beat 4
                _add(y["bass"], _bass_note(bass, root + (7 if n_beat % 4 == 3 else 0), beat * 0.45), t)
            k += 1

    w = {**MIX, **STYLE[stretches[0][2]].get("mix", {})} if len(stretches) == 1 else MIX
    mix = sum(w[part] * y[part] for part in w)[:n_total]
    tone = [STYLE[m].get("tone") for _, _, m in stretches]
    if tone[0] and len(set(tone)) == 1:
        mix = _darken(mix, tone[0])
    if all(STYLE[m].get("crackle") for _, _, m in stretches):
        mix += _crackle(len(mix), seed) * (np.sqrt(np.mean(mix ** 2)) / 0.05)
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


def _sweep(f: np.ndarray) -> np.ndarray:
    """The phase of a tone whose frequency follows `f` (Hz per sample)."""
    return 2 * np.pi * np.cumsum(f) / SR


def _bell(f: float, t: np.ndarray, decay: float) -> np.ndarray:
    """A small struck bell: the fundamental and an inharmonic partial that dies first."""
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / (decay / 3))) \
        * np.exp(-t / decay) * np.minimum(1, t / 0.002)


def sfx(name: str, dur: float | None = None) -> np.ndarray:
    """One effect, peak 1.0. Deterministic: the same name (and length) always sounds the same.
    `dur` sizes the effects in STRETCH (a riser); the others have their own length."""
    if name in STRETCH:
        return _sfx(name, round(max(0.2, dur or RISER_DUR), 3))
    return _sfx(name, None)


@functools.cache
def _sfx(name: str, dur: float | None) -> np.ndarray:
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
    elif name == "hit":  # the designed impact: a crack for the attack, a knock and a falling body, a short air tail
        t = _t(int(0.9 * SR))
        n = lambda a: a / (np.abs(a).max() or 1)  # noqa: E731
        body = np.tanh(1.8 * np.sin(_sweep(48 + 110 * np.exp(-t / 0.045))) * np.exp(-t / 0.22))  # tanh: overtones a phone can play
        knock = np.sin(_sweep(320 + 260 * np.exp(-t / 0.02))) * np.exp(-t / 0.05)  # the weight, where a phone speaker reaches
        crack = _bandpass(rng.standard_normal(len(t)), np.full(len(t), 2400.0), q=1.2) * np.exp(-t / 0.012)
        punch = np.convolve(rng.standard_normal(len(t)) * np.exp(-t / 0.03), np.ones(24) / 24, mode="same")
        tail = _bandpass(rng.standard_normal(len(t)), 900 + 1500 * np.exp(-t / 0.2), q=0.8) * np.exp(-t / 0.18)
        # lows about 6 dB over the mids: more and the hit is only a rumble on a phone (lows within ~8 dB of mids)
        x = 0.55 * body + 0.7 * knock + 1.1 * n(crack) + 0.9 * n(punch) + 0.25 * n(tail)
        x *= np.minimum(1, t / 0.0008)
    elif name == "riser":  # air and a tone climbing together, loudest at the very end, then cut on the beat
        t = _t(int(dur * SR))
        u = t / dur
        air = _bandpass(rng.standard_normal(len(t)), 300 * 20 ** u, q=1.6)
        tone = sum(np.sin(_sweep(f * 4 ** u)) / k for k, f in ((1, 220.0), (2, 330.0), (3, 440.0)))  # up two octaves
        flutter = 1 + 0.35 * np.sin(_sweep(4 + 18 * u ** 2))  # the tremolo speeds up into the hit
        x = (air / (np.abs(air).max() or 1) + 0.2 * tone * flutter) * u ** 2.2
        x[-int(0.006 * SR):] *= np.linspace(1, 0, int(0.006 * SR))
    elif name == "sting":  # the signature: a bright chord stab over a soft hit, ringing out
        t = _t(int(1.8 * SR))
        x = np.zeros(len(t))
        for m in (72, 76, 79, 86, 91):  # C major add 9, open voicing
            f = hz(m)
            x += sum(np.sin(2 * np.pi * k * f * t) / k ** 1.4 for k in range(1, 6)) * np.exp(-t / 0.55)
        hit = _sfx("hit", None)
        x = x / (np.abs(x).max() or 1) * np.minimum(1, t / 0.004)
        x[: len(hit)] += 0.45 * hit[: len(t)]
    elif name == "sparkle":  # a quick rising run of small bells: something revealed, or magic
        t = _t(int(1.4 * SR))
        x = np.zeros(len(t))
        for k, m in enumerate((88, 92, 95, 100, 104, 107)):  # E major, climbing two octaves
            at = 0.045 * k
            tt = np.clip(t - at, 0, None)
            x += np.where(t >= at, _bell(hz(m), tt, 0.35) * (0.7 + 0.06 * k), 0)
    elif name == "boing":  # a spring: a tone wobbling around its pitch as it settles (squash and stretch)
        t = _t(int(0.55 * SR))
        f = 190 * (1 + 0.55 * np.exp(-t / 0.16) * np.sin(2 * np.pi * 13 * t)) * (1 + 0.25 * t)
        x = (np.sin(_sweep(f)) + 0.3 * np.sin(2 * _sweep(f))) * np.exp(-t / 0.2) * np.minimum(1, t / 0.003)
    elif name == "zip":  # an upward zip: stretch, rise, a jump taking off
        t = _t(int(0.24 * SR))
        u = t / 0.24
        ph = _sweep(380 * 6.5 ** u)
        x = np.tanh(3 * np.sin(ph)) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 70 * t))) * np.sin(np.pi * u) ** 0.6
    elif name == "drop":  # a falling slide: falls, weight, exits
        t = _t(int(0.45 * SR))
        u = t / 0.45
        x = (np.sin(_sweep(1500 * 0.2 ** u)) + 0.2 * np.sin(2 * _sweep(1500 * 0.2 ** u))) \
            * np.minimum(1, t / 0.004) * (1 - u) ** 0.7
    elif name == "blip":  # items or letters arriving: short and high
        t = _t(int(0.07 * SR))
        x = np.tanh(2.5 * np.sin(2 * np.pi * 1760 * t)) * np.exp(-t / 0.018) * np.minimum(1, t / 0.001)
    else:
        raise ValueError(f"unknown sound effect {name!r}, expected one of {SFX}")
    return x / (np.max(np.abs(x)) or 1.0)


def place(events: list[dict], total: float, seed: int = 3) -> np.ndarray:
    """events = [{"t", "sfx", "dur", "steps"}] -> mono float samples, `total` seconds long."""
    y = np.zeros(int(total * SR) + 1)
    rng = np.random.default_rng(seed)
    for e in events:
        if e["sfx"] in ENDINGS:  # the music's job (gain_curve), not a sound
            continue
        if e["sfx"] == "type":  # a click per typed character, slightly uneven like real keys
            steps = max(int(e.get("steps") or 0), 1)
            every = (e.get("dur") or 0.03 * steps) / steps
            for k in range(steps):
                gain = 10 ** (LEVEL_DB["click"] / 20) * rng.uniform(0.55, 1.0)
                _add(y, sfx("click") * gain, e["t"] + k * every + rng.uniform(-0.004, 0.004))
        else:
            if e["sfx"] not in LEVEL_DB:
                raise ValueError(f"unknown sound effect {e['sfx']!r}, expected one of {SFX}")
            _add(y, sfx(e["sfx"], e.get("dur")) * 10 ** (LEVEL_DB[e["sfx"]] / 20) * e.get("gain", 1.0), e["t"])
    return np.clip(y, -0.98, 0.98)


# how the music bed makes room for an effect: (seconds before it, seconds after it or "dur", gain)
ROOM = {
    "hit":     (0.30, 0.55, 0.45),   # a breath before the impact, and the bed stays low under its tail
    "thud":    (0.20, 0.35, 0.65),
    "sting":   (0.25, 1.40, 0.40),
    "riser":   (0.00, "dur", 0.55),  # duck under the build itself; the hit after it takes over
    "sparkle": (0.15, 0.80, 0.65),
    "chime":   (0.15, 0.80, 0.70),
    "whoosh":  (0.25, 0.25, 0.85),   # a hold before the cut
}
RAMP = 0.06  # seconds to dip and recover: fast enough to land with the effect, slow enough not to click


def automation(events: list[dict]) -> list[tuple[float, float, float]]:
    """The bed's moves for these effects: [(t0, t1, gain)], the bed at `gain` between t0 and t1."""
    out = []
    for e in events:
        if e.get("sfx") not in ROOM:
            continue
        before, after, gain = ROOM[e["sfx"]]
        after = (e.get("dur") or RISER_DUR) if after == "dur" else after
        out.append((max(0.0, e["t"] - before), e["t"] + after, gain))
    return out


# how loud a music file sits for each scene mood: the music follows the story's energy (a file can't change
# its arrangement, but its level can); bright is full, calm sits back under the narration
FOLLOW = {"calm": 0.7, "lofi": 0.75, "tense": 0.85, "playful": 0.9, "chip": 0.9, "bright": 1.0}
CUE_LEVEL = {"drop": 0.15, "duck": 0.5, "lift": 1.0, "stop": 0.0}
LAST_SCENE = 0.6  # under the closing question


def follow(timeline: list[dict], cues: list[tuple[float, str]] = (), by_mood: bool = True) -> list[tuple[float, float, float]]:
    """The music's level scene by scene, as gain moves for gain_curve: [(t0, t1, gain)].
    by_mood (a music file): each scene at its mood's level, the last scene lower under the closing question.
    cues [(t, drop|duck|lift|stop)]: from t to the end of that scene (stop: to the end of the video)."""
    out, mood = [], None
    end = timeline[-1]["start"] + timeline[-1]["dur"] if timeline else 0.0
    for k, s in enumerate(timeline):
        mood = s.get("mood") or mood
        t0, t1 = s["start"], s["start"] + s["dur"]
        level = FOLLOW.get(mood, 1.0) if by_mood else 1.0
        if by_mood and k == len(timeline) - 1 and len(timeline) > 1:
            level = min(level, LAST_SCENE)
        here = sorted((t, c) for t, c in cues if t0 <= t < t1)
        marks = [t0] + [t for t, _ in here] + [t1]
        levels = [level] + [CUE_LEVEL[c] for _, c in here]
        for a, b, g in zip(marks, marks[1:], levels):
            if g < 1.0 and b > a:
                out.append((a, b, g))
    for t, c in cues:
        if c == "stop":
            out.append((t, end, 0.0))
    return out


def ending(events: list[dict]) -> tuple[float, float] | None:
    """The page's first cut or fade as (when the music starts to go, seconds it takes), or None."""
    ends = [(e["t"], RAMP if e["sfx"] == "cut" else max(e.get("dur") or 0.0, RAMP)) for e in events if e["sfx"] in ENDINGS]
    return min(ends) if ends else None


def gain_curve(autos: list[tuple[float, float, float]], total: float, end: tuple[float, float] | None = None) -> np.ndarray:
    """A gain per sample, 1.0 where the bed plays as it is; overlapping moves keep the lowest gain.
    `end` (from `ending`) takes the bed down to silence from that moment and keeps it there."""
    g = np.ones(int(total * SR) + 1)
    r = int(RAMP * SR)
    for t0, t1, gain in autos:
        i, j = int(t0 * SR), int(t1 * SR)
        if j <= 0 or i >= len(g):
            continue
        shape = np.full(j - i + 2 * r, gain)
        shape[:r] = np.linspace(1, gain, r)
        shape[-r:] = np.linspace(gain, 1, r)
        a, b = i - r, j + r
        lo, hi = max(a, 0), min(b, len(g))
        g[lo:hi] = np.minimum(g[lo:hi], shape[lo - a: hi - a])
    if end and int(end[0] * SR) < len(g):
        i = max(0, int(end[0] * SR))
        ramp = np.linspace(1, 0, max(1, int(end[1] * SR)))[: len(g) - i]
        g[i:i + len(ramp)] *= ramp
        g[i + len(ramp):] = 0
    return g


def write_wav(path: Path, x: np.ndarray) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path
