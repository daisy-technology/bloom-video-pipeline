"""Move a finished page's timings from one voice to another, so a video can be re-voiced without
re-timing scenes.html by hand.

    uv run python .claude/skills/bloom-sound/scripts/revoice.py scripts/<src> --from-voice "omnivoice:male" \
        --to-voice "omnivoice:female, young adult" [--out scripts/<copy>]

Both voices read the same script.md, so they speak the same phrases; only the pace differs. For each scene
the phrase starts and ends of both voices (bloom-story/scripts/when.py's timing) plus the scene's start and
end are matched up, and every time on the page is moved by straight-line interpolation between them: a
result that landed 0.3 s into a phrase still lands 0.3 s-worth (scaled) into it.

Rewritten (seconds only; "60%", "-1.5" and calc(var(--scene-dur) - x) are relative already and stay):
  "<scene>@<t>" in any attribute value       data-after, data-until, and a page's own data-type/run/sheet…
  data-cam-<scene>="t k …, …"                the time of each camera key
  inside <section data-scene="x">:           --at: Xs · data-t0="X" · data-at="X" · data-cam="t …"
  const DUR = { scene: seconds, … }          a page's own table of scene lengths, from the new clips

The new voice's clips must exist (--voice-only build of --out first). Writes <out>/scenes.html and prints
how far things moved per scene. --selftest checks the mapping.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from bisect import bisect_right
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bloom-story" / "scripts"))
from when import timing  # noqa: E402

NUM = r"\d+(?:\.\d+)?"


def anchors(a: dict, b: dict) -> list[tuple[float, float]]:
    """Matching moments in the two takes of one scene: its start, every phrase start and end, its end."""
    pts = [(0.0, 0.0)]
    for (s0, e0, _), (s1, e1, _) in zip(a["phrases"], b["phrases"]):
        pts += [(s0, s1), (e0, e1)]
    pts.append((a["dur"], b["dur"]))
    out = []
    for x, y in pts:  # keep it strictly increasing on both sides (phrases can touch)
        if not out or (x > out[-1][0] and y >= out[-1][1]):
            out.append((x, y))
    return out


def mapper(pts: list[tuple[float, float]]):
    xs = [p[0] for p in pts]

    def f(t: float) -> float:
        if t <= 0:
            return 0.0
        i = min(max(bisect_right(xs, t) - 1, 0), len(pts) - 2)
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        y = y0 + (y1 - y0) * (t - x0) / (x1 - x0)
        return min(max(y, 0.0), pts[-1][1])  # past the last anchor (a hold): clamp to the new scene's end
    return f


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") or "0"


def retime(html: str, maps: dict, durs: dict, moved: dict) -> str:
    def note(sid, old, new):
        moved.setdefault(sid, []).append(new - old)

    def at_token(m):  # "<scene>@<t>"
        sid, t = m.group(1), m.group(2)
        if sid not in maps:
            return m.group(0)
        new = maps[sid](float(t))
        note(sid, float(t), new)
        return f"{sid}@{fmt(new)}"

    def cam_keys(spec: str, sid: str) -> str:
        keys = []
        for key in spec.split(","):
            parts = key.strip().split()
            if parts and re.fullmatch(NUM, parts[0]):
                new = maps[sid](float(parts[0]))
                note(sid, float(parts[0]), new)
                parts[0] = fmt(new)
            keys.append(" ".join(parts))
        return ", ".join(keys)

    html = re.sub(rf"\b([a-z][\w-]*)@({NUM})(?=[\"'\s,;])", at_token, html)
    html = re.sub(r'data-cam-([a-z][\w-]*)="([^"]*)"',
                  lambda m: f'data-cam-{m.group(1)}="{cam_keys(m.group(2), m.group(1))}"' if m.group(1) in maps else m.group(0), html)

    def in_section(m):  # times inside a section count from that scene's start
        sid, body = m.group(2), m.group(3)
        if sid not in maps:
            return m.group(0)

        def sec(mm):
            new = maps[sid](float(mm.group(2)))
            note(sid, float(mm.group(2)), new)
            return f"{mm.group(1)}{fmt(new)}{mm.group(3)}"
        body = re.sub(rf"(--at:\s*)({NUM})(s)", sec, body)
        body = re.sub(rf'(data-(?:t0|at)=")({NUM})(")', sec, body)
        body = re.sub(r'data-cam="([^"]*)"', lambda mm: f'data-cam="{cam_keys(mm.group(1), sid)}"', body)
        return m.group(1) + body + m.group(4)
    html = re.sub(r'(<section\b[^>]*data-scene="([^"]+)"[^>]*>)(.*?)(</section>)', in_section, html, flags=re.S)

    def dur_table(m):
        rows = ", ".join(f"{sid}: {durs[sid]:.2f}" for sid in durs)
        return f"const DUR = {{ {rows} }};"
    return re.sub(r"const DUR = \{[^}]*\};", dur_table, html, flags=re.S)


def selftest() -> None:
    a = {"dur": 5.0, "phrases": [(0.35, 2.0, "x"), (2.0, 4.1, "y")]}
    b = {"dur": 6.0, "phrases": [(0.35, 2.6, "x"), (2.6, 5.1, "y")]}
    same = mapper(anchors(a, a))
    assert all(abs(same(t) - t) < 1e-9 for t in (0, .35, 1.2, 2, 4.1, 4.9, 5))
    f = mapper(anchors(a, b))
    assert f(0.35) == 0.35 and abs(f(2.0) - 2.6) < 1e-9 and abs(f(4.1) - 5.1) < 1e-9 and f(5.0) == 6.0
    assert abs(f(1.175) - 1.475) < 1e-9  # halfway through phrase one stays halfway
    assert f(9) == 6.0 and f(-1) == 0.0  # clamped to the scene
    page = ('<div data-after="s@2" data-cam-s="0 1 #a, 4.1 1.2 #b, 100% 1 #c"></div>'
            '<section data-scene="s"><i style="--at: 2s"></i><i style="--at: calc(var(--scene-dur) - .5s)"></i></section>'
            '<script>const DUR = { s: 5.00 };</script>')
    out = retime(page, {"s": f}, {"s": 6.0}, {})
    assert 's@2.6' in out and 'data-cam-s="0 1 #a, 5.1 1.2 #b, 100% 1 #c"' in out, out
    assert '--at: 2.6s' in out and 'calc(var(--scene-dur) - .5s)' in out and 'const DUR = { s: 6.00 };' in out, out
    print("revoice selftest: ok")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path, nargs="?")
    ap.add_argument("--from-voice")
    ap.add_argument("--to-voice")
    ap.add_argument("--out", type=Path, help="the copy to write (default: the project itself)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    out = a.out or a.project
    if out != a.project:  # the copy gets everything but the built output; the voice cache is shared
        for name in ("script.md", "media", "fonts", "icons", "lexicon.tsv"):
            src, dst = a.project / name, out / name
            if src.exists() and not dst.exists():
                (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
    old = {s["id"]: s for s in timing(a.project, a.from_voice)}
    new = {s["id"]: s for s in timing(out, a.to_voice)}
    lacking = [sid for sid, s in {**old, **new}.items() if s.get("missing")]
    if lacking:
        print(f"revoice: no clips yet for {', '.join(sorted(set(lacking)))}; make them first "
              f"(python -m bloom build <project> --voice ... --voice-only)", file=sys.stderr)
        return 1
    maps = {sid: mapper(anchors(old[sid], new[sid])) for sid in old}
    moved: dict = {}
    html = retime((a.project / "scenes.html").read_text(encoding="utf-8"), maps, {sid: new[sid]["dur"] for sid in old}, moved)
    (out / "scenes.html").write_text(html, encoding="utf-8")
    for sid in old:
        ds = moved.get(sid, [])
        span = f"{len(ds)} times moved {min(ds):+.2f}…{max(ds):+.2f} s" if ds else "nothing timed in seconds"
        print(f"{sid:<10} {old[sid]['dur']:5.2f}s → {new[sid]['dur']:5.2f}s  {span}")
    print(f"revoice: wrote {out / 'scenes.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
