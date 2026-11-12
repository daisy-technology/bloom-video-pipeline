"""A video's whole state as data: video.toon (TOON, compact for the beat tables) or video.json.

    {"video": {title, size, look, motion, voice, music, ending, cam, pitch},
     "cast": [{id, kind, args}],
     "scenes": [{id, hold, mood, say, note, beats: [{on, do, what, args}]}],
     "music": {"cues": [{on, do}]}}

check() names the field that's wrong and the nearest valid value, so a spec is fixed by editing the
draft, never the generated page.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path

import toons

from .components import KINDS, VERBS, parse_args

LOOKS = ("iso-clean",)
MOTIONS = ("calm", "clean", "playful", "energetic")
MOODS = ("calm", "tense", "bright", "chip", "playful", "lofi")
CUES = ("drop", "lift", "duck", "stop")
ID = re.compile(r"^[a-z][\w.-]*$")


def load(project: Path) -> dict | None:
    for name, read in (("video.toon", toons.loads), ("video.json", json.loads)):
        f = project / name
        if f.exists():
            return read(f.read_text(encoding="utf-8"))
    return None


def save(project: Path, spec: dict) -> Path:
    f = project / "video.toon"
    f.write_text(toons.dumps(spec) + "\n", encoding="utf-8")
    return f


def digest(spec: dict) -> str:
    return hashlib.sha1(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def _near(word: str, options) -> str:
    m = difflib.get_close_matches(str(word), list(options), n=1)
    return f" (did you mean {m[0]!r}?)" if m else f" (one of: {', '.join(options)})"


def check(spec: dict) -> list[str]:
    """Problems as readable lines; empty when the spec can be composed."""
    errs = []
    v = spec.get("video") or {}
    if not re.fullmatch(r"\d+x\d+", str(v.get("size", ""))):
        errs.append(f"video.size: {v.get('size')!r} should be WxH, e.g. 1920x1080 or 1080x1920")
    if v.get("look", "iso-clean") not in LOOKS:
        errs.append(f"video.look: {v.get('look')!r}" + _near(v.get("look"), LOOKS))
    if v.get("motion", "calm") not in MOTIONS:
        errs.append(f"video.motion: {v.get('motion')!r}" + _near(v.get("motion"), MOTIONS))
    cast = {}
    for c in spec.get("cast") or []:
        where = f"cast {c.get('id')!r}"
        if not ID.match(str(c.get("id", ""))):
            errs.append(f"{where}: an id is lowercase letters, digits, . - _ and starts with a letter")
        if c.get("id") in cast:
            errs.append(f"{where}: used twice")
        k = KINDS.get(c.get("kind"))
        if not k:
            errs.append(f"{where}: kind {c.get('kind')!r}" + _near(c.get("kind"), KINDS))
            continue
        try:
            for a in parse_args(c.get("args", "")):
                if a not in k.args:
                    errs.append(f"{where}: {k.name} has no argument {a!r}" + _near(a, k.args))
        except ValueError as e:
            errs.append(f"{where}: {e}")
        cast[c["id"]] = k
    ids = set()
    for s in spec.get("scenes") or []:
        sid = s.get("id")
        if not ID.match(str(sid or "")) or sid in ids or sid in ("cast", "music"):
            errs.append(f"scene {sid!r}: needs a unique id (lowercase, starts with a letter; not cast or music)")
        ids.add(sid)
        if not str(s.get("say", "")).strip():
            errs.append(f"scene {sid}: no narration (say)")
        if s.get("mood") and s["mood"] not in MOODS:
            errs.append(f"scene {sid}: mood {s['mood']!r}" + _near(s["mood"], MOODS))
        for n, b in enumerate(s.get("beats") or [], 1):
            where, verb = f"scene {sid} beat {n} ({b.get('on')} {b.get('do')} {b.get('what')})", b.get("do")
            if verb not in VERBS:
                errs.append(f"{where}: do {verb!r}" + _near(verb, VERBS))
                continue
            what = str(b.get("what", "")).lstrip("#")
            if verb == "end":
                if what not in ("cut", "fade"):
                    errs.append(f"{where}: end is cut or fade")
            elif verb == "sfx":
                pass  # checked against the effects when the page is composed
            elif what not in cast:
                errs.append(f"{where}: no cast member {what!r}" + _near(what, cast))
            elif verb != "cam" and verb not in cast[what].verbs:
                errs.append(f"{where}: a {cast[what].name} can't {verb} (it can {', '.join(cast[what].verbs)})")
    if not spec.get("scenes"):
        errs.append("no scenes")
    for c in (spec.get("music") or {}).get("cues") or []:
        if c.get("do") not in CUES:
            errs.append(f"music cue {c.get('on')}: do {c.get('do')!r}" + _near(c.get("do"), CUES))
        if "@" not in str(c.get("on", "")) or str(c["on"]).split("@")[0] not in ids:
            errs.append(f"music cue {c.get('on')!r}: on is scene@moment, e.g. turn@ขาด or end@-2")
    return errs
