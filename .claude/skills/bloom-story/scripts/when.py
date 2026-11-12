"""When each phrase is spoken, scene by scene, from the voice clips a build already made.

    uv run python .claude/skills/bloom-story/scripts/when.py scripts/<project> --voice "omnivoice:female, young adult"

Run from the Bloom repo root after the voice exists (a build, `--voice-only`, or a remote run that brought
the clips back). For every scene it prints its length and when each phrase starts and ends, in seconds
from the scene start, the clock `--at` and `data-at` use in scenes.html. Times are shared out by
the length of each phrase as spoken (digits as Thai words) inside each clip, so they are good to about half a second:
land a result a beat after its phrase starts, or in the gap after it ends.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from bloom import __main__ as cli  # noqa: E402
from bloom.compose.timing import timing  # noqa: E402,F401  (revoice.py imports it from here too)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--voice", help="the same --voice the build used")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    missing = 0
    for s in timing(a.project, a.voice, a.fps):
        if s.get("missing"):
            print(f"## {s['id']}: no voice clip yet (build it first, with the same --voice)")
            missing += 1
            continue
        print(f"## {s['id']}  scene {s['dur']:.2f}s · voice {cli.PAD_IN:.2f}–{cli.PAD_IN + s['speak']:.2f}s")
        for t0, t1, p in s["phrases"]:
            print(f"   {t0:5.2f}–{t1:5.2f}  {p}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
