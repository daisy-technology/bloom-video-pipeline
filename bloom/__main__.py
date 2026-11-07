"""bloom build <project>: script.md + scenes.html -> voice -> picture -> music + effects -> MP4."""
from __future__ import annotations

import argparse
import shlex
import time
from pathlib import Path

from . import asr, clone, dub, lexicon, mix, render, review, script, sound, subs, voice

PAD_IN, PAD_OUT = 0.35, 0.55  # breathing room around each scene's voice, seconds
WHOOSH_LEAD = 0.3             # the transition whoosh starts this early, so it peaks on the cut


def build(project: Path, out_dir: Path, spec: str | None, music: str, sfx: bool, size: tuple[int, int], fps: int,
          workers: int | None = None, retake: str | None = None, check: bool = True,
          flag_at: float = review.FLAG_AT) -> Path:
    scenes = script.parse(project / "script.md")
    html = project / "scenes.html"
    if not html.exists():
        raise FileNotFoundError(html)
    if music not in ("auto", "none") and not Path(music).is_file():
        raise FileNotFoundError(f"--music {music}: not a file (use auto, none, or a path)")
    work = project / ".bloom"
    work.mkdir(exist_ok=True)
    (work / ".gitignore").write_text("*\n")  # the cache never lands in whatever repo holds the project

    pairs = lexicon.load(project / "lexicon.tsv")  # the global lexicon, then this project's
    for s in scenes:
        s["speech"] = lexicon.apply(s["speech"], pairs)
    takes = review.update_takes(work / "takes.json", retake)
    scene_takes = [takes.get(s["id"], 0) for s in scenes]

    t0 = time.time()
    print("  voice: %s:%s" % voice.resolve(spec))
    todo = [s["speech"] for s, k in zip(scenes, scene_takes) if not voice.cached(s["speech"], work / "voice", spec, take=k)]
    if todo:
        print(f"  {len(todo)} of {len(scenes)} lines to synthesize, about {voice.fmt_seconds(voice.estimate(todo, spec))}")
    wavs = voice.synth_many([s["speech"] for s in scenes], work / "voice", spec, takes=scene_takes,
                            progress=lambda done, n: print(f"  voice {done}/{n} lines, "
                                                           f"{voice.fmt_seconds(time.time() - t0)} so far", flush=True))
    timeline, clips, cues, start = [], [], [], 0.0
    for s, wav in zip(scenes, wavs):
        speak = voice.duration(wav)
        dur = PAD_IN + speak + PAD_OUT + s["hold"]
        timeline.append({"id": s["id"], "start": start, "dur": dur, "mood": s["mood"]})
        clips.append((wav, start + PAD_IN))
        cues += subs.cues(s["text"], start + PAD_IN, speak)
        print(f"  voice  {s['id']:<14} {speak:5.1f}s")
        start += dur

    out_dir.mkdir(parents=True, exist_ok=True)
    name = project.resolve().name
    subs.write_srt(cues, out_dir / f"{name}.srt")
    print(f"  {start:.1f}s total; rendering {round(start * fps)} frames…")
    video, events = render.render(html, timeline, cues, work / "picture.mp4", size, fps, workers)

    bed = None
    if music == "auto":
        bed = sound.write_wav(work / "music.wav", sound.music(timeline, start))
    elif music != "none":
        bed = Path(music)
    fx = None
    if sfx:
        events += [{"sfx": "whoosh", "t": s["start"] - WHOOSH_LEAD} for s in timeline[1:]]
        fx = sound.write_wav(work / "sfx.wav", sound.place(events, start))
    audio = mix.master(clips, start, work / "mix.wav", bed, fx)
    mp4 = mix.mux(video, audio, out_dir / f"{name}.mp4")
    print(f"  music: {music if music != 'auto' else 'generated'} · effects: {len(events) if sfx else 'off'}")

    if check and asr.available():
        print("  checking every line with Whisper…", flush=True)
        rows = [{"n": n, "id": s["id"], "start": tl["start"] + PAD_IN, "shown": s["text"], "spoken": s["speech"],
                 "wav": wav} for n, (s, tl, wav) in enumerate(zip(scenes, timeline, wavs), 1)]
        review.check(rows, work / "heard.json", flag_at)
        bloom = f"uv run --project {shlex.quote(str(Path(__file__).resolve().parent.parent))} bloom"
        again = " ".join([bloom, "build", shlex.quote(str(project)), "--out", shlex.quote(str(out_dir))]
                         + (["--voice", spec] if spec else []) + ["--music", shlex.quote(music)]
                         + ([] if sfx else ["--no-sfx"]) + ["--size", f"{size[0]}x{size[1]}", "--fps", str(fps)])
        page = review.page(rows, out_dir / f"{name}.review.html", mp4, name, "%s:%s" % voice.resolve(spec),
                           again.replace("{", "{{").replace("}", "}}") + " --retake {id}")
        review.summary(rows, page)
    print(f"  done in {time.time() - t0:.0f}s -> {mp4}")
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(prog="bloom", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def checking(p: argparse.ArgumentParser, what: str) -> None:
        p.add_argument("--retake", metavar=what, help=f"draw these again ({what}, comma-separated); kept for later runs")
        p.add_argument("--flag-at", type=float, default=review.FLAG_AT,
                       help=f"flag lines whose Whisper error rate is above this (default {review.FLAG_AT})")
        p.add_argument("--no-check", dest="check", action="store_false", help="skip the Whisper check and review page")

    b = sub.add_parser("build", help="render a project folder (script.md + scenes.html)")
    b.add_argument("project", type=Path)
    b.add_argument("--out", type=Path, default=Path("output"), help="output folder (default: ./output)")
    b.add_argument("--voice", metavar="PROVIDER[:VARIANT]",
                   help="omnivoice[:instruct] (default) · elevenlabs[:model_id] · say[:voice]")
    b.add_argument("--music", default="auto", metavar="auto|none|FILE",
                   help="auto (default) generates a score that follows the scenes; or a file to duck under the voice")
    b.add_argument("--no-sfx", dest="sfx", action="store_false", help="leave out the sound effects")
    b.add_argument("--size", default="1080x1920", help="WxH, default 1080x1920 (vertical short)")
    b.add_argument("--fps", type=int, default=30)
    b.add_argument("--workers", type=int, help="parallel render workers (default: BLOOM_RENDER_WORKERS, else 3 on 7+ cores)")
    checking(b, "scene ids")

    d = sub.add_parser("dub", help="voice a video that already has captions (an .srt, plus chapters.json when there is one)")
    d.add_argument("video", type=Path)
    d.add_argument("--srt", type=Path, required=True, help="its captions (the studio writes out/captions.srt)")
    d.add_argument("--chapters", type=Path, help="chapters.json (studio): lines never run past a chapter; title cards get spoken")
    d.add_argument("--lexicon", type=Path, action="append",
                   help="a TSV of 'shown<TAB>spoken' (repeat for several: shared, then this video's); the global one always applies")
    d.add_argument("--voice", metavar="PROVIDER[:VARIANT]", help="e.g. omnivoice:@me for your own voice")
    d.add_argument("--music", default="auto", metavar="auto|none|FILE")
    d.add_argument("--mood", choices=script.MOODS, default="calm")
    d.add_argument("--no-sfx", dest="sfx", action="store_false", help="no whoosh on chapter changes")
    d.add_argument("--out", type=Path, help="default: <video>-voice.mp4 next to the video")
    d.add_argument("--dry-run", action="store_true", help="print what will be said, synthesize nothing")
    checking(d, "line numbers")
    d.add_argument("--audition", metavar="N,N", help="voice several takes of these lines, as the video will use them, and a page to pick from; "
                        "stops there (no re-mix) unless --use-take is given")
    d.add_argument("--takes-per", type=int, default=4, help="takes per auditioned line (default 4)")
    d.add_argument("--use-take", metavar="N=K,…", help="use take K of line N (the numbers an audition page shows)")

    lx = sub.add_parser("lexicon", help="how the voice says words, remembered for every video")
    lxs = lx.add_subparsers(dest="action", required=True)
    la = lxs.add_parser("add", help='say a word differently from now on, e.g. bloom lexicon add "พาธ" "พาด"')
    la.add_argument("shown")
    la.add_argument("spoken")
    lr = lxs.add_parser("remove", help="forget a word")
    lr.add_argument("shown")
    ll = lxs.add_parser("list", help="show the lexicon")
    for p in (la, lr, ll):
        p.add_argument("--file", type=Path, help=f"a project lexicon instead of the global {lexicon.global_path()}")

    sy = sub.add_parser("say", help="hear a line as a video would say it, to try a fix before keeping it")
    sy.add_argument("text")
    sy.add_argument("--voice", metavar="PROVIDER[:VARIANT]", help="e.g. omnivoice:@me")
    sy.add_argument("--takes", type=int, default=1, help="hear several takes (OmniVoice draws each differently)")
    sy.add_argument("--lexicon", type=Path, help="a project lexicon to apply on top of the global one")
    sy.add_argument("--no-play", dest="play", action="store_false")

    v = sub.add_parser("voice", help="your own voice: record, check and test a profile for --voice omnivoice:@name")
    vs = v.add_subparsers(dest="action", required=True)
    r = vs.add_parser("record", help="record a reference clip from the microphone")
    r.add_argument("name", help="profile name; use it as --voice omnivoice:@<name>")
    r.add_argument("--seconds", type=int, default=clone.RECORD_SECONDS, help="recording window (the read is ~15 s)")
    r.add_argument("--device", default="0", help="microphone number from `bloom voice devices` (default 0)")
    r.add_argument("--text", default=clone.SENTENCE, help="what you will read (it becomes ref.txt)")
    r.add_argument("--lexicon", type=Path, help="a project lexicon, so the words check reads terms like API your way")
    ad = vs.add_parser("add", help="use a recording made elsewhere")
    ad.add_argument("name", help="profile name; use it as --voice omnivoice:@<name>")
    ad.add_argument("recording", type=Path)
    ad.add_argument("--text", required=True, help="exactly the words spoken in the recording")
    ad.add_argument("--lexicon", type=Path, help="a project lexicon, so the words check reads terms like API your way")
    ck = vs.add_parser("check", help="check a profile against cloning best practice")
    ck.add_argument("name", help="profile name; use it as --voice omnivoice:@<name>")
    ck.add_argument("--lexicon", type=Path, help="a project lexicon, so the words check reads terms like API your way")
    t = vs.add_parser("test", help="say a test line in the cloned voice and play it")
    t.add_argument("name", help="profile name; use it as --voice omnivoice:@<name>")
    t.add_argument("--text", default=clone.TEST_LINE)
    t.add_argument("--no-play", dest="play", action="store_false")
    vs.add_parser("list", help="list voice profiles")
    vs.add_parser("devices", help="list the microphones you can record from")

    a = ap.parse_args()
    if a.cmd == "dub":
        dub.dub(a.video, a.srt, a.chapters, a.lexicon, a.voice, a.music, a.mood, a.sfx, a.out, a.dry_run,
                a.retake, a.check, a.flag_at, a.audition, a.takes_per, a.use_take)
        return
    if a.cmd == "lexicon":
        if a.action == "add":
            print(f"{a.shown} -> {a.spoken}   ({lexicon.add(a.shown, a.spoken, a.file)})")
            print("every video says it this way from its next run; only lines containing it are voiced again")
        elif a.action == "remove":
            raise SystemExit(0 if lexicon.remove(a.shown, a.file) else f"bloom lexicon: {a.shown!r} is not in it")
        else:
            entries = lexicon.read(a.file or lexicon.global_path())
            for shown, spoken in entries.items():
                print(f"  {shown}\t{spoken}")
            print(f"{len(entries)} entries in {a.file or lexicon.global_path()}")
        return
    if a.cmd == "say":
        review.say(a.text, a.voice, a.takes, a.play, a.lexicon)
        return
    if a.cmd == "voice":
        try:
            ok = {"record": lambda: clone.record(a.name, a.seconds, a.device, a.text, a.lexicon),
                  "add": lambda: clone.add(a.name, a.recording, a.text, a.lexicon),
                  "check": lambda: clone.check(a.name, a.lexicon),
                  "test": lambda: clone.test(a.name, a.text, a.play),
                  "list": clone.listing,
                  "devices": clone.devices}[a.action]()
        except (FileNotFoundError, ValueError) as e:
            raise SystemExit(f"bloom voice: {e}")
        raise SystemExit(0 if ok is not False else 1)
    w, h = (int(x) for x in a.size.lower().split("x"))
    build(a.project, a.out, a.voice, a.music, a.sfx, (w, h), a.fps, a.workers, a.retake, a.check, a.flag_at)


if __name__ == "__main__":
    main()
