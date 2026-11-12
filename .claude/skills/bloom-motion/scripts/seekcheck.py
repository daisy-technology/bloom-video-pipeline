"""Check that a Bloom page's motion is seek-safe, and print where each scene moves.

    uv run python .claude/skills/bloom-motion/scripts/seekcheck.py scripts/<project> --voice "<voice>"

Bloom renders by seeking: every frame is drawn from (scene, time) alone, and the scenes are split across
several workers that each start mid-video. So a frame must look the same whichever frame came before it.
This draws every sampled frame twice: once in order, once on a fresh page with the scenes in reverse
(last scene first, like a worker that starts late), and compares the pictures. A frame that differs depends
on something other than its time: Math.random or Date in bloomSeek, state carried between bloomSeek calls,
SVG <animate> (runs on the wall clock), a <video> element, requestAnimationFrame or timers, or a CSS
transition. The page's script is scanned for those to name the likely cause.

It also prints a motion strip per scene, one character per --step: how much of the picture changed since
the previous sample (' ' still, '.' under 1 % of the frame: an ambient loop, ':' some, '#' a lot), and the
longest quiet stretch (' ' and '.' in a row, leaving out the closing second). Over about 3 s while the voice
talks is dead air: only a loop is moving. '#' everywhere is noise with no beat.

Writes the first differing frame pair of each scene to <project>/.bloom/seekcheck/; exits 1 if any frame
after a scene's first differs (a first frame alone differing is a warning: see below).
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bloom-visual" / "scripts"))
from bloom.render import CUES, HIDE_OTHERS, SEEK, SHOW, prepare  # noqa: E402
from frames import durations  # noqa: E402

HAZARDS = {  # what in the page makes a frame depend on more than its time
    r"<animate|<animateTransform|<animateMotion|<set\b": "SVG <animate> runs on the wall clock: in bloomSeek call svg.pauseAnimations(); svg.setCurrentTime(t), or use CSS",
    r"<video\b": "<video> seeks asynchronously; render its frames to images, or set currentTime and accept a possibly stale frame",
    r"Math\.random": "Math.random gives a new value every frame: use a seeded hash of (index, seed)",
    r"Date\.now|performance\.now|new Date\(": "wall-clock time: use the t that bloomSeek receives",
    r"requestAnimationFrame|setTimeout|setInterval": "timers and rAF run on the wall clock: draw everything inside bloomSeek(id, t)",
}
TRANSITIONS = "() => document.getAnimations().filter(a => a instanceof CSSTransition).map(a => a.effect.target.tagName.toLowerCase() + (a.effect.target.className ? '.' + String(a.effect.target.className).split(' ')[0] : '') + ' ' + a.transitionProperty)"
STRIP = " .:#"


def grab(page) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(page.screenshot(type="png"))).convert("L"), dtype=np.int16)


def changed(a: np.ndarray, b: np.ndarray) -> tuple[float, tuple | None]:
    """Share of pixels that differ visibly, and their bounding box (x, y, w, h)."""
    d = np.abs(a - b) > 24
    if not d.any():
        return 0.0, None
    ys, xs = np.nonzero(d)
    return d.mean(), (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--voice", help="the --voice the build uses, for the real scene lengths")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--brand", default="daisy", help="the brand mark Bloom adds when it renders (daisy | daisy-end | none)")
    ap.add_argument("--step", type=float, default=0.25, help="seconds between sampled frames")
    ap.add_argument("--scene", action="append", help="only these scenes (repeatable)")
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    dur = durations(a.project, a.voice, a.fps)
    starts, clock = {}, 0.0
    for sid, d in dur.items():
        starts[sid], clock = clock, clock + d
    todo = [s for s in dur if not a.scene or s in a.scene]
    times = {s: sorted({round(k * a.step, 3) for k in range(int(dur[s] / a.step) + 1)} | {round(dur[s] - 1 / a.fps, 3)}) for s in todo}
    out = a.project / ".bloom" / "seekcheck"
    out.mkdir(parents=True, exist_ok=True)

    def seek(page, sid, t):
        page.evaluate(SEEK, [sid, t, "", [1, 0.5], starts[sid] + t])

    def open_page(p):
        page = p.chromium.launch().new_page(viewport={"width": W, "height": H})
        prepare(page, a.project / "scenes.html", (W, H), a.brand, sum(dur.values()))
        page.screenshot()  # warm-up: a fresh browser's first paint can differ by a few antialiased pixels
        return page

    forward: dict[tuple, np.ndarray] = {}
    bad, transitions = [], set()
    with sync_playwright() as p:
        page = open_page(p)
        for sid in todo:
            if not page.evaluate(SHOW, [sid, dur[sid]]):  # then CUES, exactly as bloom.render does before a scene's frames
                raise SystemExit(f"seekcheck: script.md has scene {sid!r} but scenes.html has no section for it")
            page.evaluate(CUES)
            strip, prev = "", None
            for t in times[sid]:
                seek(page, sid, t)
                forward[sid, t] = img = grab(page)
                transitions.update(page.evaluate(TRANSITIONS))
                if prev is not None:
                    share = changed(prev, img)[0]
                    strip += STRIP[0 if share == 0 else 1 if share < .01 else 2 if share < .08 else 3]
                prev = img
            quiet = max((len(m) for m in re.findall(r"[ .]+", strip[:-4] if len(strip) > 8 else strip)), default=0) * a.step
            print(f"{sid:<10} {dur[sid]:5.2f}s |{strip}|  longest quiet {quiet:.2f}s")
        # a fresh page that takes the scenes last first, like a worker that starts mid-video. Within a
        # scene it goes forward from the first frame, as every worker does (a layer seen for the first
        # time mid-scene may not be rasterised yet, which the renderer never asks for)
        page = open_page(p)
        for sid in reversed(todo):
            page.evaluate(SHOW, [sid, dur[sid]])
            page.evaluate(CUES)
            first = None
            for t in times[sid]:
                seek(page, sid, t)
                img = grab(page)
                share, box = changed(forward[sid, t], img)
                if share > 0.0005:
                    bad.append((sid, t, share, box))
                    if first is None:
                        first = t
                        Image.fromarray(np.hstack([forward[sid, t], img]).astype(np.uint8)).resize((W, H // 2)).save(out / f"{sid}-{t:05.2f}.png")

    html = (a.project / "scenes.html").read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->|/\*.*?\*/|(?<![:\"'])//[^\n]*", "", html, flags=re.S)  # comments that mention a hazard aren't one
    causes = [msg for pat, msg in HAZARDS.items() if re.search(pat, html)
              and not (msg.startswith("SVG") and "setCurrentTime" in html)]  # the motion kit already syncs SMIL
    if transitions:
        causes.append(f"CSS transitions only start on a style change and aren't keyframed to the scene: {', '.join(sorted(transitions))}; use @keyframes")
    # a scene's very first frame can differ by a few pixels however the page is written: Chromium starts
    # the newly shown scene's animations on it (seen on pages with no JS at all). Warn, don't fail.
    first_only = [b for b in bad if b[1] == 0]
    bad = [b for b in bad if b[1] > 0]
    for sid, _, share, _ in first_only:
        print(f"warn  {sid:<10} @0.00s     first frame differs by {share:.1%}: Chromium starting the scene's animations, "
              "usually invisible; a real fault shows on later frames too")
    for sid in todo:  # one line per scene with differing frames, in scene order
        ts = sorted(b for b in bad if b[0] == sid)
        if ts:
            worst = max(ts, key=lambda b: b[2])
            x, y, w, h = worst[3]
            print(f"error {sid:<10} @{ts[0][1]:.2f}–{ts[-1][1]:.2f}s  {len(ts)} frames differ when reached out of order "
                  f"(worst {worst[2]:.1%} of the frame, around x{x} y{y} {w}×{h})")
    if bad:
        print("likely causes:" if causes else "likely cause: state kept between bloomSeek calls (a variable that accumulates, a DOM change that isn't reset)")
        for c in causes:
            print(f"  - {c}")
        print(f"{len(bad)} frames differ · pairs (in order | out of order) in {out}")
    else:
        print(f"seek-safe: {sum(len(v) for v in times.values())} frames match in and out of order")
        for c in causes:  # present but harmless so far, e.g. a timer that only builds the DOM once
            print(f"  note: {c}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
