"""bloom build <project>: script.md + scenes.html -> voice -> mix -> subtitles -> MP4."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import mix, render, script, subs, voice

PAD_IN, PAD_OUT = 0.35, 0.55  # breathing room around each scene's voice, seconds


def build(project: Path, out_dir: Path, spec: str | None, bed: Path | None,
          size: tuple[int, int], fps: int) -> Path:
    scenes = script.parse(project / "script.md")
    html = project / "scenes.html"
    if not html.exists():
        raise FileNotFoundError(html)
    work = project / ".bloom"
    work.mkdir(exist_ok=True)
    (work / ".gitignore").write_text("*\n")  # the cache never lands in whatever repo holds the project

    t0 = time.time()
    print("  voice: %s:%s" % voice.resolve(spec))
    timeline, clips, cues, start = [], [], [], 0.0
    for s in scenes:
        wav = voice.synth(s["speech"], work / "voice", spec)
        speak = voice.duration(wav)
        dur = PAD_IN + speak + PAD_OUT + s["hold"]
        timeline.append({"id": s["id"], "start": start, "dur": dur})
        clips.append((wav, start + PAD_IN))
        cues += subs.cues(s["text"], start + PAD_IN, speak)
        print(f"  voice  {s['id']:<14} {speak:5.1f}s")
        start += dur

    out_dir.mkdir(parents=True, exist_ok=True)
    name = project.resolve().name
    audio = mix.narration(clips, start, work / "narration.wav", bed)
    subs.write_srt(cues, out_dir / f"{name}.srt")
    print(f"  mix + subs done, {start:.1f}s total; rendering {round(start * fps)} frames…")
    mp4 = render.render(html, timeline, cues, audio, out_dir / f"{name}.mp4", size, fps)
    print(f"  done in {time.time() - t0:.0f}s -> {mp4}")
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(prog="bloom", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="render a project folder (script.md + scenes.html)")
    b.add_argument("project", type=Path)
    b.add_argument("--out", type=Path, default=Path("output"), help="output folder (default: ./output)")
    b.add_argument("--voice", metavar="PROVIDER[:VARIANT]",
                   help="omnivoice[:instruct] (default) · elevenlabs[:model_id] · say[:voice]")
    b.add_argument("--bed", type=Path, help="music or source audio to duck under the voice")
    b.add_argument("--size", default="1080x1920", help="WxH, default 1080x1920 (vertical short)")
    b.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.lower().split("x"))
    build(a.project, a.out, a.voice, a.bed, (w, h), a.fps)


if __name__ == "__main__":
    main()
