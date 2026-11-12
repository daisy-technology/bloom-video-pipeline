"""A contact sheet of a Bloom page at chosen moments, on the real scene lengths, without rendering the video.

    uv run python .claude/skills/bloom-visual/scripts/frames.py scripts/<project> --voice "<voice>" \
        hook:0.5,3.6 day:1.5,2.6,11 month:7.2,14.5

Each frame is drawn the way the renderer draws it (bloom.render's SHOW and SEEK, the mouth half open),
with the scene's real length from its voice clip (so `--scene-dur` and the props' relative times are
right), and labelled `scene @time`. Writes <project>/.bloom/frames/sheet.png and prints the sounds each
scene will play, with their times. Look at it before rendering: the result of each beat should be the
focal point at its moment (bloom-visual, section 6).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path.cwd()))
from bloom import __main__ as cli, lexicon, script, voice  # noqa: E402
from bloom.render import CUES, HIDE_OTHERS, SEEK, SHOW, cue_events, prepare  # noqa: E402


def durations(project: Path, spec: str | None, fps: int) -> dict[str, float]:
    pairs = lexicon.load(project / "lexicon.tsv")
    out = {}
    for s in script.parse(project / "script.md"):
        clip = voice._clip(lexicon.apply(s["speech"], pairs), project / ".bloom" / "voice", spec, None)[3]
        speak = voice.duration(clip) if clip.exists() else 5.0
        out[s["id"]] = round((cli.PAD_IN + speak + cli.PAD_OUT + s["hold"]) * fps) / fps
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("moments", nargs="+", help="scene:t1,t2,…  (seconds from the scene start)")
    ap.add_argument("--voice", help="the --voice the build uses, for the real scene lengths")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--brand", default="daisy", help="the brand mark Bloom adds when it renders (daisy | daisy-end | none)")
    ap.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    w, h = map(int, a.size.split("x"))
    dur = durations(a.project, a.voice, a.fps)
    starts, clock = {}, 0.0  # each scene's start on the video clock: what stays across cuts (a ticker) runs on it
    for sid, d in dur.items():
        starts[sid], clock = clock, clock + d
    out = a.project / ".bloom" / "frames"
    out.mkdir(parents=True, exist_ok=True)
    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        prepare(page, a.project / "scenes.html", (w, h), a.brand, sum(dur.values()))
        for m in a.moments:
            sid, _, times = m.partition(":")
            if not page.evaluate(SHOW, [sid, dur.get(sid, 6.0)]):
                raise SystemExit(f"frames: no scene {sid!r}")
            sounds = [f"{e['sfx']} @{e['t']:.2f}" for c in page.evaluate(CUES) for e in cue_events(c, 0.0, dur.get(sid, 6.0))]
            print(f"{sid} ({dur.get(sid, 6.0):.2f}s): {', '.join(sounds) or 'no sounds'}")
            for t in (float(x) for x in times.split(",") if x):
                page.evaluate(SEEK, [sid, t, f"{sid} @{t:.2f}s", [1, 0.5], starts.get(sid, 0.0) + t])
                f = out / f"{sid}-{t:05.2f}.png"
                page.screenshot(path=str(f))
                shots.append(f)
        browser.close()
    cols = min(a.cols, len(shots))
    rows = [shots[i:i + cols] for i in range(0, len(shots), cols)]
    inputs, chains, labels = [], [], []
    for r, row in enumerate(rows):
        row = row + [row[-1]] * (cols - len(row))  # pad the last row with its last frame
        for c, f in enumerate(row):
            k = len(inputs) // 2
            inputs += ["-i", str(f)]
            chains.append(f"[{k}]scale={480 if w > h else 270}:-1[s{k}]")  # 16:9 frames need room to read
        labels.append("".join(f"[s{r * cols + c}]" for c in range(cols)) + f"hstack={cols}[r{r}]" if cols > 1
                      else f"[s{r * cols}]null[r{r}]")
    graph = ";".join(chains + labels) + ";" + ("".join(f"[r{r}]" for r in range(len(rows))) + f"vstack={len(rows)}[o]"
                                              if len(rows) > 1 else "[r0]null[o]")
    sheet = out / "sheet.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[o]", str(sheet)], check=True)
    print(f"sheet: {sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
