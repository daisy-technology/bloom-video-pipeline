"""The component library: what a spec can put on screen (kinds) and what its beats can do (verbs).

Every kind renders to HTML that is seek-safe by construction (state comes from motion.js's data-after /
data-until and the video clock in compose.js, never from timers). A spec names only these; a new visual
idea becomes a new kind here, with a test, never hand-written HTML in a page.

World kinds sit in one isometric world outside every section, so they stay on screen across cuts and keep
what happened (a long take, or a 9:16 world the camera moves through). Screen kinds sit in the section of
the scene that first shows them, in fixed bands (headline, labels, the closing question).
"""
from __future__ import annotations

import html as _h
import shlex
from dataclasses import dataclass, field


@dataclass
class Kind:
    name: str
    place: str          # "world" or "screen"
    args: dict          # arg -> one-line help (the catalog)
    verbs: tuple        # verbs a beat may use on it
    doc: str
    render: callable = field(repr=False, default=None)


def parse_args(text: str) -> dict:
    """'at="1 0 0" size="3 2 2" color=c1' -> {"at": "1 0 0", ...}. Values with spaces go in quotes."""
    out = {}
    for tok in shlex.split(text or ""):
        k, sep, v = tok.partition("=")
        if not sep:
            raise ValueError(f"argument {tok!r} should be name=value")
        out[k.strip()] = v
    return out


def esc(s: str) -> str:
    return _h.escape(str(s), quote=True)


def lines(text: str) -> list[str]:
    return [x.strip() for x in str(text).replace("\\n", "\n").split("\n")]


def color(v: str | None, default: str = "c1") -> str:
    v = v or default
    return f"var(--{v})" if v in ("c1", "c2", "c3", "c4", "accent", "floor", "ink", "soft") else v


def nums(v: str | None, n: int, default: str) -> list[float]:
    vals = [float(x) for x in str(v or default).replace(",", " ").split()]
    if len(vals) != n:
        raise ValueError(f"expected {n} numbers, got {v!r}")
    return vals


# ---- renderers: (id, args, state) -> HTML. `state` is the attribute string compose built from the beats
# (data-after / data-until / data-ease / data-len / data-play-at); each kind decides which element carries it.

def _tile(i, a, st):
    x, y = nums(a.get("at"), 2, "0 0"); w, d = nums(a.get("size"), 2, "4 2")
    return f'<div id="{esc(i)}" data-tile="{x:g} {y:g} {w:g} {d:g}" style="--c: {color(a.get("color"), "floor")}" {st}></div>'


def _box(i, a, st):
    x, y, z = nums(a.get("at"), 3, "0 0 0"); w, d, h = nums(a.get("size"), 3, "2 2 2")
    return (f'<div id="{esc(i)}" class="build" data-box="{x:g} {y:g} {z:g} {w:g} {d:g} {h:g}" '
            f'style="--c: {color(a.get("color"))}" {st}></div>')


def _pin(i, a, st):
    x, y, z = nums(a.get("at"), 3, "0 0 0")
    return f'<div id="{esc(i)}" class="tag grow" data-pin="{x:g} {y:g} {z:g}" {st}>{esc(a.get("text", i))}</div>'


def _card(i, a, st):
    x, y, z = nums(a.get("at"), 3, "0 0 0")
    body = "".join(f'<p data-type-line>{esc(t)}</p>' for t in lines(a.get("text", "")))
    title = f'<header>{esc(a["title"])}</header>' if a.get("title") else ""
    return (f'<div id="{esc(i)}" class="card grow" data-pin="{x:g} {y:g} {z:g}" style="width:{float(a.get("w", 420)):g}px" '
            f'{st}>{title}<div class="body">{body}</div></div>')


def _phone(i, a, st):
    x, y, z = nums(a.get("at"), 3, "0 0 0")
    w = float(a.get("w", 220)); h = w * 16 / 9
    label = f'<span class="tag">{esc(a["label"])}</span>' if a.get("label") else ""
    sheet = esc(a.get("sheet", ""))
    return (f'<div id="{esc(i)}" class="phone grow" data-pin="{x:g} {y:g} {z:g}" {st}>{label}'
            f'<div class="screen" data-sheet="{sheet}" style="width:{w:g}px;height:{h:g}px;'
            f'background-image:url({sheet});background-size:{w * 8:g}px {h * 5:g}px"></div></div>')


def _line(i, a, st, project=None):
    return f'<svg id="{esc(i)}" class="wline" data-line="{esc(a.get("from", "0 0 0"))};{esc(a.get("to", "1 0 0"))}" style="--c: {color(a.get("color"), "accent")}" {st}></svg>'


def _count(i, a, st):
    x, y, z = nums(a.get("at"), 3, "0 0 0")
    fmt = f'data-from="{esc(a.get("from", 0))}" data-to="{esc(a.get("to", 0))}" data-dec="{esc(a.get("dec", 0))}" ' \
          f'data-pre="{esc(a.get("pre", ""))}" data-suf="{esc(a.get("suf", ""))}"'
    label = f'<small>{esc(a["label"])}</small>' if a.get("label") else ""
    return (f'<div id="{esc(i)}" class="counter grow" data-pin="{x:g} {y:g} {z:g}" {st}>'
            f'<b data-count {fmt}>{esc(a.get("pre", ""))}{esc(a.get("from", 0))}{esc(a.get("suf", ""))}</b>{label}</div>')


def _headline(i, a, st):
    rows = "".join(f'<span class="rise"><span>{esc(t)}</span></span>' for t in lines(a.get("text", "")))
    sub = f'<p class="wipe">{esc(a["sub"])}</p>' if a.get("sub") else ""
    return f'<div id="{esc(i)}" class="head appear" {st}><h1 data-stagger>{rows}</h1>{sub}</div>'


def _label(i, a, st):
    x, y = nums(a.get("xy"), 2, "120 300")
    return f'<div id="{esc(i)}" class="tag grow" style="left:{x:g}px;top:{y:g}px" {st}>{esc(a.get("text", i))}</div>'


def _ask(i, a, st):
    sub = f'<p>{esc(a["sub"])}</p>' if a.get("sub") else ""
    return f'<div id="{esc(i)}" class="ask grow" {st}><h1>{esc(a.get("text", ""))}</h1>{sub}</div>'


KINDS = {k.name: k for k in [
    Kind("tile", "world", {"at": "x y on the grid", "size": "w d", "color": "c1..c4, floor, or a CSS colour"},
         ("show", "hide"), "a flat floor plate: the ground, a road, a pad", _tile),
    Kind("box", "world", {"at": "x y z", "size": "w d h", "color": "c1..c4 or a CSS colour"},
         ("show", "hide"), "an isometric block; `show` raises it from its base", _box),
    Kind("pin", "world", {"at": "x y z (the point it hangs above)", "text": "the label"},
         ("show", "hide"), "a flat, readable label pinned to a world point", _pin),
    Kind("card", "world", {"at": "x y z", "title": "header text", "text": "lines, split with \\n", "w": "width px (420)"},
         ("show", "hide", "type"), "a flat UI card (a file, a panel); `type` writes its lines out", _card),
    Kind("phone", "world", {"at": "x y z", "sheet": "sprite sheet: 8×5 frames of 9:16, 10 fps", "w": "width px (220)", "label": "a tag above it"},
         ("show", "hide", "play"), "a phone playing a clip (a sprite sheet); `play` starts it", _phone),
    Kind("line", "world", {"from": "x y z", "to": "x y z", "color": "accent by default"},
         ("show", "hide", "draw"), "a line on the ground or in the air; `draw` draws it on", _line),
    Kind("count", "world", {"at": "x y z", "from": "start value", "to": "end value", "dec": "decimals",
                            "pre": "prefix", "suf": "suffix", "label": "small text under it"},
         ("show", "hide", "count"), "a number pinned in the world; `count` counts it up, eased out", _count),
    Kind("headline", "screen", {"text": "lines, split with \\n", "sub": "one line under it (a source)"},
         ("show", "hide"), "the title band top-left: lines rise in, the sub wipes in", _headline),
    Kind("label", "screen", {"text": "the label", "xy": "x y in px on the frame"},
         ("show", "hide"), "a label fixed on the frame (prefer a world pin)", _label),
    Kind("ask", "screen", {"text": "the question", "sub": "a small line under it (a URL)"},
         ("show", "hide"), "the closing question card, centred near the top", _ask),
]}

VERBS = {
    "show": "make it appear (a block rises, a label grows); stays shown in later scenes · len=seconds",
    "hide": "make it leave · len=seconds",
    "type": "write a card's lines out, steadily · len=seconds (default: by length)",
    "count": "count a number up to its `to`, eased out · len=seconds (default 1)",
    "play": "start a phone's clip; it plays on through cuts",
    "draw": "draw a line on · len=seconds (default .8)",
    "cam": "move the camera to `what` (an id) · zoom=1 · len=1.2 · the move lasts len, eased in-out",
    "sfx": "play a sound effect named in `what` (hit, pop, whoosh, riser, sting, chime, buzz, …)",
    "end": "end the video: `what` = cut (black at once, music stops) or fade (len=1) — the hook rule",
}


def catalog() -> str:
    """The compact table an agent reads instead of any kit code."""
    rows = ["KINDS (cast: id | kind | args)"]
    for k in KINDS.values():
        rows.append(f"  {k.name:<9}{k.place:<7}{k.doc}")
        rows.append(f"           args: " + " · ".join(f"{a}={h}" for a, h in k.args.items()))
        rows.append(f"           verbs: {', '.join(k.verbs)}")
    rows.append("VERBS (beats: on | do | what | args)")
    rows += [f"  {v:<7}{h}" for v, h in VERBS.items()]
    rows.append("ON: a word of the scene's narration (ขาด, ขาด#2, ขาด+0.3) · seconds (2.4) · 60% · -1.5 (before the end) · start · end")
    return "\n".join(rows)
