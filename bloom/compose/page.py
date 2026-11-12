"""Spec + the voice's timing -> scenes.html and script.md. Nobody edits either by hand.

Every beat's `on` is resolved to seconds from the scene start with the voice that was just made, so the
page always lands on the words. World things are placed once, outside the sections (they stay across
cuts and keep what happened); screen things go in the section of the scene that first shows them.
"""
from __future__ import annotations

from pathlib import Path

from .components import KINDS, color, esc, parse_args
from .spec import digest
from .timing import moment

ASSETS = Path(__file__).parent / "assets"

LOOK = {  # per frame shape: world size and origin, the header band, the captions
    "wide": {"world": (3600, 2200), "origin": "1700 520", "unit": 56,
             "head": "left:120px;top:84px", "h1": 72, "caption": "left:240px;right:240px;bottom:90px;font-size:44px"},
    "tall": {"world": (2400, 3400), "origin": "1200 1000", "unit": 56,
             "head": "left:60px;top:200px", "h1": 84, "caption": "left:60px;right:60px;bottom:150px;font-size:48px"},
}
MOTION = {"calm": (".6s", "100ms"), "clean": (".4s", "70ms"), "playful": (".25s", "50ms"), "energetic": (".2s", "35ms")}


def script_md(spec: dict) -> str:
    v = spec["video"]
    out = [f"# {v.get('title', 'video')}", "",
           f"<!-- generated from video.toon ({digest(spec)}) by bloom spec. Edit draft.md, then run bloom spec. -->", ""]
    for s in spec["scenes"]:
        flags = (f" +{float(s['hold']):g}" if float(s.get("hold") or 0) else "") + (f" ~{s['mood']}" if s.get("mood") else "")
        out += [f"## {s['id']}{flags}", s["say"], ""]
    return "\n".join(out)


def _cam_start(value: str | None, origin: str) -> tuple[str, float]:
    """video.cam -> (target, zoom): "#ground 0.6" (an id and a zoom), "1700 520 0.8" (a point), or the origin."""
    parts = str(value or "").split()
    if not parts:
        return origin, 1.0
    if parts[0].startswith("#"):
        return parts[0], float(parts[1]) if len(parts) > 1 else 1.0
    return " ".join(parts[:2]), float(parts[2]) if len(parts) > 2 else 1.0


def compose(spec: dict, timing: list[dict], project: Path) -> str:
    v = spec["video"]
    w, h = (int(x) for x in v["size"].lower().split("x"))
    look = LOOK["wide" if w > h else "tall"]
    unit, ms = MOTION.get(v.get("motion", "calm"), MOTION["calm"])
    when = {t["id"]: t for t in timing}
    order = [s["id"] for s in spec["scenes"]]
    starts, clock = {}, 0.0
    for sid in order:
        starts[sid], clock = clock, clock + when[sid]["dur"]
    cast = {c["id"]: (KINDS[c["kind"]], parse_args(c.get("args", ""))) for c in spec.get("cast") or []}

    # ---- every beat -> (scene, seconds, verb, target, args)
    state = {cid: {} for cid in cast}          # cid -> attributes from its beats
    first_scene = {}                           # screen things live in the scene that first shows them
    cues = {sid: [] for sid in order}          # (seconds, effect) per scene
    ends = {sid: [] for sid in order}
    cams = {sid: [] for sid in order}
    for s in spec["scenes"]:
        sid = s["id"]
        for b in s.get("beats") or []:
            t = round(moment(b["on"], when[sid]), 3)
            a, verb, what = parse_args(b.get("args", "")), b["do"], str(b.get("what", "")).lstrip("#")
            if verb == "sfx":
                cues[sid].append((t, what))
                continue
            if verb == "end":
                ends[sid].append((t, what, a))
                continue
            if verb == "cam":
                cams[sid].append((t, f"#{what}", float(a.get("zoom", 1)), float(a.get("len", 1.2))))
                continue
            st, stamp = state[what], f"{sid}@{t:g}"
            first_scene.setdefault(what, sid)
            if verb == "show":
                st.setdefault("data-after", stamp)
                st.setdefault("data-len", a.get("len", ""))
                st["--at"] = f"{t:g}s"
            elif verb == "hide":
                st["data-until"] = stamp
            elif verb == "type":
                text = cast[what][1].get("text", "")
                st["data-type"], st["data-type-len"] = stamp, a.get("len", f"{max(.8, len(text) / 18):.2f}")
            elif verb == "count":
                st["data-count-at"], st["data-count-len"] = stamp, a.get("len", "1")
            elif verb == "play":
                st["data-play-at"] = f"{starts[sid] + t:.3f}"
            elif verb == "draw":
                st["data-draw"], st["data-draw-len"] = stamp, a.get("len", ".8")

    def attrs(cid: str) -> str:
        st = state[cid]
        out = " ".join(f'{k}="{esc(val)}"' for k, val in st.items() if k.startswith("data-") and val != "")
        if "--at" in st:
            out += f' style="--at: {st["--at"]}"'
        return out

    # ---- the camera: continuous across cuts; each scene starts where the last one ended
    cur = _cam_start(v.get("cam"), look["origin"])
    cam_attrs = []
    for sid in order:
        keys = [(0.0, cur)]
        for t, target, zoom, ln in sorted(cams[sid]):
            keys += [(t, cur), (min(t + ln, when[sid]["dur"]), (target, zoom))]
            cur = (target, zoom)
        cam_attrs.append(f'data-cam-{sid}="' + ", ".join(f"{t:g} {z:g} {tg}" for t, (tg, z) in keys) + '"')

    world_items, screen_items = [], {sid: [] for sid in order}
    for cid, (kind, a) in cast.items():
        markup = kind.render(cid, a, attrs(cid))
        if kind.place == "world":
            world_items.append(markup)
        else:
            screen_items[first_scene.get(cid, order[0])].append(markup)

    sections = []
    for sid in order:
        body = list(screen_items[sid])
        body += [f'<i class="cue" data-sfx="{esc(e)}" style="--at: {t:g}s"></i>' for t, e in cues[sid]]
        for t, kind, a in ends[sid]:
            if kind == "cut":
                body.append(f'<div class="end-cut" data-sfx="hit cut" style="--at: {t:g}s"></div>')
            else:
                body.append(f'<div class="end-fade" data-sfx="fade" style="--at: {t:g}s; --len: {float(a.get("len", 1)):g}s"></div>')
        sections.append(f'<section data-scene="{esc(sid)}">\n  ' + "\n  ".join(body) + "\n</section>")

    css = (ASSETS / "motion.css").read_text(encoding="utf-8")
    js = "\n".join((ASSETS / f).read_text(encoding="utf-8") for f in ("iso.js", "motion.js", "compose.js"))
    ww, wh = look["world"]
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{esc(v.get('title', 'video'))}</title>
<!-- generated from video.toon ({digest(spec)}) by bloom compose. Never edit this file: edit draft.md, run bloom spec, then build. -->
<style>
  :root {{ --bg: #eef2f7; --ink: #17202c; --soft: #5b6676; --accent: #ff5d73; --c1: #5b8def; --c2: #2ec4a6;
          --c3: #ffb84d; --c4: #ff5d73; --floor: #dde4ee; }}
  @font-face {{ font-family: Mitr; src: url(fonts/Mitr-Regular.ttf); font-weight: 400; }}
  @font-face {{ font-family: Mitr; src: url(fonts/Mitr-SemiBold.ttf); font-weight: 600; }}
  html, body {{ margin: 0; width: {w}px; height: {h}px; overflow: hidden; background: var(--bg);
               font-family: Mitr, system-ui, sans-serif; color: var(--ink); }}
  section {{ position: absolute; inset: 0; z-index: 10; }}
  .world {{ position: absolute; left: 0; top: 0; z-index: 0; width: {ww}px; height: {wh}px; }}
  .tag {{ font-size: 34px; font-weight: 600; background: #fff; padding: 10px 22px; border-radius: 999px;
          box-shadow: 0 10px 30px #17202c22; white-space: nowrap; }}
  section > .tag {{ position: absolute; }}
  .card {{ background: #fff; border-radius: 16px; box-shadow: 0 18px 50px #17202c24; overflow: hidden; font-size: 28px; }}
  .card header {{ background: var(--ink); color: #fff; padding: 10px 18px; font-size: 24px; }}
  .card .body {{ padding: 14px 18px; line-height: 1.45; }}
  .card p {{ margin: 0; min-height: 1.45em; }}
  .ghost {{ visibility: hidden; }}
  .phone {{ display: flex; flex-direction: column; align-items: center; gap: 12px; }}
  .phone .screen {{ border-radius: 22px; border: 8px solid var(--ink); background-color: #000;
                    box-shadow: 0 24px 60px #17202c33; }}
  .counter {{ text-align: center; background: #fff; border-radius: 18px; padding: 10px 26px; box-shadow: 0 14px 40px #17202c22; }}
  .counter b {{ display: block; font-size: 64px; line-height: 1.15; font-variant-numeric: tabular-nums; }}
  .counter small {{ font-size: 24px; color: var(--soft); }}
  .wline path {{ fill: none; stroke: var(--c); stroke-width: 10; stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 1; }}
  .head {{ position: absolute; {look['head']}; }}
  .head h1 {{ margin: 0; font-size: {look['h1']}px; line-height: 1.2; font-weight: 600; }}
  .head p {{ margin: 10px 0 0; font-size: 30px; color: var(--soft); }}
  .ask {{ position: absolute; left: 50%; top: 120px; translate: -50% 0; padding: 22px 48px 30px; border-radius: 28px;
          background: color-mix(in oklch, var(--bg) 92%, transparent); box-shadow: 0 20px 60px #17202c1f; text-align: center; }}
  .ask h1 {{ margin: 0; font-size: 68px; line-height: 1.25; font-weight: 600; white-space: nowrap; }}
  .ask p {{ margin: 8px 0 0; font-size: 30px; color: var(--soft); }}
  .cue {{ position: absolute; width: 0; height: 0; animation: m-cue .001s linear var(--at) both; }}
  @keyframes m-cue {{ to {{ opacity: 1 }} }}
  #caption {{ position: absolute; {look['caption']}; z-index: 50; text-align: center; line-height: 1.35; }}
  #caption:empty {{ display: none; }}
{css}
  :root {{ --u: {unit}; --stagger: {ms}; }}
</style>
</head>
<body>
<div class="world iso" data-unit="{look['unit']}" data-origin="{look['origin']}"
     {' '.join(cam_attrs)}>
  {chr(10).join('  ' + m for m in world_items).strip()}
</div>
{chr(10).join(sections)}
<div id="caption"></div>
<script>
{js}
</script>
</body>
</html>
"""
