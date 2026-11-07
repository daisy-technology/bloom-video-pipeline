"""Voice a video that already has captions: speak each caption in sync with the picture.

  bloom dub video.mp4 --srt captions.srt [--chapters chapters.json] [--lexicon words.tsv] [--voice omnivoice:@me]

Made for screen-recording exports with captions.srt and chapters.json next to the MP4, and works
for any video with an .srt. Each caption is spoken when it appears. A line may run on into the next
caption's time but never past its chapter; a chapter whose speech still doesn't fit is sped up a
little (pitch kept), and past MAX_SPEEDUP the run warns that its captions need shortening.
By default (hold) the voice keeps its own pace instead and the picture waits for it: the frame before a
caption gives way is held until its line is done (`--no-hold` speeds the voice up as before). A chapter
with no captions (a title card) speaks its title. The lexicons (bloom/lexicon.py: the global one plus
--lexicon) turn what a caption shows into what the voice should say ("API" -> "เอพีไอ"); numbers follow
thainum (baht and satang, codes digit by digit). Afterwards Whisper checks every line and
<name>.review.html lists the ones that may be wrong, with the commands that fix them (bloom/review.py).
`--retake 12,17` draws those lines again; the takes are kept in <name>.takes.json for later runs.
`--audition 4,5` voices several takes of those lines, each exactly as the video will use it, writes
<name>.audition.html to pick from by ear, and stops there; `--use-take 4=3,5=2` keeps the picks and
re-mixes the video once.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import asr, lexicon, mix, review, sound, voice

LEAD, GAP, TAIL = 0.15, 0.25, 0.35  # seconds: after a caption appears, between lines, before a chapter ends
MAX_LAG = 1.0                       # a line may run this far into the next caption before it is spoken faster
MAX_SPEEDUP = 1.35                  # faster than this sounds rushed: shorten the caption instead
CUT_GUARD = 0.5                     # hold a chapter's end this far before the cut, clear of any fade-out
ENCODERS = ([["-c:v", "h264_videotoolbox", "-q:v", "70"]] if sys.platform == "darwin" else
            [["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"]]) + \
           [["-c:v", "libx264", "-preset", "veryfast", "-crf", "16"]]  # the held picture: tried in order


@dataclass
class Line:
    shown: str
    spoken: str
    cue: float      # when its caption appears
    chapter: int
    dur: float = 0.0
    start: float = 0.0
    tempo: float = 1.0
    wav: Path | None = None


def read_srt(path: Path) -> list[tuple[float, float, str]]:
    """Cues as (start, end, text); one caption split across back-to-back cues comes back as one."""
    def sec(ts: str) -> float:
        h, m, s = ts.strip().replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8-sig").strip()):
        rows = block.splitlines()
        i = next((k for k, r in enumerate(rows) if "-->" in r), None)
        if i is None:
            continue
        a, b = (sec(x) for x in rows[i].split("-->"))
        text = " ".join(r.strip() for r in rows[i + 1:] if r.strip())
        if cues and cues[-1][2] == text and abs(cues[-1][1] - a) < 0.05:
            cues[-1] = (cues[-1][0], b, text)
        elif text:
            cues.append((a, b, text))
    return cues


def plan(cues, chapters: list[dict], pairs: list[tuple[str, str]]) -> list[Line]:
    lines = []
    for k, ch in enumerate(chapters):
        own = [c for c in cues if ch["start"] - 0.05 <= c[0] < ch["end"] - 0.05]
        if not own and ch.get("title"):  # a title card: say its title
            title = re.sub(r"^\d+\s*·\s*", "", ch["title"].replace("\n", " "))
            own = [(ch["start"], ch["end"], title)]
        lines += [Line(text, lexicon.apply(text, pairs), a, k) for a, _, text in own]
    return lines


def place(lines: list[Line], chapters: list[dict], total: float) -> list[str]:
    """Keep every line with its caption: start it when its caption appears (or right after the line
    before), and when it would run more than MAX_LAG into the next caption, or past its chapter, speak
    it faster, up to MAX_SPEEDUP. A line that still runs late makes the next one start late, and that
    one then catches up, so the voice never drifts further and further behind the picture."""
    warnings, t = [], 0.0
    for k, ch in enumerate(chapters):
        mine = [ln for ln in lines if ln.chapter == k]
        limit = min(ch["end"], total) - TAIL
        for i, ln in enumerate(mine):
            ln.start = max(ln.cue + LEAD, t + GAP if t else 0.0)
            nxt = mine[i + 1] if i + 1 < len(mine) else None
            end_by = min(nxt.cue + LEAD + MAX_LAG - GAP, limit) if nxt else limit
            room = end_by - ln.start
            ln.tempo = 1.0 if ln.dur <= room else (MAX_SPEEDUP if room <= 0 else min(MAX_SPEEDUP, ln.dur / room))
            t = ln.start + ln.dur / ln.tempo
        if mine and t - limit > 0.02:
            warnings.append(f"chapter {k + 1} ends {t - limit:.1f} s late even at {MAX_SPEEDUP:.2f}x: shorten its captions")
    return warnings


def hold(lines: list[Line], chapters: list[dict], total: float, fps: float) -> list[tuple[float, float]]:
    """Every line at its own pace; the picture waits. When a line would still be speaking as its caption
    gives way (or its chapter ends), the frame just before that moment is held, in whole frames, until the
    line is done. Returns the holds as (source seconds, seconds held); line starts are in held-video time."""
    holds, shift, t = [], 0.0, 0.0
    for k, ch in enumerate(chapters):
        mine = [ln for ln in lines if ln.chapter == k]
        end = min(ch["end"], total)
        for i, ln in enumerate(mine):
            ln.tempo = 1.0
            ln.start = max(ln.cue + shift + LEAD, t + GAP if t else 0.0)
            t = ln.start + ln.dur
            nxt = mine[i + 1] if i + 1 < len(mine) else None
            at, room = (nxt.cue - 1 / fps, nxt.cue + LEAD - GAP) if nxt else (end - CUT_GUARD, end - TAIL)
            late = math.ceil((t - room - shift) * fps - 1e-6) / fps
            if late > 0:
                holds.append((max(at, ln.cue), late))
                shift += late
    return holds


def held(video: Path, holds: list[tuple[float, float]], fps: float, out: Path) -> Path:
    """The picture with each hold inserted: one linear chain of single-frame loops (nothing buffered)."""
    chain, added = [], 0
    for at, secs in holds:
        n = round(secs * fps)
        chain.append(f"loop=loop={n}:size=1:start={round(at * fps) + added}")
        added += n
    # -reinit_filter 0 keeps one filter graph for the whole video. A video joined from separately encoded
    # parts can change its colour tags midway, and ffmpeg rebuilds the graph there by default, which restarts
    # the loops' frame count (every later hold lands late) and setpts's N (as many frames as came before
    # the change are dropped as already past). Measured on a 398 s video: 147 frames lost, holds 4.9 s late
    base = ["ffmpeg", "-v", "error", "-y", "-reinit_filter", "0", "-i", str(video), "-an",
            "-vf", ",".join([*chain, "setpts=N/FRAME_RATE/TB"])]
    # the GPU's own video encoder when there is one (a separate chip: it leaves the CPU, and the CUDA memory
    # the voice needs, alone, and is several times faster); x264 on the CPU otherwise
    for codec in ENCODERS:
        if subprocess.run([*base, *codec, "-pix_fmt", "yuv420p", str(out)], capture_output=True).returncode == 0:
            # a lost frame shortens the picture, and the voice that runs past its end is cut off
            if (got := _frames(out)) != (want := _frames(video) + added):
                raise RuntimeError(f"the held picture of {video} has {got} frames, not {want}")
            return out
    raise RuntimeError(f"ffmpeg could not render the held picture of {video}")


def _frames(video: Path) -> int:
    return int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                               "stream=nb_read_packets", "-of", "csv=p=0", str(video)],
                              capture_output=True, text=True, check=True).stdout.strip())


def _fps(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout.strip()
    a, _, b = r.partition("/")
    return float(a) / float(b or 1)


def _fit(ln: Line, take: int) -> float | None:
    """The length a line is voiced to. Take 0 with room to spare speaks at its own pace; any other take,
    and a line that must catch up, is voiced to its planned length. The timing is planned on take 0
    alone, so a take changes how a line sounds, never where it sits: the take picked by ear is the
    clip the video gets."""
    return round(ln.dur / ln.tempo, 2) if take or ln.tempo > 1.001 else None


def dub(video: Path, srt: Path, chapters_json: Path | None, lexicon_files: list[Path] | None, spec: str | None,
        music: str, mood: str, sfx: bool, out: Path | None, dry_run: bool = False,
        retake: str | None = None, check: bool = True, flag_at: float = review.FLAG_AT,
        audition: str | None = None, audition_takes: int = 4, use_take: str | None = None, hold_picture: bool = True,
        voice_only: bool = False) -> Path | None:
    total = voice.duration(video)
    cues = read_srt(srt)
    chapters = json.loads(Path(chapters_json).read_text(encoding="utf-8"))["chapters"] if chapters_json else \
        [{"start": 0.0, "end": total, "title": ""}]
    lines = plan(cues, chapters, lexicon.load(*(lexicon_files or [])))
    out = out or video.with_name(f"{video.stem}-voice.mp4")
    takes = review.update_takes(out.with_suffix(".takes.json"), retake, use_take)
    line_takes = [takes.get(str(n), 0) for n in range(1, len(lines) + 1)]
    work = out.parent / ".bloom" / hashlib.sha1(str(video.resolve()).encode()).hexdigest()[:10]
    work.mkdir(parents=True, exist_ok=True)
    (work.parent / ".gitignore").write_text("*\n")

    bloom = f"uv run --project {shlex.quote(str(Path(__file__).resolve().parent.parent))} bloom"
    again = " ".join([bloom, "dub", shlex.quote(str(video)), "--srt", shlex.quote(str(srt))]
                     + (["--chapters", shlex.quote(str(chapters_json))] if chapters_json else [])
                     + [x for f in (lexicon_files or []) for x in ("--lexicon", shlex.quote(str(f)))]
                     + (["--voice", spec] if spec else []) + ["--music", shlex.quote(music), "--mood", mood]
                     + ([] if sfx else ["--no-sfx"]) + ([] if hold_picture else ["--no-hold"]) + ["--out", shlex.quote(str(out))])
    if dry_run:  # what will be said, chapter by chapter, before spending minutes on synthesis
        for ln in lines:
            print(f"  {ln.chapter + 1:>2} {ln.cue:6.1f}s  {ln.spoken}")
        return None
    todo = [ln.spoken for ln in lines if not voice.cached(ln.spoken, work / "voice", spec)]
    print("  voice: %s:%s" % voice.resolve(spec))
    print(f"  {len(lines)} lines in {len(chapters)} chapters; {len(todo)} to synthesize, "
          f"about {voice.fmt_seconds(voice.estimate(todo, spec))}")
    t0 = time.time()
    wavs = voice.synth_many([ln.spoken for ln in lines], work / "voice", spec,  # take 0: what the timing is planned on
                            progress=lambda done, n: print(f"  voice {done}/{n} lines, "
                                                           f"{voice.fmt_seconds(time.time() - t0)} so far", flush=True))
    for ln, wav in zip(lines, wavs):
        ln.wav, ln.dur = wav, voice.duration(wav)
    fps = _fps(video)
    holds = hold(lines, chapters, total, fps) if hold_picture else []
    for w in ([] if hold_picture else place(lines, chapters, total)):
        print(f"  ! {w}")
    if audition:  # takes of these lines voiced exactly as the video will use them, to pick by ear
        entries = []
        for n in (int(x) for x in audition.split(",") if x.strip()):
            if not 1 <= n <= len(lines):
                raise SystemExit(f"--audition: there is no line {n} (lines 1-{len(lines)})")
            ln, ks = lines[n - 1], sorted({*range(audition_takes), line_takes[n - 1]})
            print(f"  auditioning line {n}: takes {', '.join(str(k + 1) for k in ks)}…", flush=True)
            wavs = voice.synth_many([ln.spoken] * len(ks), work / "voice", spec, fits=[_fit(ln, k) for k in ks], takes=ks)
            entries.append({"n": n, "shown": ln.shown, "spoken": ln.spoken, "tempo": ln.tempo, "current": line_takes[n - 1],
                            "takes": list(zip(ks, wavs))})
        hints = iter(review.heard([w for e in entries for _, w in e["takes"]], work / "heard.json")) if asr.available() else None
        for e in entries:  # Whisper's reading of each take: a hint beside your ears
            e["takes"] = [(k, w, next(hints) if hints else "") for k, w in e["takes"]]
        print(f"  pick by ear: {review.audition_page(entries, out.with_suffix('.audition.html'), '%s:%s' % voice.resolve(spec), again + ' --use-take ')}")
        if not (use_take or retake):  # a round of takes only: the video is voiced and mixed once, with the picks
            print(f"  done in {voice.fmt_seconds(time.time() - t0)}; pick, then add --use-take N=K to re-mix")
            return None
    redo = [(i, ln) for i, ln in enumerate(lines) if _fit(ln, line_takes[i])]
    if redo:  # the voice paces itself to the planned length: natural, where a time-stretch sounds processed
        print(f"  {len(redo)} lines voiced to fit their time (faster to keep up, or another take)…", flush=True)
        wavs = voice.synth_many([ln.spoken for _, ln in redo], work / "voice", spec,
                                fits=[_fit(ln, line_takes[i]) for i, ln in redo], takes=[line_takes[i] for i, _ in redo])
        for (_, ln), wav in zip(redo, wavs):
            ln.wav = wav
    if voice_only:  # every clip is made: the picture, mix and check need no GPU, so another run can finish later
        print(f"  voice ready in {voice.fmt_seconds(time.time() - t0)}", flush=True)
        return None
    clips = [(ln.wav, ln.start) for ln in lines]
    picture = video
    if holds:  # the picture waits for the voice: chapters, music and effects move with it
        print(f"  holding the picture {len(holds)} times, {sum(s for _, s in holds):.1f} s in all…", flush=True)
        picture = held(video, holds, fps, work / "picture.mp4")
        later = lambda s: s + sum(d for at, d in holds if at < s)
        chapters = [{**ch, "start": later(ch["start"]), "end": later(ch["end"])} for ch in chapters]
        total += sum(s for _, s in holds)

    timeline = [{"start": ch["start"], "dur": ch["end"] - ch["start"], "mood": mood if k == 0 else None}
                for k, ch in enumerate(chapters)]
    bed = sound.write_wav(work / "music.wav", sound.music(timeline, total)) if music == "auto" else \
        (None if music == "none" else Path(music))
    fx = sound.write_wav(work / "sfx.wav", sound.place([{"sfx": "whoosh", "t": ch["start"] - 0.3}
                                                        for ch in chapters[1:]], total)) if sfx else None
    mix.mux(picture, mix.master(clips, total, work / "mix.wav", bed, fx), out)

    rows = [{"n": n, "start": ln.start, "shown": ln.shown, "spoken": ln.spoken, "wav": ln.wav, "take": k,
             "heard": "", "score": 0.0, "flag": False} for n, (ln, k) in enumerate(zip(lines, line_takes), 1)]
    if check and asr.available():
        print("  checking every line with Whisper…", flush=True)
        review.check(rows, work / "heard.json", flag_at)
        page = review.page(rows, out.with_suffix(".review.html"), out, out.stem, "%s:%s" % voice.resolve(spec),
                           again.replace("{", "{{").replace("}", "}}") + " --retake {n}")
        review.summary(rows, page)
    with out.with_suffix(".speech.tsv").open("w", encoding="utf-8") as f:  # what was said, line by line
        f.write("n\tstart\ttempo\ttake\tshown\tspoken\theard\tscore\tflag\n")
        for r, ln in zip(rows, lines):
            f.write(f"{r['n']}\t{ln.start:.2f}\t{ln.tempo:.2f}\t{r['take']}\t{ln.shown}\t{ln.spoken}\t"
                    f"{r['heard']}\t{r['score']:.3f}\t{'yes' if r['flag'] else ''}\n")
    squeezed = sorted({ln.chapter + 1 for ln in lines if ln.tempo > 1.001})
    print(f"  chapters sped up: {squeezed or 'none'}")
    print(f"  done in {voice.fmt_seconds(time.time() - t0)} -> {out}")
    return out
