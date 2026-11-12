"""The repo's rules, checked on what is about to be committed, whoever commits it (a person or any agent).

    bloom guard            the staged files (the pre-commit hook in .githooks runs this)
    bloom guard --all      every tracked file (for CI)

Blocks: audio in a project's media/ (licensed or generated: never redistributed) · generated files
(made from video.toon: edit draft.md instead) · a video.toon that isn't exactly what its approved draft
says · files over 10 MB outside docs/media (renders and caches are made again, not committed).
"""
from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from . import draft, spec

GENERATED = "generated from video.toon"
AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")
BIG = 10 * 1024 * 1024


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def _files(all_files: bool) -> list[str]:
    out = _git("ls-files", "-z") if all_files else _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [f for f in out.decode().split("\0") if f]


def _content(path: str, all_files: bool) -> bytes:
    return Path(path).read_bytes() if all_files else _git("show", f":{path}")


def check(all_files: bool = False) -> list[str]:
    problems, projects = [], set()
    for f in _files(all_files):
        p = PurePosixPath(f)
        data = _content(f, all_files)
        if p.parts[0] == "scripts" and "media" in p.parts and p.suffix.lower() in AUDIO:
            problems.append(f"{f}: audio in a project's media/ is licensed or generated; keep it out of the repo "
                            "(the spec records where it came from)")
        if p.suffix in (".html", ".md") and GENERATED.encode() in data[:2000]:
            problems.append(f"{f}: generated from video.toon; never commit or hand-edit it (edit draft.md, run bloom spec)")
        if len(data) > BIG and p.parts[0] != "docs":
            problems.append(f"{f}: {len(data) / 1e6:.0f} MB; renders and caches are made again, not committed")
        if p.name in ("draft.md", "video.toon", "video.json") and p.parts[0] == "scripts":
            projects.add(Path(*p.parts[:-1]))
    for project in sorted(projects):
        problems += _spec_matches_draft(project)
    return problems


def _spec_matches_draft(project: Path) -> list[str]:
    """video.toon is made by bloom spec from the approved draft, never written by hand."""
    has_spec = (project / "video.toon").exists() or (project / "video.json").exists()
    if not (project / "draft.md").exists():
        return [f"{project}: a spec without draft.md; the draft is what the person reviews"] if has_spec else []
    try:
        d, status = draft.read(project)
    except draft.DraftError as e:
        return [f"{project}/draft.md: {e}"]
    if not has_spec:
        return []  # a draft still in review: nothing to compare yet
    if status != "approved":
        return [f"{project}: video.toon exists but draft.md is status: {status}; a spec comes only from an approved draft"]
    if spec.load(project) != d:
        return [f"{project}: video.toon differs from the approved draft.md; run bloom spec {project} (never edit the spec by hand)"]
    return [f"{project}: {e}" for e in spec.check(d)]
