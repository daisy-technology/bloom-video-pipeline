"""Animated HTML scenes -> MP4, frame by frame.

The page is a normal HTML file with one `<section data-scene="<id>">` per script scene,
animated with CSS animations or the Web Animations API. For each output frame the
renderer pauses every animation and seeks it to that frame's time, then screenshots.
That makes the render deterministic: a slow machine gives the same video, just later.

Contract for scenes.html:
  - `<section data-scene="id">` per scene; only the current one is shown
  - animation delays count from the start of that scene
  - the shown section gets `--scene-dur: <seconds>s`, for exits:
    `animation-delay: calc(var(--scene-dur) - .4s)`
  - optional `#caption` element: the renderer writes the current caption line into it
  - optional `window.bloomSeek(sceneId, seconds)` for canvas / JS-driven motion
  - optional `data-sfx="<effect>"` on an animated element: that effect plays when its
    animation starts (see bloom/sound.py for the effects)

The renderer writes the picture only; the build mixes the audio and muxes it on afterwards,
using the sound-effect cues collected here.

Frames are independent (every one is a seek), so the scenes are split into groups of whole
scenes and rendered by several workers at once, each with its own browser and encoder; the
parts are joined without re-encoding. A worker always starts on a scene's first frame, exactly
like the one-worker render, so no frame lands on a layer Chromium hasn't rasterised yet.
"""
from __future__ import annotations

import itertools
import multiprocessing
import os
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HIDE_OTHERS = "[data-scene]:not([data-on]){display:none!important}"

SHOW = """([id, dur]) => {
  document.querySelectorAll('[data-scene]').forEach(s => s.toggleAttribute('data-on', s.dataset.scene === id));
  const el = document.querySelector(`[data-scene="${CSS.escape(id)}"]`);
  if (el) el.style.setProperty('--scene-dur', dur + 's');
  return !!el;
}"""

# every data-sfx element in the shown scene, with when its own first animation starts
CUES = """() => [...document.querySelectorAll('[data-on] [data-sfx], [data-on][data-sfx]')].map(el => {
  const a = el.getAnimations()[0];
  const t = a ? a.effect.getTiming() : {};
  return {sfx: el.dataset.sfx, at: (+t.delay || 0) / 1000, dur: (+t.duration || 0) / 1000,
          steps: parseInt(getComputedStyle(el).getPropertyValue('--n')) || 0};
})"""

SEEK = """([id, t, caption]) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  const c = document.getElementById('caption');
  if (c && c.textContent !== caption) c.textContent = caption;
  if (window.bloomSeek) window.bloomSeek(id, t);
}"""


def _scene_cues(page, scene: dict) -> list[dict]:
    return [{"sfx": c["sfx"], "t": scene["start"] + c["at"], "dur": c["dur"], "steps": c["steps"]}
            for c in page.evaluate(CUES) if c["at"] < scene["dur"]]


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
           size: tuple[int, int] = (1080, 1920), fps: int = 30, workers: int | None = None) -> tuple[Path, list[dict]]:
    """timeline = [{"id", "start", "dur"}] in seconds; cues = [(start, end, text)] on the same clock.
    Writes a silent video; returns it with the page's sound-effect cues [{"t", "sfx", "dur", "steps"}]."""
    groups = _partition(timeline, fps, workers or default_workers())
    if len(groups) == 1:
        return out, _render_scenes(html, timeline, cues, out, size, fps)
    with tempfile.TemporaryDirectory(dir=Path(out).parent) as tmp:
        parts = [Path(tmp) / f"part-{k}.mp4" for k in range(len(groups))]
        with multiprocessing.get_context("spawn").Pool(len(groups)) as pool:
            found = pool.starmap(_render_scenes, [(html, g, cues, p, size, fps) for g, p in zip(groups, parts)])
        listing = Path(tmp) / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(out)], check=True)
    return out, [c for cues_k in found for c in cues_k]


def _render_scenes(html: Path, timeline: list[dict], cues: list[tuple], out: Path,
                   size: tuple[int, int], fps: int) -> list[dict]:
    """Render these scenes (on the full video's clock) to `out`; return their sound-effect cues."""
    w, h = size
    sfx: list[dict] = []
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE,
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(Path(html).resolve().as_uri())
            page.add_style_tag(content=HIDE_OTHERS)
            page.evaluate("document.fonts.ready")
            for scene in timeline:
                if not page.evaluate(SHOW, [scene["id"], scene["dur"]]):
                    raise ValueError(f'{html}: no <section data-scene="{scene["id"]}">')
                sfx += _scene_cues(page, scene)
                for f in range(round(scene["dur"] * fps)):
                    t = f / fps
                    now = scene["start"] + t
                    caption = next((c[2] for c in cues if c[0] <= now < c[1]), "")
                    page.evaluate(SEEK, [scene["id"], t, caption])
                    ffmpeg.stdin.write(page.screenshot(type="jpeg", quality=95))
            browser.close()
    finally:
        ffmpeg.stdin.close()
        if ffmpeg.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {out}")
    return sfx
