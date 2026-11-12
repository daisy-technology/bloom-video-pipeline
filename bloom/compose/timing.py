"""When each phrase and word is spoken, from the voice clips a build made, and moments written against them.

A beat in a spec says when it happens in words, not seconds (`on: ขาด`), so a new voice or a reworded
line never needs re-timing: the moment is found again in whatever the voice now says.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import lexicon, script, subs, thainum, voice

PAD_IN, PAD_OUT = 0.35, 0.55  # bloom.__main__'s pads: the voice starts 0.35 s into a scene


def timing(project: Path, spec: str | None, fps: int = 30) -> list[dict]:
    """Per scene: {"id", "dur", "speak", "text", "phrases": [(start, end, text)]} in seconds from the scene
    start, or {"id", "missing": True} when its clip hasn't been made with this voice yet."""
    pairs = lexicon.load(project / "lexicon.tsv")
    cache = project / ".bloom" / "voice"
    out = []
    for s in script.parse(project / "script.md"):
        clip = voice._clip(lexicon.apply(s["speech"], pairs), cache, spec, None)[3]
        if not clip.exists():  # a clip made before a lexicon entry changed this line still times it
            clip = voice._clip(s["speech"], cache, spec, None)[3]
        if not clip.exists():
            out.append({"id": s["id"], "missing": True})
            continue
        speak = voice.duration(clip)
        dur = round((PAD_IN + speak + PAD_OUT + s["hold"]) * fps) / fps
        phrases = subs.phrases(s["text"])
        said = [_said(p) for p in phrases]  # "1859" takes as long as its words
        total, t, spans = sum(said) or 1, PAD_IN, []
        for p, n in zip(phrases, said):
            d = speak * n / total
            spans.append((t, t + d, p))
            t += d
        out.append({"id": s["id"], "dur": dur, "speak": speak, "text": s["text"], "phrases": spans})
    return out


def _said(text: str) -> int:
    return len(thainum.spell(text).replace(" ", ""))


WHEN = re.compile(r"^(?P<word>.*?)(?:#(?P<nth>\d+))?(?P<off>[+-]\d+(?:\.\d+)?)?$")


def moment(on: str, scene: dict) -> float:
    """Seconds from the scene start for an `on` value: 2.4 · 60% · -1.5 (before the end) · start · end ·
    a word or phrase of the narration, optionally #2 (its second time) and +0.3 / -0.2 (seconds after/before)."""
    on = str(on).strip()
    dur = scene["dur"]
    if on in ("", "start"):
        return 0.0
    if on == "end":
        return dur
    if re.fullmatch(r"-?\d+(?:\.\d+)?", on):
        v = float(on)
        return min(max(dur + v if on.startswith("-") else v, 0.0), dur)
    if on.endswith("%") and re.fullmatch(r"\d+(?:\.\d+)?%", on):
        return float(on[:-1]) / 100 * dur
    m = WHEN.match(on)
    word, nth, off = m.group("word").strip(), int(m.group("nth") or 1), float(m.group("off") or 0)
    seen = 0
    for start, end, phrase in scene["phrases"]:
        i = phrase.find(word)
        while i >= 0:
            seen += 1
            if seen == nth:  # inside the phrase, in proportion to how long its words take to say
                at = start + (end - start) * _said(phrase[:i]) / max(_said(phrase), 1)
                return min(max(at + off, 0.0), dur)
            i = phrase.find(word, i + 1)
    raise ValueError(f'scene {scene["id"]}: "{word}" is not in its narration ({scene["text"]})')
