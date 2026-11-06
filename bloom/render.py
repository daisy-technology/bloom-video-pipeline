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
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HIDE_OTHERS = "[data-scene]:not([data-on]){display:none!important}"

SHOW = """([id, dur]) => {
  document.querySelectorAll('[data-scene]').forEach(s => s.toggleAttribute('data-on', s.dataset.scene === id));
  const el = document.querySelector(`[data-scene="${CSS.escape(id)}"]`);
  if (el) el.style.setProperty('--scene-dur', dur + 's');
  return !!el;
}"""

SEEK = """([id, t, caption]) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  const c = document.getElementById('caption');
  if (c && c.textContent !== caption) c.textContent = caption;
  if (window.bloomSeek) window.bloomSeek(id, t);
}"""


def render(html: Path, timeline: list[dict], cues: list[tuple], audio: Path, out: Path,
           size: tuple[int, int] = (1080, 1920), fps: int = 30) -> Path:
    """timeline = [{"id", "start", "dur"}] in seconds; cues = [(start, end, text)] on the same clock."""
    w, h = size
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(fps), "-i", "-",
         "-i", str(audio),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
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
    return out
