"""Caption cues and .srt output.

Thai has no spaces between words; a space marks a phrase break. So cues split only on
spaces, never inside a phrase, and each cue's time is shared out by character count.
The exceptions are spaces Thai spelling requires around ๆ and numbers ("เงียบ ๆ",
"บรรทัดที่ 18"): those glue with a no-break space, so neither a cue nor the browser's
line wrap can strand "ๆ" or a number on its own. Authors can glue anything else with NBSP.
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_CHARS = 38  # one line on a 1080-wide frame at the caption size the templates use
MIN_CHARS = 8   # shorter than this ("SPRC", "ครับ") reads as a stray word on screen
GLUE = " "


def phrases(text: str) -> list[str]:
    out: list[str] = []
    for tok in re.split(r"[ \t\r\n]+", text.strip()):  # ASCII whitespace only: an author's NBSP stays glue
        if out and (tok.startswith("ๆ") or tok[0].isdigit()):
            out[-1] += GLUE + tok
        elif tok:
            out.append(tok)
    return out


def chunk(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    lines: list[str] = []
    for phrase in phrases(text):
        if lines and len(lines[-1]) + 1 + len(phrase) <= max_chars:
            lines[-1] += " " + phrase
        else:
            lines.append(phrase)  # a phrase longer than max_chars stays whole
    # fold stubs into the line before: a stub nearly always ends the phrase it belongs to
    # (หรือ "SPRC"); only a leading stub folds forward
    out: list[str] = []
    for line in lines:
        if out and (len(line) < MIN_CHARS or len(out[-1]) < MIN_CHARS):
            out[-1] += " " + line
        else:
            out.append(line)
    return out


def cues(text: str, start: float, dur: float) -> list[tuple[float, float, str]]:
    lines = chunk(text)
    total = sum(len(s) for s in lines)
    out, t = [], start
    for line in lines:
        d = dur * len(line) / total
        out.append((t, t + d, line))
        t += d
    return out


def _ts(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms // 3_600_000:02}:{ms // 60_000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(all_cues: list[tuple[float, float, str]], path: Path) -> Path:
    blocks = [f"{i}\n{_ts(s)} --> {_ts(e)}\n{line}\n" for i, (s, e, line) in enumerate(all_cues, 1)]
    Path(path).write_text("\n".join(blocks), encoding="utf-8")
    return path
