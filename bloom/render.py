"""Animated HTML scenes -> MP4, frame by frame.

The page is a normal HTML file with one `<section data-scene="<id>">` per script scene,
animated with CSS animations or the Web Animations API. For each output frame the
renderer pauses every animation and seeks it to that frame's time, then screenshots.
That makes the render deterministic: a slow machine gives the same video, just later.

Contract for scenes.html:
  - `<section data-scene="id">` per scene; only the current one is shown
  - animation delays count from the start of that scene; an element outside every section (a news
    ticker, a frame, a logo bug) stays on screen across cuts, so its animations run on the video's
    clock instead and never restart or jump at a cut
  - the shown section gets `--scene-dur: <seconds>s`, for exits:
    `animation-delay: calc(var(--scene-dur) - .4s)`
  - optional `#caption` element: the renderer writes the current caption line into it
  - optional `window.bloomSeek(sceneId, seconds, videoSeconds)` for canvas / JS-driven motion; the third
    argument is the video's clock, for motion that runs on across cuts (a long take's world)
  - optional `data-sfx="<effect>"` on an animated element: that effect plays when its
    animation starts (see bloom/sound.py for the effects). Several effects, each at its own
    moment of the element's first animation: `data-sfx="riser hit@end"` (a riser spans the
    animation and a hit lands as it ends), `zip@.2 thud@.86` (seconds into the animation)
  - the voice drives `<html data-mouth="0|1|2">` (closed, half, open) and `--voice` (0 to 1)
    on every frame, so a character's mouth moves with the words and rests in the pauses:
    `html[data-mouth] .talk { animation: none; opacity: 0 } html[data-mouth="2"] .talk { opacity: 1 }`.
    Drive plain properties from them, not animations (an animation they start isn't seeked).

The renderer writes the picture only; the build mixes the audio and muxes it on afterwards,
using the sound-effect cues collected here.

Frames are independent (every one is a seek), so the scenes are split into groups of whole
scenes and rendered by several workers at once, each with its own browser and encoder; the
parts are joined without re-encoding. A worker always starts on a scene's first frame, exactly
like the one-worker render, so no frame lands on a layer Chromium hasn't rasterised yet.
"""
from __future__ import annotations

import functools
import itertools
import multiprocessing
import os
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from .sound import ENDINGS, SFX, STRETCH

HIDE_OTHERS = "[data-scene]:not([data-on]){display:none!important}"

# ---- the brand: added by Bloom at render time to every video (not written into pages), so every video
# carries it the same way. A small mark in the corner, on the video's clock (it never restarts at a cut).
BRANDS = ("daisy", "daisy-end", "none")  # quiet corner mark all video · the mark only at the end · none
BRAND_END = 3.0  # daisy-end: the mark arrives this long before the video's end (the end cut covers it)
_BRAND_DIR = Path(__file__).parent / "compose" / "assets" / "brand"


def _data_uri(name: str, mime: str) -> str:
    import base64
    return f"data:{mime};base64," + base64.b64encode((_BRAND_DIR / name).read_bytes()).decode()


def brand_layer(size: tuple[int, int], brand: str = "daisy", total: float | None = None) -> tuple[str, str] | None:
    """(css, html) for the brand mark: Bloom's icon, then Daisy Technology's logo, and nothing else (no pill,
    no shadow, no text). "daisy": small and translucent in a corner the whole video (bottom right inside the
    title-safe area on 16:9, top right below the app's header on 9:16). "daisy-end": larger and opaque, only in the
    last BRAND_END seconds (needs the video's total length). None for brand "none"."""
    if brand == "none":
        return None
    if brand not in BRANDS:
        raise ValueError(f"brand {brand!r}: expected one of {BRANDS}")
    w, h = size
    wide = w > h
    # 16:9: bottom right, the broadcast bug's place, clear of headers, question cards and the centred captions;
    # 9:16: top right, since the app's buttons own the bottom right
    pos = "bottom: 64px; right: 100px" if wide else "top: 200px; right: 60px"
    if brand == "daisy-end":
        s, show, start = (60 if wide else 66), 1, max(0.0, (total or BRAND_END) - BRAND_END)
    else:
        s, show, start = (40 if wide else 44), .55, 0.3
    css = f"""#bloom-brand {{ position: absolute; {pos}; z-index: 80; display: flex; align-items: center; gap: {round(s * .3)}px;
      opacity: 0; animation: bloom-brand-in .6s ease-out {start:.3f}s forwards; pointer-events: none; }}
    #bloom-brand img {{ width: {s}px; height: {s}px; border-radius: {round(s * .23)}px; display: block; }}
    @keyframes bloom-brand-in {{ to {{ opacity: {show}; }} }}"""
    html = (f'<div id="bloom-brand" data-audit="safe" aria-label="Bloom by Daisy Technology">'
            f'<img src="{_data_uri("bloom-icon.png", "image/png")}" alt="Bloom">'
            f'<img src="{_data_uri("daisy-logo.png", "image/png")}" alt="Daisy Technology"></div>')
    return css, html


# The mark sits above the page, so the end cut's black (inside its scene) can't cover it: each frame, after
# the animations are set, the mark takes the inverse of the end layer's opacity. A cut takes it at once, a fade
# fades it, and the black after the end stays black.
BRAND_FOLLOWS_END = """() => {
  const mark = document.getElementById('bloom-brand'), before = window.bloomSeek;
  window.bloomSeek = (id, t, now) => {
    if (before) before(id, t, now);
    const end = document.querySelector('[data-on] .end-cut, [data-on] .end-fade');
    mark.style.visibility = '';
    mark.style.filter = '';
    if (end) {
      const o = +getComputedStyle(end).opacity || 0;
      if (o >= .999) mark.style.visibility = 'hidden';
      else if (o > 0) mark.style.filter = `opacity(${(1 - o).toFixed(3)})`;
    }
  };
}"""


# ---- banding. An 8-bit video steps a smooth gradient (a navy sky, a soft shadow on a pale floor) into visible
# bands, and Bloom's pages are perfectly clean, so nothing hides the steps. Every frame is debanded in 16 bits and
# brought back to 8 with error-diffusion dithering before it is encoded: gradients come out smooth, with no visible
# noise and little extra bitrate. Measured on a navy radial gradient: flat runs (the bands) 19 px -> 2.7 px.
DEBAND = ("format=gbrp16le,deband=1thr=0.015:2thr=0.015:3thr=0.015:range=24:blur=1,"
          "scale=sws_dither=ed,format=yuv420p")


def prepare(page, html: Path, size: tuple[int, int], brand: str = "daisy", total: float | None = None) -> None:
    """Open a page the way every render and every check sees it: one scene shown at a time, the brand mark
    added, fonts loaded."""
    page.goto(Path(html).resolve().as_uri())
    page.add_style_tag(content=HIDE_OTHERS)
    layer = brand_layer(size, brand, total)
    if layer:
        page.add_style_tag(content=layer[0])
        page.evaluate("h => document.body.insertAdjacentHTML('beforeend', h)", layer[1])
        page.evaluate(BRAND_FOLLOWS_END)
    page.evaluate("document.fonts.ready")

SHOW = """([id, dur]) => {
  document.querySelectorAll('[data-scene]').forEach(s => s.toggleAttribute('data-on', s.dataset.scene === id));
  const el = document.querySelector(`[data-scene="${CSS.escape(id)}"]`);
  if (el) el.style.setProperty('--scene-dur', dur + 's');
  return !!el;
}"""

# every data-sfx element in the shown scene, with when its own first animation starts and how long it runs
CUES = """() => [...document.querySelectorAll('[data-on] [data-sfx], [data-on][data-sfx]')].map(el => {
  const a = el.getAnimations()[0];
  const t = a ? a.effect.getTiming() : {};
  return {sfx: el.dataset.sfx, at: (+t.delay || 0) / 1000, dur: (+t.duration || 0) / 1000,
          iterations: Number.isFinite(t.iterations) ? +t.iterations : 1,
          steps: parseInt(getComputedStyle(el).getPropertyValue('--n')) || 0};
})"""

# the mouth goes first: changing it restyles the page, and the seek below then covers every animation
SEEK = """([id, t, caption, mouth, now]) => {
  const r = document.documentElement;
  if (mouth) {
    if (r.dataset.mouth !== String(mouth[0])) r.dataset.mouth = mouth[0];
    r.style.setProperty('--voice', mouth[1].toFixed(3));
  } else if (r.hasAttribute('data-mouth')) {
    r.removeAttribute('data-mouth');
    r.style.removeProperty('--voice');
  }
  for (const a of document.getAnimations()) {  // outside the sections: the video's clock, so it runs on through cuts
    a.pause();
    const el = a.effect && a.effect.target;
    a.currentTime = (now != null && el && !el.closest('[data-scene]') ? now : t) * 1000;
  }
  const c = document.getElementById('caption');
  if (c && c.textContent !== caption) c.textContent = caption;
  if (window.bloomSeek) window.bloomSeek(id, t, now);
}"""


def cue_events(found: dict, start: float, scene_dur: float) -> list[dict]:
    """One data-sfx element's effects on the video clock. `found` is what CUES reports for it.

    Each token is `name`, `name@end` or `name@<seconds>`: when the element's first animation
    starts, ends (all its iterations), or that long after it starts. A stretched effect (riser)
    runs from its moment to the animation's end, so it lands exactly where the motion does."""
    out = []
    end = found["at"] + found["dur"] * max(1, found.get("iterations") or 1)
    for tok in found["sfx"].split():
        name, _, when = tok.partition("@")
        if name not in SFX and name not in ENDINGS and name != "click":
            raise ValueError(f'data-sfx="{found["sfx"]}": unknown effect {name!r}, expected one of {SFX + ENDINGS}')
        try:
            at = end if when == "end" else found["at"] + (float(when.rstrip("s")) if when else 0.0)
        except ValueError:
            raise ValueError(f'data-sfx="{found["sfx"]}": {tok!r} should be {name}, {name}@end or {name}@<seconds>') from None
        if at >= scene_dur:
            continue
        dur = max(0.0, end - at) if name in STRETCH + ENDINGS else found["dur"]
        out.append({"sfx": name, "t": start + at, "dur": dur, "steps": found["steps"]})
    return out


def _scene_cues(page, scene: dict) -> list[dict]:
    return [e for c in page.evaluate(CUES) for e in cue_events(c, scene["start"], scene["dur"])]


def sfx_cues(html: Path, timeline: list[dict], size: tuple[int, int] = (1080, 1920)) -> list[dict]:
    """The page's sound-effect cues on `timeline`, without rendering a single frame."""
    out: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        page.goto(Path(html).resolve().as_uri())
        page.add_style_tag(content=HIDE_OTHERS)
        for scene in timeline:
            if page.evaluate(SHOW, [scene["id"], scene["dur"]]):
                out += _scene_cues(page, scene)
        browser.close()
    return out


def default_workers() -> int:
    """BLOOM_RENDER_WORKERS, else 3 on a machine with 7+ cores (leaving room for the encoders), else 1."""
    env = os.environ.get("BLOOM_RENDER_WORKERS")
    return max(1, int(env)) if env else max(1, min(3, (os.cpu_count() or 2) - 4))


def _partition(timeline: list[dict], fps: int, workers: int) -> list[list[dict]]:
    """Contiguous groups of whole scenes, each cut placed at the scene boundary nearest an even split."""
    workers = max(1, min(workers, len(timeline)))
    frames = [round(s["dur"] * fps) for s in timeline]
    cum, total = list(itertools.accumulate(frames)), sum(frames)
    cuts, last = [], -1
    for k in range(1, workers):  # leave at least one scene for every group still to come
        last = min(range(last + 1, len(timeline) - (workers - k)), key=lambda j: abs(cum[j] - total * k / workers))
        cuts.append(last)
    bounds = [-1, *cuts, len(timeline) - 1]
    return [timeline[a + 1:b + 1] for a, b in zip(bounds, bounds[1:])]


def render(html: Path, timeline: list[dict], cues: list[tuple], out: Path,
           size: tuple[int, int] = (1080, 1920), fps: int = 30, workers: int | None = None,
           mouth: list | None = None, brand: str = "daisy", deband: bool = True) -> tuple[Path, list[dict]]:
    """timeline = [{"id", "start", "dur"}] in seconds; cues = [(start, end, text)] on the same clock.
    mouth = [(state, level)] per output frame (bloom.lipsync), or None to leave the page's mouths looping.
    Writes a silent video; returns it with the page's sound-effect cues [{"t", "sfx", "dur", "steps"}]."""
    frame0 = itertools.accumulate((round(s["dur"] * fps) for s in timeline), initial=0)
    timeline = [{**s, "frame0": f, "mouth": _slice(mouth, f, round(s["dur"] * fps))} for s, f in zip(timeline, frame0)]
    groups = _partition(timeline, fps, workers or default_workers())
    total = timeline[-1]["start"] + timeline[-1]["dur"] if timeline else None
    if len(groups) == 1:
        return out, _render_scenes(html, timeline, cues, out, size, fps, brand, deband, total)
    with tempfile.TemporaryDirectory(dir=Path(out).parent) as tmp:
        parts = [Path(tmp) / f"part-{k}.mp4" for k in range(len(groups))]
        with multiprocessing.get_context("spawn").Pool(len(groups)) as pool:
            found = pool.starmap(_render_scenes, [(html, g, cues, p, size, fps, brand, deband, total) for g, p in zip(groups, parts)])
        listing = Path(tmp) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(out)], check=True)
    return out, [c for cues_k in found for c in cues_k]


def _slice(mouth: list | None, first: int, n: int) -> list | None:
    """This scene's frames of the mouth track, the last value held if the track is short."""
    if not mouth:
        return None
    return [list(mouth[min(first + k, len(mouth) - 1)]) for k in range(n)]


def _render_scenes(html: Path, timeline: list[dict], cues: list[tuple], out: Path,
                   size: tuple[int, int], fps: int, brand: str = "daisy", deband: bool = True,
                   total: float | None = None) -> list[dict]:
    """Render these scenes (on the full video's clock) to `out`; return their sound-effect cues."""
    w, h = size
    sfx: list[dict] = []
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(fps), "-i", "-",
         *(["-vf", DEBAND] if deband else []),
         # aq-mode 3 gives flat and dark areas their bits back: smooth gradients don't step into bands
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-x264-params", "aq-mode=3", "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE,
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": w, "height": h})
            prepare(page, html, size, brand, total)
            for scene in timeline:
                if not page.evaluate(SHOW, [scene["id"], scene["dur"]]):
                    raise ValueError(f'{html}: no <section data-scene="{scene["id"]}">')
                sfx += _scene_cues(page, scene)
                for f in range(round(scene["dur"] * fps)):
                    t = f / fps
                    now = scene["start"] + t
                    caption = next((c[2] for c in cues if c[0] <= now < c[1]), "")
                    page.evaluate(SEEK, [scene["id"], t, caption, scene["mouth"][f] if scene.get("mouth") else None,
                                         (scene["frame0"] + f) / fps])
                    ffmpeg.stdin.write(page.screenshot(type="jpeg", quality=95))
            browser.close()
    finally:
        ffmpeg.stdin.close()
        if ffmpeg.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {out}")
    return sfx
