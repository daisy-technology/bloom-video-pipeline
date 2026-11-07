"""bloom batch FILE: dub several videos, voicing the next one while the last one finishes.

FILE has one video per line: the arguments `bloom dub` takes, with paths relative to FILE (# starts a comment).

    intro/export.mp4 --srt intro/captions.srt --chapters intro/chapters.json --voice omnivoice:@me --out voiced/intro.mp4
    "set up/export.mp4" --srt "set up/captions.srt" --voice omnivoice:@me --out voiced/setup.mp4

One process voices every video in turn, so the voice model loads once. As each video's voice is ready, that
video is finished (picture, mix, Whisper check) while the next one is voiced, so the GPU and the CPU work at
the same time. With --voice-on NAME the voicing runs on that computer and the finishing here; with --on NAME
both run there (bloom/remote.py).
"""
from __future__ import annotations

import os
import queue
import shlex
import subprocess
import sys
import threading
from pathlib import Path

from . import dub
from .remote import STATEFUL, _fetch, _job, _rewrite, _run, _send, _voice, _whole, get, stop_there


def batch(file: Path, on: str | None = None, voice_on: str | None = None) -> int:
    from . import __main__ as cli

    file = Path(file).resolve()
    os.chdir(file.parent)  # the paths in the file are relative to it
    rows = [ln for ln in file.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    argvs = [["dub", *shlex.split(ln)] for ln in rows]
    jobs = [cli.parser().parse_args(argv) for argv in argvs]  # every line is checked before any work starts
    outs = [dub.paths(a.video, a.out)[0] for a in jobs]
    name = on or voice_on
    r = get(name) if name else None
    where = f" --on {name}" if on else f" --voice-on {name}" if voice_on else ""
    agains = [dub.rerun(a.video, a.srt, a.chapters, a.lexicon, a.voice, a.music, a.mood, a.sfx, a.hold, out) + where
              for a, out in zip(jobs, outs)]
    # the finish leaves out what voicing applied already: retakes and picks would otherwise count twice
    plain = [_rewrite(argv, {}, ("--on", "--voice-on", "--voice-only", *STATEFUL)) for argv in argvs]
    ready: queue.Queue = queue.Queue()
    sent: list[str] = []  # jobs started there, stopped on Ctrl-C (it reaches only this thread)

    def voices() -> None:
        try:
            if r:  # one job there for all the videos, reporting each as its voice is ready
                files, job = {}, None
                for a, argv, again in zip(jobs, argvs, agains):
                    f, j, _ = _job(a, argv, r, True, again)
                    files.update(f)
                    if job is None:
                        job = j
                    else:
                        job["argvs"] += j["argvs"]
                        job["home"].update(j["home"])
                        job["absent"] += j["absent"]
                sent.append(_send(r, files, job, "voice: "))
                _run(r, "run", sent[-1], "voice: ", ready.put)
            else:
                for i, (argv, out) in enumerate(zip(argvs, outs)):
                    print(f"voice: {out.stem}", flush=True)
                    code = 0
                    try:
                        cli.main(argv + ["--voice-only"])
                    except SystemExit as e:
                        code = e.code if isinstance(e.code, int) else 1
                    ready.put({"index": i, "code": code})
        finally:
            ready.put(None)

    threading.Thread(target=voices, daemon=True).start()
    done, failed = [], []
    try:
        while (res := _next(ready)) is not None:
            i = res["index"]
            a, label = jobs[i], f"[{outs[i].stem}] "
            ok = not res["code"]
            if ok and getattr(a, "audition", None) and not (a.use_take or a.retake):  # an audition page is the result
                if r:
                    _fetch(r, res["files"], _voice, label)
            elif ok and on:
                _fetch(r, res["files"], lambda rel: rel.endswith(".takes.json"), label)  # picks in step before the finish sends
                f, j, _ = _job(a, plain[i], r, False, agains[i])
                results = _run(r, "run", _send(r, f, j, label), label)
                ok = bool(results) and not results[-1]["code"]
                if ok:
                    _fetch(r, results[-1]["files"], _whole, label)
            elif ok:
                if voice_on:
                    _fetch(r, res["files"], _voice, label)
                ok = _finish(plain[i] + ["--again", agains[i]], label) == 0
            (done if ok else failed).append(outs[i].name)
    except KeyboardInterrupt:
        for job_name in sent:
            stop_there(r, job_name, "voice: ")
        raise
    missing = len(jobs) - len(done) - len(failed)  # the voicing stopped early
    print(f"batch: {len(done)} of {len(jobs)} done" + (f"; failed: {', '.join(failed)}" if failed else "")
          + (f"; {missing} never voiced" if missing else ""))
    return 0 if len(done) == len(jobs) else 1


def _next(ready: queue.Queue):
    """The next voiced video, waiting in short steps: a plain get() can't be interrupted by Ctrl-C on Windows."""
    while True:
        try:
            return ready.get(timeout=1)
        except queue.Empty:
            pass


def _finish(argv: list[str], label: str) -> int:
    """One video's picture, mix and check, in its own process so its lines can carry its name."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parent.parent),
                                                        os.environ.get("PYTHONPATH", "")])}
    p = subprocess.Popen([sys.executable, "-u", "-X", "utf8", "-m", "bloom", *argv], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, env=env)
    for line in p.stdout:
        sys.stdout.write(label + line)
        sys.stdout.flush()
    return p.wait()
