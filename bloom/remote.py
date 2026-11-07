"""Another computer for the heavy work: `--on NAME` runs a whole dub or build there, `--voice-on NAME` only
its voice (the picture, mix and Whisper check then run here, which pays when this computer encodes video
in hardware and the other has the GPU).

    bloom remote add gpu-box me@10.0.0.5 --python C:/Users/me/bloom/.venv/Scripts/python.exe --path C:/Users/me/tools/bin
    bloom remote check gpu-box

The other computer needs OpenSSH with a key login and a Bloom checkout with its environment (uv sync, plus
the CUDA build of torch on an NVIDIA card). Bloom's own code travels with every job, so both sides always
run the same Bloom: the checkout there only supplies Python and its packages.

Each local file a job needs lies there at <root>/<its absolute path> (a drive letter becomes a folder; the
root is bloom-jobs/<user> in the home folder there). Files keep their places relative to each other, so the
links in review pages work once the pages come back, and a job's clips wait there for its next run. Your
voice profile, global lexicon and voice prompts go to <root>/.home, the job's BLOOM_HOME.

A job takes four connections: a stat (what is there already), an sftp put (only what changed, by size and
modification time, which put -p keeps), the run (its output streams back, and its last line lists what the
job wrote) and an sftp get (only what changed). The shell there sees one command line without quotes inside
it; argv, settings and texts travel in a JSON file that run.py reads with python -X utf8.
"""
from __future__ import annotations

import contextlib
import getpass
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
import uuid
from pathlib import Path, PurePath

from . import asr, dub, lexicon, review, voice

# what changes how the voice sounds, all of it in the clip key: set there exactly as here, unset when unset
# here. API keys and other secrets never travel
SOUND = ("BLOOM_VOICE", "BLOOM_OV_INSTRUCT", "BLOOM_OV_STEPS", "BLOOM_OV_SPEED", "BLOOM_OV_SEED")
# applied by the run there; the run here that finishes a --voice-on job must not apply them a second time
STATEFUL = ("--retake", "--use-take", "--audition", "--takes-per")
RESULT = "bloom-result: "
# Windows and macOS start a worker process (the picture renders in several) by running the main script again,
# so the job runs only under the __main__ guard; the workers still need the path to import bloom
RUN_PY = """import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
if __name__ == "__main__":
    from bloom.remote import serve
    raise SystemExit(serve(sys.argv[1:]))
"""
# the stat runs before Bloom's code is there, so it is a one-liner; inside its double quotes it avoids
# what cmd or sh would read: no " % $ ` \ !
STAT = ("import sys,json,os;print(json.dumps({p:[os.stat(p).st_size,int(os.stat(p).st_mtime)] "
        "if os.path.isfile(p) else None for p in json.load(sys.stdin)}))")


# --- the list of computers: ~/.bloom/remotes.json --------------------------------------------------------

def _config() -> Path:
    return voice.home() / "remotes.json"


def _all() -> dict:
    p = _config()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save(remotes: dict) -> None:
    p = _config()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(remotes, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def get(name: str) -> dict:
    remotes = _all()
    if name not in remotes:
        known = f" (known: {', '.join(remotes)})" if remotes else ""
        raise SystemExit(f"no remote {name!r}{known}: add it with `bloom remote add {name} user@host --python …`")
    return {"name": name, **remotes[name]}


def add(name: str, ssh: str, python: str, identity: str | None = None, path: list[str] | None = None,
        root: str | None = None) -> None:
    root = (root or "bloom-jobs/" + re.sub(r"[^A-Za-z0-9._-]", "_", getpass.getuser())).rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*", root) or ".." in root.split("/"):
        raise SystemExit(f"--root {root!r}: use a plain folder under the home folder there, like bloom-jobs/me")
    if '"' in python or "%" in python:
        raise SystemExit(f"--python {python!r}: a path without quotes or %")
    remotes = _all()
    remotes[name] = {"ssh": ssh, "python": python, "identity": identity, "path": list(path or []), "root": root}
    _save(remotes)
    print(f"{name}: {ssh}, jobs in {root} there   ({_config()})")


def remove(name: str) -> bool:
    remotes = _all()
    if remotes.pop(name, None) is None:
        return False
    _save(remotes)
    return True


def listing() -> None:
    remotes = _all()
    for name, r in remotes.items():
        print(f"  {name:<12} {r['ssh']:<28} {r['python']}")
    print(f"{len(remotes)} in {_config()}" if remotes else "no remotes yet: bloom remote add NAME user@host --python …")


# --- paths: where a local file lies there ----------------------------------------------------------------

def _rel(p: PurePath) -> str:
    """An absolute path as it lies under the root there: /Users/me/a.mp4 -> Users/me/a.mp4, C:\\x\\a.mp4 -> C/x/a.mp4."""
    head, *rest = p.parts
    head = head.strip("/\\").rstrip(":")
    return "/".join(([head] if head else []) + rest)


def _mirror(p: Path) -> str:
    return _rel(Path(p).resolve())


def _back(rel: str, windows: bool = os.name == "nt") -> Path:
    """Where a path under the root there lies here: the inverse of _mirror."""
    if windows:
        drive, _, rest = rel.partition("/")
        return Path(f"{drive}:/{rest}")
    return Path("/" + rel)


def _rewrite(argv: list[str], paths: dict[str, str], drop: tuple[str, ...]) -> list[str]:
    """argv with each path argument swapped for its place there, and the `drop` options (with their values) left out."""
    swap = lambda v: paths.get(str(Path(v)), v) if v else v  # noqa: E731
    out, it = [], iter(argv)
    for tok in it:
        flag, eq, val = tok.partition("=")
        if flag in drop:
            if not eq:
                next(it, None)
            continue
        out.append(f"{flag}={swap(val)}" if eq and flag.startswith("--") else swap(tok))
    return out


# --- ssh and sftp ------------------------------------------------------------------------------------------

def _opts(r: dict) -> list[str]:
    o = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30"]  # never asks for a password
    return o + (["-i", str(Path(r["identity"]).expanduser())] if r.get("identity") else [])


def _ssh(r: dict, *words: str) -> list[str]:
    return ["ssh", *_opts(r), r["ssh"], f'"{r["python"]}" ' + " ".join(words)]


def _why(stderr: str) -> str:
    """What ssh said, and what to do about the usual failures."""
    said = " / ".join(stderr.strip().splitlines()[-2:]) or "no output"
    if "Host key verification failed" in stderr:
        said += " (connect once with plain ssh to accept its host key)"
    elif "Permission denied" in stderr:
        said += " (Bloom needs a key login: ssh-copy-id, or --identity)"
    return said


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sftp(r: dict, lines: list[str]) -> None:
    p = subprocess.run(["sftp", *_opts(r), "-b", "-", r["ssh"]], input="\n".join(lines) + "\n",
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise SystemExit(f"{r['name']}: sftp failed: {_why(p.stderr)}")


def _puts(files: list[tuple[str, Path]]) -> list[str]:
    """sftp lines that put each file at its path there, making its folders first (an existing one is fine)."""
    folders = []
    for there, _ in files:
        parts = there.split("/")[:-1]
        folders += ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    return ([f"-mkdir {_q(d)}" for d in dict.fromkeys(folders)]
            + [f"put -p {_q(here.as_posix())} {_q(there)}" for there, here in files])


def _changed(files: dict[str, Path], there: dict) -> list[tuple[str, Path]]:
    """The files whose size or modification time differ from what is there."""
    out = []
    for name, p in files.items():
        st = p.stat()
        if there.get(name) != [st.st_size, int(st.st_mtime)]:
            out.append((name, p))
    return out


CLIP = re.compile(r"/\.bloom/(?:[0-9a-f]{10}/)?voice/[^/]+$")  # dub's clips, then build's


def _to_pull(results: list, keep, root: str) -> list[tuple[str, Path]]:
    out = []
    for rel, size, mtime in results:
        here = _back(rel)
        if not keep(rel):
            continue
        # a clip's name says what it holds, so one here is that clip already (maybe one you've listened to): kept
        if here.is_file() and (CLIP.search(rel) or (here.stat().st_size == size and int(here.stat().st_mtime) == mtime)):
            continue
        out.append((f"{root}/{rel}", here))
    return out


def _mb(files) -> str:
    return f"{len(files)} file{'s' * (len(files) != 1)}, {sum(p.stat().st_size for _, p in files) / 2**20:.1f} MB"


def _send(r: dict, files: dict[str, Path], job: dict, label: str = "") -> str:
    """Put what changed, plus the job file; returns the job file's path under the root there."""
    files = {**{f"{r['root']}/.code/bloom/{p.name}": p for p in Path(__file__).parent.glob("*.py")},
             f"{r['root']}/.code/run.py": _run_py(), **files}
    p = subprocess.run(_ssh(r, "-X utf8 -c", f'"{STAT}"'), input=json.dumps(list(files)),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise SystemExit(f"{r['name']}: {_why(p.stderr)}")
    todo = _changed(files, json.loads(p.stdout.strip().splitlines()[-1]))
    if todo:
        print(f"{label}→ {r['name']}: {_mb(todo)}", flush=True)
    name = f".jobs/{uuid.uuid4().hex[:12]}.json"
    with tempfile.TemporaryDirectory() as tmp:
        jf = Path(tmp) / "job.json"
        jf.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        _sftp(r, _puts([*todo, (f"{r['root']}/{name}", jf)]))
    return name


def _run_py() -> Path:
    """The bootstrap, kept in one place here so its modification time (and so its upload) only changes with it."""
    p = voice.SPEED_FILE.parent / "remote" / "run.py"
    if not p.exists() or p.read_text(encoding="utf-8") != RUN_PY:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(RUN_PY, encoding="utf-8")
    return p


def _run(r: dict, verb: str, job_name: str, label: str = "", each=None) -> list[dict]:
    """Run a job there with its output streaming here (prefixed by `label`). Returns what each of its runs
    reported, in order, and hands each to `each` the moment it arrives; a failed run has a non-zero "code"."""
    p = subprocess.Popen(_ssh(r, "-u -X utf8", f"{r['root']}/.code/run.py", verb, job_name), stdout=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", bufsize=1)
    results = []
    try:
        for line in p.stdout:
            if line.startswith(RESULT):
                results.append(json.loads(line[len(RESULT):]))
                if each:
                    each(results[-1])
            else:
                sys.stdout.write(label + line)
                sys.stdout.flush()
        code = p.wait()
    except KeyboardInterrupt:
        stop_there(r, job_name, label)
        raise
    finally:
        if p.poll() is None:
            p.terminate()
            p.wait()
    if code == 255:
        raise SystemExit(f"{r['name']}: ssh failed (see above)")
    return results


def stop_there(r: dict, job_name: str, label: str = "") -> None:
    """Stop a job on the other computer. Losing the connection isn't enough: Windows keeps the job running,
    and on a small GPU an orphaned job makes the next one run out of memory."""
    print(f"\n{label}stopping the job on {r['name']}…", flush=True)
    try:
        subprocess.run(_ssh(r, "-X utf8", f"{r['root']}/.code/run.py", "stop", job_name), capture_output=True, timeout=60)
    except (subprocess.SubprocessError, OSError):
        print(f"{label}{r['name']} didn't answer: the job there may still be running", flush=True)


def _fetch(r: dict, results: list, keep, label: str = "") -> None:
    todo = _to_pull(results, keep, r["root"])
    if not todo:
        return
    for _, here in todo:
        here.parent.mkdir(parents=True, exist_ok=True)
    _sftp(r, [f"get -p {_q(there)} {_q(here.as_posix())}" for there, here in todo])
    print(f"{label}← {r['name']}: {_mb([(None, here) for _, here in todo])}", flush=True)


# --- a dub or build there ------------------------------------------------------------------------------------

def _job(a, argv: list[str], r: dict, voice_only: bool, again: str) -> tuple[dict, dict, Path]:
    """What a dub or build needs there: the files to send, the job file, and the output video here."""
    if a.cmd == "dub":
        out, work = dub.paths(a.video, a.out)
        inputs = [a.video, a.srt, a.chapters, *(a.lexicon or [])]
        state = out.with_suffix(".takes.json")
        named = [a.video, a.srt, a.chapters, *(a.lexicon or []), a.out]
    else:
        out, work = a.out, a.project / ".bloom"
        inputs = [f for f in a.project.rglob("*") if f.is_file() and ".bloom" not in f.relative_to(a.project).parts]
        state = a.project / ".bloom" / "takes.json"
        named = [a.project, a.out]
    # a designed voice (no profile) is one take of it, made by the first computer that needed it: the same timbre there
    inputs += sorted((work / "voice").glob("omnivoice-anchor-*.wav"))
    if a.music not in ("auto", "none"):
        inputs.append(Path(a.music))
        named.append(Path(a.music))
    if missing := [str(p) for p in inputs if p and not Path(p).is_file()]:
        raise SystemExit(f"bloom {a.cmd}: not found: {', '.join(missing)}")
    root = r["root"]
    files = {f"{root}/{_mirror(p)}": Path(p) for p in inputs if p}
    if state.exists():
        files[f"{root}/{_mirror(state)}"] = state
    home = {"lexicon.tsv": lexicon.global_path().read_text(encoding="utf-8") if lexicon.global_path().exists() else None}
    provider, variant = voice.resolve(a.voice)
    if provider == "omnivoice" and variant.startswith("@"):
        ref, text = voice.profile(variant[1:])
        files[f"{root}/.home/voices/{variant[1:]}/ref.wav"] = ref
        home[f"voices/{variant[1:]}/ref.txt"] = text
    files.update({f"{root}/.home/prompts/{p.name}": p for p in voice.PROMPTS.glob("*.pt")})
    remote_argv = _rewrite(argv, {str(Path(p)): _mirror(p) for p in named if p}, ("--on", "--voice-on")) \
        + ["--out", _mirror(out)] + (["--voice-only"] if voice_only else []) + ["--again", again]
    job = {"argvs": [remote_argv], "env": {k: os.environ.get(k) for k in SOUND}, "cli": review.cli(),
           "path": r.get("path", []), "home": home, "absent": [] if state.exists() else [_mirror(state)]}
    return files, job, out


def _whole(rel: str) -> bool:  # --on brings back everything a job wrote but its big intermediates
    return not re.search(r"/\.bloom/(?:[^/]+/)?(?:picture\.mp4|music\.wav|sfx\.wav)$", rel)


def _voice(rel: str) -> bool:  # --voice-on brings back the clips and the picks (and an audition page)
    return bool(CLIP.search(rel) or re.search(r"\.takes\.json$|/\.bloom/takes\.json$|\.audition\.html$", rel))


def offload(a, argv: list[str]) -> None:
    """Run the dub or build parsed from `argv` on a remote: all of it (--on), or its voice and then the rest here."""
    from . import __main__ as cli

    name, whole = a.on or a.voice_on, bool(a.on)
    r = get(name)
    where = f"--on {name}" if whole else f"--voice-on {name}"
    if a.cmd == "dub":
        out = dub.paths(a.video, a.out)[0]
        again = dub.rerun(a.video, a.srt, a.chapters, a.lexicon, a.voice, a.music, a.mood, a.sfx, a.hold, out)
    else:
        again = cli.rerun(a.project, a.out, a.voice, a.music, a.sfx, cli.size(a.size), a.fps)
    again += f" {where}"
    voice_only = a.voice_only or not whole
    files, job, out = _job(a, argv, r, voice_only, again)
    results = _run(r, "run", _send(r, files, job))
    if not results or results[-1]["code"]:
        raise SystemExit(f"bloom {a.cmd}: the run on {name} failed")
    _fetch(r, results[-1]["files"], _whole if whole else _voice)
    audition_only = bool(getattr(a, "audition", None)) and not (getattr(a, "use_take", None) or a.retake)
    if whole or a.voice_only or audition_only:
        print(f"  results here: {out}")
        return
    print("  the voice is ready; the picture, mix and check run here", flush=True)
    cli.main(_rewrite(argv, {}, ("--voice-on", *STATEFUL)) + ["--again", again])


# --- what it has: bloom remote check -------------------------------------------------------------------------

def check(name: str) -> bool:
    r = get(name)
    results = _run(r, "check", _send(r, {}, {"path": r.get("path", [])}))
    if not results:
        raise SystemExit(f"{name}: the check could not run there")
    f = results[-1]["facts"]
    print(f"{name} ({r['ssh']}): {f['system']}, Python {f['python']}")
    rows = [
        ("GPU", "ok" if f.get("gpu") else "warn",
         f.get("gpu") or "none: the voice would run on the CPU there, slowly (NVIDIA: install torch's CUDA build)"),
        # the voice model peaks at about 2.1 GB plus CUDA's own: with less free it spills into system memory,
        # and a browser open on a 4 GB card made it about 6 s a line instead of 3.5
        *([("GPU memory", "warn", f"{f['gpu_free_gb']} GB free: close programs that hold it there (browsers, editors)")]
          if f.get("gpu_free_gb", 99) < 3 else []),
        ("OmniVoice", "ok" if f.get("omnivoice") else "fail",
         (f"{f['omnivoice']}, weights " + ("cached" if f.get("weights") else "download on the first run (2.4 GB)"))
         if f.get("omnivoice") else "missing: run uv sync in the Bloom checkout there"),
        *[(t, "ok" if f.get(t) else "fail", f.get(t) or "not found: add its folder with --path") for t in ("ffmpeg", "ffprobe")],
        ("whisper-cli", "ok", f["whisper-cli"]) if f.get("whisper-cli") and f.get("whisper_model") else
        ("whisper-cli", "warn", "no Whisper check there (--voice-on checks here instead): install whisper.cpp "
                                "or add its folder with --path, and fetch its model once"),
        ("Playwright", "ok" if f.get("playwright") else "warn",
         "for bloom build" if f.get("playwright") else "bloom build --on needs it: uv run playwright install chromium there"),
        ("disk", "ok" if f["free_gb"] > 10 else "warn", f"{f['free_gb']} GB free"),
    ]
    for what, state, note in rows:
        print(f"  {state:<5} {what:<12} {note}")
    return all(state != "fail" for _, state, _ in rows)


# --- the other side: run.py calls serve() ----------------------------------------------------------------------

def serve(argv: list[str], root: Path | None = None) -> int:
    """run.py's entry point there: `run`, `check` or `stop` a job, named by its job file's path under the root."""
    verb, name = argv
    root = root or Path(__file__).resolve().parents[2]  # <root>/.code/bloom/remote.py
    job_file = root / name
    pid_file = job_file.with_suffix(".pid")
    if verb == "stop":
        _stop(pid_file)
        return 0
    job = json.loads(job_file.read_text(encoding="utf-8"))
    job_file.unlink()
    os.environ["PATH"] = os.pathsep.join([*job.get("path", []), os.environ.get("PATH", "")])
    if verb == "check":
        print(RESULT + json.dumps({"facts": _facts(root)}), flush=True)
        return 0
    pid_file.write_text(str(os.getpid()))  # so a Ctrl-C on the computer that sent the job can stop it
    try:
        _settle(root, job)
        from . import __main__ as cli

        failed = 0
        for i, argv in enumerate(job["argvs"]):  # one process for them all: the voice model loads once
            code = 0
            try:
                cli.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
                if isinstance(e.code, str):
                    print(e.code, file=sys.stderr)
            except Exception:  # the next video still gets its turn
                traceback.print_exc()
                code = 1
            failed += bool(code)
            print(RESULT + json.dumps({"index": i, "code": code, "files": _outputs(root, argv)}), flush=True)
    finally:
        pid_file.unlink(missing_ok=True)
    return 1 if failed else 0


def _stop(pid_file: Path) -> None:
    """End a running job and all it started: ffmpeg, whisper-cli, render workers. A job that ended already is fine."""
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text())
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)  # sshd gives each session its own process group
    pid_file.unlink(missing_ok=True)


def _settle(root: Path, job: dict) -> None:
    """The job's world: its folder, sound settings, BLOOM_HOME with the profile and lexicons, voice prompts."""
    os.chdir(root)
    for k, v in job["env"].items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    home = root / ".home"
    os.environ["BLOOM_HOME"] = str(home)
    os.environ.pop("BLOOM_VOICES", None)
    os.environ["BLOOM_CLI"] = job["cli"]  # the pages show the command to run here, not there
    for rel, text in job["home"].items():
        f = home / rel
        if text is None:
            f.unlink(missing_ok=True)
        else:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
    for rel in job["absent"]:  # takes.json deleted here: the picks reset there too
        (root / rel).unlink(missing_ok=True)
    voice.PROMPTS.mkdir(parents=True, exist_ok=True)
    for pt in (home / "prompts").glob("*.pt"):  # made here already: no tokenizing burst on a small GPU there
        if not (voice.PROMPTS / pt.name).exists():
            shutil.copy2(pt, voice.PROMPTS / pt.name)


def _outputs(root: Path, argv: list[str]) -> list:
    """What a dub or build wrote, as [path under the root, size, modification time]."""
    from . import __main__ as cli

    a = cli.parser().parse_args(argv)
    if a.cmd == "dub":
        out, work = dub.paths(a.video, a.out)
        files = [out] + [out.with_suffix(s) for s in (".review.html", ".speech.tsv", ".takes.json", ".audition.html")]
        folders = [work]
    else:
        name = a.project.resolve().name
        files = [a.out / f"{name}{s}" for s in (".mp4", ".srt", ".review.html")]
        folders = [a.project / ".bloom"]
    found = [f for f in files if f.is_file()] + [f for d in folders if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file()]
    return [[Path(os.path.relpath(f.resolve(), root.resolve())).as_posix(), f.stat().st_size, int(f.stat().st_mtime)]
            for f in found]


def _facts(root: Path) -> dict:
    f = {"python": platform.python_version(), "system": platform.platform(terse=True)}
    try:
        import torch

        f["torch"] = torch.__version__
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            f["gpu"] = f"{torch.cuda.get_device_name(0)}, {total / 2**30:.1f} GB"
            f["gpu_free_gb"] = round(free / 2**30, 1)
        elif torch.backends.mps.is_available():
            f["gpu"] = "Apple GPU (MPS)"
    except ImportError:
        pass
    if importlib.util.find_spec("omnivoice"):
        import omnivoice
        from huggingface_hub import try_to_load_from_cache

        f["omnivoice"] = omnivoice.__version__
        f["weights"] = isinstance(try_to_load_from_cache("k2-fsa/OmniVoice", "config.json"), str)
    f.update({t: shutil.which(t) for t in ("ffmpeg", "ffprobe", "whisper-cli")})
    f["whisper_model"] = asr.MODEL.exists()
    f["playwright"] = importlib.util.find_spec("playwright") is not None
    f["free_gb"] = round(shutil.disk_usage(root).free / 2**30, 1)
    return f
