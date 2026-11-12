"""Preview a Bloom project's scenes and catch the mistakes that render silently.

    uv run python .claude/skills/bloom-character/scripts/peek.py scripts/<project> [--at 1.5] [--size 1080x1920]

Run from the Bloom repo root (it drives the page with bloom.render's own SHOW/SEEK, so the
frames match a real build). Writes <project>/.bloom/peek/<scene>.png and sheet.png (every
scene side by side), prints a report and exits 1 if any check fails. Needs no voice, so it
takes seconds instead of the minutes a full `bloom build` spends synthesizing.

Checks:
  scenes     every `## id` in script.md has a <section data-scene="id">
  fonts      every @font-face loaded; the caption's first font family is one of them
  shorthand  every `animation:` declaration is valid CSS (an invalid one, e.g. two timing
             functions like `steps(4) ... linear`, is dropped by the browser without a word)
  keyframes  every animation name used has an @keyframes rule
  reverse    no steps() animation runs in reverse (a pose swap built that way blanks on one frame)
  frame      every [data-character] element of the shown scene lies inside the frame
             (scenery that drifts off on purpose, like clouds, is not marked)
  sounds     every data-sfx names known effects with a valid moment (hit@end, zip@.2), and the
             report lists where each one lands, assuming a 6 s scene, to check against the voice
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path.cwd()))
from bloom.render import CUES, HIDE_OTHERS, SEEK, SHOW, cue_events  # noqa: E402

PROBE = r"""() => {
  const styles = [...document.querySelectorAll('style')].map(s => s.textContent).join('\n')
    + '\n' + [...document.querySelectorAll('[style]')].map(e => e.getAttribute('style')).join(';\n');
  const decls = [...styles.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/(?:^|[;{\s])animation\s*:\s*([^;}]+)/g)].map(m => m[1].trim());
  const bad = decls.filter(v => !CSS.supports('animation', v));
  const names = new Set(), defined = new Set();
  for (const sheet of document.styleSheets) for (const r of sheet.cssRules) {
    if (r.type === CSSRule.KEYFRAMES_RULE) defined.add(r.name);
    if (r.style && r.style.animationName) r.style.animationName.split(',').forEach(n => names.add(n.trim()));
  }
  document.querySelectorAll('[style]').forEach(e => e.style.animationName && e.style.animationName.split(',').forEach(n => names.add(n.trim())));
  const missing = [...names].filter(n => n && n !== 'none' && !defined.has(n));
  const faces = [...document.fonts].map(f => ({family: f.family.replace(/"/g, ''), weight: f.weight, status: f.status}));
  const cap = document.getElementById('caption');
  const capFamily = getComputedStyle(cap || document.body).fontFamily.split(',')[0].replace(/["']/g, '').trim();
  return {bad, missing, faces, capFamily, scenes: [...document.querySelectorAll('[data-scene]')].map(s => s.dataset.scene)};
}"""

# per shown scene: hidden scenes are display:none, so their animations don't exist yet
REVERSED = """() => [...new Set(document.getAnimations().filter(a => /reverse/.test(a.effect.getTiming().direction)
    && a.effect.getKeyframes().some(k => /^steps/.test(k.easing))).map(a => a.animationName))]"""

BOUNDS = """([w, h]) => [...document.querySelectorAll('[data-on] [data-character]')].map(e => {
  const r = e.getBoundingClientRect();
  return {character: e.dataset.character || e.dataset.sprite || e.tagName, left: Math.round(r.left), top: Math.round(r.top),
          right: Math.round(r.right), bottom: Math.round(r.bottom),
          inside: r.left >= -1 && r.top >= -1 && r.right <= w + 1 && r.bottom <= h + 1};
})"""


def script_ids(md: Path) -> list[str]:
    return re.findall(r"^##\s+([^\s+~]+)", md.read_text(encoding="utf-8"), re.M) if md.exists() else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--at", type=float, default=1.5, help="seconds into each scene to capture")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--out", type=Path, help="default: <project>/.bloom/peek")
    a = ap.parse_args()
    w, h = map(int, a.size.split("x"))
    html = a.project / "scenes.html"
    out = a.out or a.project / ".bloom" / "peek"
    out.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(html.resolve().as_uri())
        page.add_style_tag(content=HIDE_OTHERS)
        page.evaluate("document.fonts.ready")
        info = page.evaluate(PROBE)
        report.update(info)

        ids = script_ids(a.project / "script.md")
        for sid in ids:
            if sid not in info["scenes"]:
                problems.append(f'scenes: script.md has "## {sid}" but scenes.html has no <section data-scene="{sid}">')
        for v in info["bad"]:
            problems.append(f"shorthand: invalid, so the browser dropped it: animation: {v}")
        for n in info["missing"]:
            problems.append(f"keyframes: animation {n!r} has no @keyframes rule")
        for f in info["faces"]:
            if f["status"] == "error":
                problems.append(f"fonts: {f['family']} {f['weight']} failed to load (check the url() path)")
            elif f["status"] != "loaded":
                problems.append(f"fonts: {f['family']} {f['weight']} is {f['status']}: nothing used it at load, so "
                                "early captions fall back to another font; add document.fonts.forEach(f => f.load())")
        if info["capFamily"] not in {f["family"] for f in info["faces"] if f["status"] == "loaded"}:
            problems.append(f"fonts: captions use {info['capFamily']!r}, which no loaded @font-face provides")

        shots, report["bounds"], report["sounds"] = [], {}, {}
        for sid in ids or info["scenes"]:
            if not page.evaluate(SHOW, [sid, 6]):
                continue
            try:
                report["sounds"][sid] = [f"{e['sfx']} @{e['t']:.2f}s" for c in page.evaluate(CUES) for e in cue_events(c, 0.0, 6)]
            except ValueError as e:
                problems.append(f"sounds: scene {sid}: {e}")
            page.evaluate(SEEK, [sid, a.at, "ตัวอย่างคำบรรยาย Sample caption"])
            for n in page.evaluate(REVERSED):
                problems.append(f"reverse: {n!r} in scene {sid} runs steps() in reverse; at the halfway frame neither "
                                "pose of a swap shows. Give the second pose its own mirror-image keyframes")
            bounds = page.evaluate(BOUNDS, [w, h])
            report["bounds"][sid] = bounds
            for b in bounds:
                if not b["inside"]:
                    problems.append(f"frame: {b['character']} in scene {sid} spills out of the {w}x{h} frame: {b}")
            shot = out / f"{sid}.png"
            page.screenshot(path=str(shot))
            shots.append(shot)
        problems += [f"script: {e}" for e in errors]
        browser.close()

    if shots:
        inputs = sum((["-i", str(s)] for s in shots), [])
        stack = "".join(f"[{k}]" for k in range(len(shots))) + (f"hstack={len(shots)}," if len(shots) > 1 else "")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"{stack}scale=-2:900",
                        str(out / "sheet.png")], check=True)
    report["problems"] = problems
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"sheet: {out / 'sheet.png'}")
    print(f"fonts: {', '.join(f'{f['family']} {f['weight']} {f['status']}' for f in info['faces']) or 'none'}")
    for sid, cues in report["sounds"].items():
        print(f"sounds {sid}: {', '.join(cues) or 'none'}")
    print("\n".join(problems) if problems else "ok: no problems found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
