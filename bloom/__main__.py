"""bloom build <project>: script.md + scenes.html -> voice -> picture -> music + effects -> MP4."""
from __future__ import annotations

import argparse
import shlex
import sys
import time
from pathlib import Path

from . import asr, batch, clone, compose, dub, lexicon, lipsync, mix, remote, render, review, script, sound, subs, voice
from .compose.timing import PAD_IN, PAD_OUT  # breathing room around each scene's voice, seconds (one source)
WHOOSH_LEAD = 0.3             # the transition whoosh starts this early, so it peaks on the cut
PACE = (10.0, 19.0)           # Thai characters a second outside this read as dragging or rushed (natural: ~15)


def lufs_arg(text: str) -> float | None:
    """--lufs -14 masters to -14 LUFS; --lufs off leaves the voice at the mix level."""
    return None if text.lower() in ("off", "none") else float(text)


def pace(text: str, seconds: float, performed: bool = False) -> str:
    """Characters a second, flagged when a line is rushed or drags: the number, not a feeling.
    A line with delivery tags (`performed`) also spends time laughing or sighing, so it isn't flagged."""
    cps = len(text.replace(" ", "")) / max(seconds, 0.1)
    if performed:
        return f"{cps:4.1f} ch/s (with its tags)"
    return f"{cps:4.1f} ch/s" + (" (rushed)" if cps > PACE[1] else " (drags)" if cps < PACE[0] else "")


def rerun(project: Path, out_dir: Path, spec: str | None, music: str, sfx: bool, size: tuple[int, int], fps: int,
          lufs: float | None = mix.DELIVERY_LUFS, mood: str | None = None) -> str:
    """This build's command line. The review page adds --retake to it."""
    return " ".join([review.cli(), "build", shlex.quote(str(project)), "--out", shlex.quote(str(out_dir))]
                    + (["--voice", shlex.quote(spec)] if spec else []) + ["--music", shlex.quote(music)]
                    + ([] if sfx else ["--no-sfx"]) + ["--size", f"{size[0]}x{size[1]}", "--fps", str(fps)]
                    + ([] if lufs == mix.DELIVERY_LUFS else ["--lufs", "off" if lufs is None else f"{lufs:g}"])
                    + (["--mood", mood] if mood else []))


def size(text: str) -> tuple[int, int]:
    w, h = (int(x) for x in text.lower().split("x"))
    return w, h


def build(project: Path, out_dir: Path, spec: str | None, music: str, sfx: bool, size: tuple[int, int], fps: int,
          workers: int | None = None, retake: str | None = None, check: bool = True,
          flag_at: float = review.FLAG_AT, voice_only: bool = False, again: str | None = None,
          lufs: float | None = mix.DELIVERY_LUFS, mood: str | None = None, brand: str = "daisy",
          deband: bool = True) -> Path | None:
    scenes = script.parse(project / "script.md")
    if mood:  # one music style for the whole video, whatever the script's ~moods say
        for k, s in enumerate(scenes):
            s["mood"] = mood if k == 0 else None
    html = project / "scenes.html"
    spec_first = compose.has_spec(project)  # the page is generated after the voice: its beats land on the words
    if not html.exists() and not spec_first:
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
    if voice_only:  # every clip is made: a later run renders and mixes without the GPU
        print(f"  voice ready in {voice.fmt_seconds(time.time() - t0)}", flush=True)
        return None
    if spec_first:
        print(f"  page: generated from the spec -> {compose.write_page(project, spec, fps)}")
    timeline, clips, cues, start = [], [], [], 0.0
    for s, wav in zip(scenes, wavs):
        speak = voice.duration(wav)
        # whole frames: the picture is cut in frames, so the sound and the picture never drift apart
        dur = round((PAD_IN + speak + PAD_OUT + s["hold"]) * fps) / fps
        timeline.append({"id": s["id"], "start": start, "dur": dur, "mood": s["mood"]})
        clips.append((wav, start + PAD_IN))
        cues += subs.cues(s["text"], start + PAD_IN, speak)
        print(f"  voice  {s['id']:<14} {speak:5.1f}s  {pace(s['text'], speak, script.untagged(s['speech']) != s['speech'])}")
        start += dur

    out_dir.mkdir(parents=True, exist_ok=True)
    name = project.resolve().name
    subs.write_srt(cues, out_dir / f"{name}.srt")
    print(f"  {start:.1f}s total; rendering {round(start * fps)} frames…")
    mouth = lipsync.track(clips, start, fps)  # the characters' mouths follow the voice
    video, events = render.render(html, timeline, cues, work / "picture.mp4", size, fps, workers, mouth, brand, deband)

    bed = None
    if music == "auto":
        bed = sound.write_wav(work / "music.wav", sound.music(timeline, start))
    elif music != "none":
        bed = Path(music)
    fx = gain = None
    end = sound.ending(events)  # a cut@ or fade@ on the page: the music stops with the picture
    autos = []
    if sfx:
        events += [{"sfx": "whoosh", "t": s["start"] - WHOOSH_LEAD} for s in timeline[1:]]
        fx = sound.write_wav(work / "sfx.wav", sound.place(events, start))
        autos = sound.automation(events)  # the bed takes a breath before each hit and ducks under risers and stings
    # the music follows the video: a music file's level follows the scene moods and drops under the closing
    # question; a spec's music cues (drop, duck, lift, stop on a word) apply to any music
    cues_m = compose.music_cues(project, spec, {s["id"]: s["start"] for s in timeline}, fps) if spec_first else []
    if bed:
        autos += sound.follow(timeline, cues_m, by_mood=music not in ("auto", "none"))
    if bed and (autos or end):
        gain = sound.write_wav(work / "bed-gain.wav", sound.gain_curve(autos, start, end))
    audio = mix.master(clips, start, work / "mix.wav", bed, fx, gain, lufs)
    mp4 = mix.mux(video, audio, out_dir / f"{name}.mp4")
    print(f"  music: {music if music != 'auto' else 'generated'} · effects: {effects(events) if sfx else 'off'}")
    if lufs is not None:
        m, ok = mix.report(mp4, lufs)
        print(f"  loudness: {m['i']:.1f} LUFS, true peak {m['tp']:.1f} dBTP"
              + ("" if ok else f"  (off target: {lufs:g} LUFS ±1, true peak at most -1 dBTP)"))

    if check and asr.available():
        print("  checking every line with Whisper…", flush=True)
        rows = [{"n": n, "id": s["id"], "start": tl["start"] + PAD_IN, "shown": s["text"], "spoken": script.untagged(s["speech"]),
                 "wav": wav} for n, (s, tl, wav) in enumerate(zip(scenes, timeline, wavs), 1)]
        review.check(rows, work / "heard.json", flag_at)
        again = again or rerun(project, out_dir, spec, music, sfx, size, fps, lufs, mood)
        page = review.page(rows, out_dir / f"{name}.review.html", mp4, name, "%s:%s" % voice.resolve(spec),
                           again.replace("{", "{{").replace("}", "}}") + " --retake {id}")
        review.summary(rows, page)
    print(f"  done in {time.time() - t0:.0f}s -> {mp4}")
    return mp4


def effects(events: list[dict]) -> str:
    """'9 (2 hit, 3 whoosh, …)': how many effects, and which."""
    counts: dict[str, int] = {}
    events = [e for e in events if e["sfx"] not in sound.ENDINGS]
    for e in events:
        counts[e["sfx"]] = counts.get(e["sfx"], 0) + 1
    return f"{len(events)} (" + ", ".join(f"{n} {k}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1])) + ")" if events else "0"


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="bloom", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def checking(p: argparse.ArgumentParser, what: str) -> None:
        p.add_argument("--retake", metavar=what, help=f"draw these again ({what}, comma-separated); kept for later runs")
        p.add_argument("--flag-at", type=float, default=review.FLAG_AT,
                       help=f"flag lines whose Whisper error rate is above this (default {review.FLAG_AT})")
        p.add_argument("--no-check", dest="check", action="store_false", help="skip the Whisper check and review page")

    def elsewhere(p: argparse.ArgumentParser) -> None:
        g = p.add_mutually_exclusive_group()
        g.add_argument("--on", metavar="NAME", help="run all of it on another computer (bloom remote add); the results come back here")
        g.add_argument("--voice-on", metavar="NAME", help="make the voice on another computer, then finish here")
        p.add_argument("--again", help=argparse.SUPPRESS)  # a remote run's pages show the command to run here

    b = sub.add_parser("build", help="render a project folder (script.md + scenes.html)")
    b.add_argument("project", type=Path)
    b.add_argument("--out", type=Path, default=Path("output"), help="output folder (default: ./output)")
    b.add_argument("--voice", metavar="PROVIDER[:VARIANT]",
                   help="omnivoice[:instruct] (default) · elevenlabs[:model_id] · say[:voice]")
    b.add_argument("--music", default="auto", metavar="auto|none|FILE",
                   help="auto (default) generates a score that follows the scenes; or a file to duck under the voice")
    b.add_argument("--no-sfx", dest="sfx", action="store_false", help="leave out the sound effects")
    b.add_argument("--mood", choices=script.MOODS,
                   help="one generated music style for the whole video, overriding the script's ~moods "
                        "(calm, tense, bright, chip: 8-bit, playful: marimba and claps, lofi: soft keys and vinyl)")
    b.add_argument("--lufs", type=lufs_arg, default=mix.DELIVERY_LUFS, metavar="LUFS|off",
                   help=f"master the finished video to this loudness (default {mix.DELIVERY_LUFS:g}, true peak under -1 dBTP)")
    b.add_argument("--size", default="1080x1920", help="WxH, default 1080x1920 (vertical short)")
    b.add_argument("--brand", default="daisy", choices=render.BRANDS, help="daisy: a quiet mark in the corner (default) · daisy-end: the mark only in the last seconds · none")
    b.add_argument("--no-deband", dest="deband", action="store_false",
                   help="leave out the deband + dither that keeps smooth gradients from stepping into bands")
    b.add_argument("--fps", type=int, default=30)
    b.add_argument("--workers", type=int, help="parallel render workers (default: BLOOM_RENDER_WORKERS, else 3 on 7+ cores)")
    b.add_argument("--voice-only", action="store_true",
                   help="make every scene's clip and stop; a later run renders and mixes without the GPU")
    checking(b, "scene ids")
    elsewhere(b)

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
    d.add_argument("--lufs", type=lufs_arg, default=mix.DELIVERY_LUFS, metavar="LUFS|off",
                   help=f"master the finished video to this loudness (default {mix.DELIVERY_LUFS:g}, true peak under -1 dBTP)")
    d.add_argument("--out", type=Path, help="default: <video>-voice.mp4 next to the video")
    d.add_argument("--dry-run", action="store_true", help="print what will be said, synthesize nothing")
    checking(d, "line numbers")
    d.add_argument("--audition", metavar="N,N", help="voice several takes of these lines, as the video will use them, and a page to pick from; "
                        "stops there (no re-mix) unless --use-take is given")
    d.add_argument("--takes-per", type=int, default=4, help="takes per auditioned line (default 4)")
    d.add_argument("--use-take", metavar="N=K,…", help="use take K of line N (the numbers an audition page shows)")
    d.add_argument("--no-hold", dest="hold", action="store_false",
                   help="leave the picture as it is and speed late lines up (to 1.35x) instead of holding the frame until they finish")
    d.add_argument("--voice-only", action="store_true",
                   help="make every line's clip and stop; a later run finishes picture, mix and check without the GPU")
    elsewhere(d)

    bt = sub.add_parser("batch", help="dub several videos, voicing the next one while the last one finishes")
    bt.add_argument("file", type=Path, help="one video per line: the arguments of bloom dub, paths relative to the file (# comments)")
    g = bt.add_mutually_exclusive_group()
    g.add_argument("--on", metavar="NAME", help="voice and finish them on another computer")
    g.add_argument("--voice-on", metavar="NAME", help="voice them on another computer and finish them here")

    rm = sub.add_parser("remote", help="another computer for the heavy work, used with --on / --voice-on NAME")
    rms = rm.add_subparsers(dest="action", required=True)
    ra = rms.add_parser("add", help="remember a computer you can ssh into with a key, then check it")
    ra.add_argument("name")
    ra.add_argument("ssh", help="user@host, or a Host from ~/.ssh/config")
    ra.add_argument("--python", required=True,
                    help="the Python of Bloom's environment there, e.g. C:/Users/me/bloom/.venv/Scripts/python.exe")
    ra.add_argument("--identity", help="the ssh key, when ssh doesn't find it by itself")
    ra.add_argument("--path", action="append", default=[], help="a folder to put first on PATH there (ffmpeg, whisper-cli); repeat for several")
    ra.add_argument("--root", help="where jobs live there, under the home folder (default bloom-jobs/<your user name>)")
    rms.add_parser("list", help="the computers added so far")
    rr = rms.add_parser("remove", help="forget a computer (its files there stay)")
    rr.add_argument("name")
    rc = rms.add_parser("check", help="what a computer has and lacks for Bloom")
    rc.add_argument("name")

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
        p.add_argument("--shared", action="store_true",
                       help="Bloom's shared lexicon (bloom/lexicon.tsv, in the repo): a fix every machine and agent gets")

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
    gd = sub.add_parser("guard", help="check what's about to be committed against the repo's rules (the git hook runs it)")
    gd.add_argument("--all", action="store_true", help="every tracked file, not just the staged ones")
    dr = sub.add_parser("draft", help="start a video: draft.md for the person to review (spec-first Bloom)")
    dr.add_argument("project", type=Path)
    dr.add_argument("--size", default="1920x1080", help="1920x1080 (16:9) or 1080x1920 (9:16)")
    dr.add_argument("--from-spec", action="store_true", help="write the draft back from video.toon")
    sp = sub.add_parser("spec", help="turn an approved draft.md into video.toon and script.md")
    sp.add_argument("project", type=Path)
    co = sub.add_parser("compose", help="generate scenes.html from video.toon (bloom build does this itself)")
    co.add_argument("project", type=Path, nargs="?")
    co.add_argument("--catalog", action="store_true", help="list every component and verb a draft can use")
    co.add_argument("--voice", metavar="PROVIDER[:VARIANT]", help="default: the spec's voice")
    co.add_argument("--fps", type=int, default=30)
    return ap


def main(argv: list[str] | None = None) -> None:
    try:
        _main(sys.argv[1:] if argv is None else argv)
    except KeyboardInterrupt:
        raise SystemExit(130)  # Ctrl-C: stopped here, and there too when it ran on another computer


def _main(argv: list[str]) -> None:
    a = parser().parse_args(argv)
    if a.cmd in ("dub", "build") and (a.on or a.voice_on) and not getattr(a, "dry_run", False):
        remote.offload(a, argv)
        return
    if a.cmd == "dub":
        dub.dub(a.video, a.srt, a.chapters, a.lexicon, a.voice, a.music, a.mood, a.sfx, a.out, a.dry_run,
                a.retake, a.check, a.flag_at, a.audition, a.takes_per, a.use_take, a.hold, a.voice_only, a.again, a.lufs)
        return
    if a.cmd == "batch":
        raise SystemExit(batch.batch(a.file, a.on, a.voice_on))
    if a.cmd == "remote":
        if a.action == "add":
            remote.add(a.name, a.ssh, a.python, a.identity, a.path, a.root)
        if a.action in ("add", "check"):
            raise SystemExit(0 if remote.check(a.name) else 1)
        if a.action == "remove":
            raise SystemExit(0 if remote.remove(a.name) else f"bloom remote: no remote {a.name!r}")
        remote.listing()
        return
    if a.cmd == "lexicon":
        if a.shared:
            a.file = lexicon.SHARED
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
    if a.cmd == "guard":
        from .compose import guard
        problems = guard.check(a.all)
        for line in problems:
            print(f"  ✗ {line}")
        raise SystemExit(f"bloom guard: {len(problems)} problem(s); fix them before committing" if problems else 0)
    if a.cmd == "draft":
        try:
            print(f"bloom draft: {compose.new_draft(a.project, a.size, a.from_spec)}")
        except (FileExistsError, FileNotFoundError) as e:
            raise SystemExit(f"bloom draft: {e}")
        return
    if a.cmd == "spec":
        try:
            print(f"bloom spec: {compose.make_spec(a.project)} and {a.project / 'script.md'}")
        except (PermissionError, ValueError, FileNotFoundError, compose.draft.DraftError) as e:
            raise SystemExit(f"bloom spec: {e}")
        return
    if a.cmd == "compose":
        if a.catalog or a.project is None:
            print(compose.catalog())
            return
        try:
            v = (compose.spec.load(a.project) or {}).get("video", {})
            print(f"bloom compose: {compose.write_page(a.project, a.voice or v.get('voice'), a.fps)}")
        except (FileNotFoundError, ValueError) as e:
            raise SystemExit(f"bloom compose: {e}")
        return
    spec_defaults(a, argv)
    build(a.project, a.out, a.voice, a.music, a.sfx, size(a.size), a.fps, a.workers, a.retake, a.check, a.flag_at,
          a.voice_only, a.again, a.lufs, a.mood, a.brand, a.deband)


def spec_defaults(a: argparse.Namespace, argv: list[str]) -> None:
    """A project with a spec builds with the spec's voice, size and music unless the command line says otherwise."""
    v = (compose.spec.load(a.project) or {}).get("video") if compose.has_spec(a.project) else None
    if not v:
        return
    given = lambda flag: any(x == flag or x.startswith(flag + "=") for x in argv)  # noqa: E731
    if not given("--voice") and v.get("voice"):
        a.voice = v["voice"]
    if not given("--size") and v.get("size"):
        a.size = v["size"]
    if not given("--brand") and v.get("brand"):
        a.brand = v["brand"]
    music = str(v.get("music") or "")
    if not given("--music") and not given("--mood") and music:
        if music in script.MOODS:
            a.mood = music
        elif music not in ("auto", "none"):
            a.music = str(a.project / music)
        else:
            a.music = music


if __name__ == "__main__":
    main()
