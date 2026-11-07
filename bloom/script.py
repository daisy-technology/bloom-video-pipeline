"""Read a voiceover script: one `## <scene-id>` heading per scene, text below it.

`{shown|spoken}` splits what the caption shows from what the voice says, for
abbreviations and English that TTS misreads: `{ภ.ง.ด.90|ภองอดอเก้าสิบ}`.
`## outro +1.5` holds the scene 1.5 s past the end of its voice.
`## fix ~bright` sets the music's mood from this scene on (calm | tense | bright).
"""
from __future__ import annotations

import re
from pathlib import Path

MOODS = ("calm", "tense", "bright")
HEADING = re.compile(r"^##\s+([\w-]+)((?:\s+(?:\+\d+(?:\.\d+)?s?|~[a-z]+))*)\s*$")
SAY_AS = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")


def parse(path: Path) -> list[dict]:
    """Return [{"id", "text", "speech", "hold", "mood"}] in file order. `#` titles and <!-- --> comments are skipped."""
    raw = re.sub(r"<!--.*?-->", "", Path(path).read_text(encoding="utf-8"), flags=re.S)
    scenes: list[dict] = []
    for line in raw.splitlines():
        m = HEADING.match(line)
        if m:
            hold, mood = 0.0, None
            for tok in m.group(2).split():
                if tok.startswith("+"):
                    hold = float(tok[1:].rstrip("s"))
                elif tok[1:] in MOODS:
                    mood = tok[1:]
                else:
                    raise ValueError(f"{path}: unknown mood {tok!r} in {line!r}, expected one of {MOODS}")
            scenes.append({"id": m.group(1), "hold": hold, "mood": mood, "lines": []})
        elif re.match(r"##\s", line):
            raise ValueError(f"{path}: bad scene heading {line!r}, expected '## <id> [+<seconds>] [~<mood>]'")
        elif scenes and line.strip() and not line.startswith("#"):
            scenes[-1]["lines"].append(line.strip())
    out = []
    for s in scenes:
        raw_text = " ".join(s["lines"])
        out.append({"id": s["id"], "text": SAY_AS.sub(r"\1", raw_text), "speech": SAY_AS.sub(r"\2", raw_text),
                    "hold": s["hold"], "mood": s["mood"]})
    ids = [s["id"] for s in out]
    if not out:
        raise ValueError(f"{path}: no '## <scene-id>' headings found")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate scene ids in {ids}")
    if empty := [s["id"] for s in out if not s["text"]]:
        raise ValueError(f"{path}: scenes with no text: {empty}")
    return out
