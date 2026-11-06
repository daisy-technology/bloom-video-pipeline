"""Read a voiceover script: one `## <scene-id>` heading per scene, text below it.

`{shown|spoken}` splits what the caption shows from what the voice says, for
abbreviations and English that TTS misreads: `{ภ.ง.ด.90|ภองอดอเก้าสิบ}`.
`## outro +1.5` holds the scene 1.5 s past the end of its voice.
"""
from __future__ import annotations

import re
from pathlib import Path

HEADING = re.compile(r"^##\s+([\w-]+)(?:\s+\+(\d+(?:\.\d+)?)s?)?\s*$")
SAY_AS = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")


def parse(path: Path) -> list[dict]:
    """Return [{"id", "text", "speech", "hold"}] in file order. `#` titles and <!-- --> comments are skipped."""
    raw = re.sub(r"<!--.*?-->", "", Path(path).read_text(encoding="utf-8"), flags=re.S)
    scenes: list[dict] = []
    for line in raw.splitlines():
        m = HEADING.match(line)
        if m:
            scenes.append({"id": m.group(1), "hold": float(m.group(2) or 0), "lines": []})
        elif re.match(r"##\s", line):
            raise ValueError(f"{path}: bad scene heading {line!r}, expected '## <id>' or '## <id> +<seconds>'")
        elif scenes and line.strip() and not line.startswith("#"):
            scenes[-1]["lines"].append(line.strip())
    out = []
    for s in scenes:
        raw_text = " ".join(s["lines"])
        out.append({"id": s["id"], "text": SAY_AS.sub(r"\1", raw_text), "speech": SAY_AS.sub(r"\2", raw_text),
                    "hold": s["hold"]})
    ids = [s["id"] for s in out]
    if not out:
        raise ValueError(f"{path}: no '## <scene-id>' headings found")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate scene ids in {ids}")
    if empty := [s["id"] for s in out if not s["text"]]:
        raise ValueError(f"{path}: scenes with no text: {empty}")
    return out
