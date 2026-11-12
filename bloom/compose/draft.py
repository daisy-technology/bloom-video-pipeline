"""draft.md: the video, written for the person to review, in a fixed shape that turns into the spec exactly.

    ---
    status: draft            ← the person approves; then status: approved
    title: …
    size: 1920x1080          (or 1080x1920)
    look: iso-clean
    motion: calm             (calm | clean | playful | energetic)
    voice: omnivoice:female, young adult
    music: lofi              (a Bloom mood, or a file such as media/music.mp3)
    ending: question         (question | teaser)
    cam: #ground 0.6         (where the camera starts: an id and a zoom)
    ---
    # Title
    One paragraph: what the video is and who it's for.

    ## cast                  ← everything that appears, once
    | id | kind | args |

    ## <scene> [+hold] [~mood]
    > The narration, exactly as it will be spoken.
    | on | do | what | args |   ← what happens, on which word
    Any other lines are notes for the reviewer.

    ## music
    | on | do |                ← cues: scene@word | drop · lift · duck · stop

Tables and the narration become the spec; notes ride along so the draft can be written back from a spec.
"""
from __future__ import annotations

import re
from pathlib import Path

HEADING = re.compile(r"^##\s+([\w.-]+)((?:\s+(?:\+\d+(?:\.\d+)?s?|~[a-z]+))*)\s*$")
FRONT = ("status", "title", "size", "look", "motion", "voice", "music", "ending", "cam")


class DraftError(ValueError):
    pass


def _row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def _table(rows: list[str], cols: tuple, where: str, first: int) -> list[dict]:
    head = [c.lower() for c in _row(rows[0])]
    if tuple(head) != cols:
        raise DraftError(f"line {first}: {where} table needs the columns | {' | '.join(cols)} |, found | {' | '.join(head)} |")
    out = []
    for k, line in enumerate(rows[2:], first + 2):  # rows[1] is the |---| rule
        cells = _row(line)
        if len(cells) != len(cols):
            raise DraftError(f"line {k}: {where} row has {len(cells)} cells, expected {len(cols)}: {line.strip()}")
        out.append(dict(zip(cols, cells)))
    return out


def parse(text: str) -> tuple[dict, str]:
    """draft.md -> (spec, status)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DraftError("line 1: a draft starts with --- and its settings (status, title, size, …)")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise DraftError("the settings block at the top has no closing ---")
    video = {}
    for k, line in enumerate(lines[1:end], 2):
        if not line.strip():
            continue
        key, sep, val = line.partition(":")
        if not sep or key.strip() not in FRONT:
            raise DraftError(f"line {k}: unknown setting {line.strip()!r} (settings: {', '.join(FRONT)})")
        video[key.strip()] = re.sub(r"\s+#\s.*$", "", val).strip()  # a "  # comment" after a value is dropped
    status = video.pop("status", "draft")
    spec = {"video": video, "cast": [], "scenes": [], "music": {"cues": []}}
    blocks, cur, pitch = [], None, []
    for k, line in enumerate(lines[end + 1:], end + 2):
        if line.startswith("## "):
            m = HEADING.match(line)
            if not m:
                raise DraftError(f"line {k}: a section heading is ## <id> [+hold] [~mood], found {line!r}")
            cur = {"id": m.group(1), "flags": m.group(2), "lines": [], "line": k}
            blocks.append(cur)
        elif line.startswith("# ") and cur is None:
            video.setdefault("title", line[2:].strip())
        elif cur is None:
            if line.strip():
                pitch.append(line.strip())
        else:
            cur["lines"].append((k, line))
    if pitch:
        video["pitch"] = " ".join(pitch)
    for b in blocks:
        tables, said, notes, run = [], [], [], []
        for k, line in b["lines"] + [(None, "")]:
            if line.strip().startswith("|"):
                run.append((k, line))
                continue
            if run:
                tables.append(run)
                run = []
            if line.startswith(">"):
                said.append(line.lstrip("> ").strip())
            elif line.strip():
                notes.append(line.rstrip())
        if b["id"] == "cast":
            for t in tables:
                spec["cast"] += _table([l for _, l in t], ("id", "kind", "args"), "cast", t[0][0])
        elif b["id"] == "music":
            for t in tables:
                spec["music"]["cues"] += _table([l for _, l in t], ("on", "do"), "music", t[0][0])
        else:
            scene = {"id": b["id"], "hold": 0.0, "mood": "", "say": " ".join(said), "note": "\n".join(notes), "beats": []}
            for flag in b["flags"].split():
                if flag.startswith("+"):
                    scene["hold"] = float(flag[1:].rstrip("s"))
                elif flag.startswith("~"):
                    scene["mood"] = flag[1:]
            for t in tables:
                scene["beats"] += _table([l for _, l in t], ("on", "do", "what", "args"), f"scene {b['id']}", t[0][0])
            if not scene["say"]:
                raise DraftError(f"line {b['line']}: scene {b['id']} has no narration line (> …)")
            spec["scenes"].append(scene)
    return spec, status


def write(spec: dict, status: str = "draft") -> str:
    """spec -> draft.md (the inverse of parse)."""
    v = dict(spec.get("video") or {})
    out = ["---", f"status: {status}"] + [f"{k}: {v[k]}" for k in FRONT[1:] if v.get(k) not in (None, "")] + ["---", ""]
    out += [f"# {v.get('title', '')}", ""]
    if v.get("pitch"):
        out += [v["pitch"], ""]
    cell = lambda s: str(s).replace("|", "\\|")  # noqa: E731
    if spec.get("cast"):
        out += ["## cast", "", "| id | kind | args |", "|---|---|---|"]
        out += [f"| {cell(c['id'])} | {cell(c['kind'])} | {cell(c.get('args', ''))} |" for c in spec["cast"]] + [""]
    for s in spec.get("scenes") or []:
        flags = (f" +{s['hold']:g}" if float(s.get("hold") or 0) else "") + (f" ~{s['mood']}" if s.get("mood") else "")
        out += [f"## {s['id']}{flags}", f"> {s['say']}", ""]
        if s.get("beats"):
            out += ["| on | do | what | args |", "|---|---|---|---|"]
            out += [f"| {cell(b['on'])} | {cell(b['do'])} | {cell(b['what'])} | {cell(b.get('args', ''))} |" for b in s["beats"]] + [""]
        if s.get("note"):
            out += [s["note"], ""]
    cues = (spec.get("music") or {}).get("cues") or []
    if cues:
        out += ["## music", "", "| on | do |", "|---|---|"] + [f"| {cell(c['on'])} | {cell(c['do'])} |" for c in cues] + [""]
    return "\n".join(out)


def read(project: Path) -> tuple[dict, str]:
    f = project / "draft.md"
    if not f.exists():
        raise DraftError(f"{f}: no draft yet (bloom draft {project})")
    return parse(f.read_text(encoding="utf-8"))
