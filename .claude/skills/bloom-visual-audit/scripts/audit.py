"""Audit a Bloom page's layout and motion, frame by frame, before it is rendered.

    uv run python .claude/skills/bloom-visual-audit/scripts/audit.py scripts/<project> --voice "<voice>"

Steps through every scene on its real length (from the voice clips) the way the renderer does
(bloom.render's SHOW and SEEK), samples it every --step seconds plus consecutive frames for motion, and
reports what a viewer would see go wrong:

  frame      text or a character partly outside the 1080x1920 frame
  spill      text running out of the box it sits in (a note, a card, a bubble)
  collide    two pieces of text overlapping each other, or text under the caption
  hidden     text meant to be read, covered (even partly) by something opaque
  small      text drawn smaller than 28 px on the frame (scale included)
  safe       text in the platform's overlay zones: vertical, top 150 px and right 110 px (the app's
             header and button column); 16:9, the outer 5 % on every side (title-safe: the player's title
             overlay and progress bar)
  cut-jump   something that stays on screen across a cut (outside the sections) jumps at the cut
  teleport   something visible moving more than 250 px in one frame (a seek or a keyframe gap)

An element or one of its ancestors can opt out of a check with data-audit="frame collide ..." (for
example a ticker that runs off the edge on purpose: data-audit="frame"). Writes
<project>/.bloom/audit.json and prints the findings grouped, most severe first; exits 1 if any
error-level finding remains.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path.cwd()))
from bloom import __main__ as cli, lexicon, script, voice  # noqa: E402
from bloom.render import HIDE_OTHERS, SEEK, SHOW, prepare  # noqa: E402

SEVERITY = {"frame": "error", "spill": "error", "collide": "error", "hidden": "error", "cut-jump": "error", "teleport": "warn",
            "small": "warn", "safe": "warn"}

PROBE = r"""([W, H]) => {
  const on = document.querySelector('[data-on]');
  const skip = (el, check) => { for (let e = el; e && e !== document; e = e.parentElement)
      if ((e.dataset && (e.dataset.audit || '').split(/\s+/).includes(check))) return true; return false; };
  const alpha = el => { let a = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; a *= +cs.opacity; } return a; };
  const name = el => {
    const t = (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 28);
    const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (cls ? '.' + cls : '') + (t ? ` "${t}"` : '');
  };
  const path = el => { const p = []; for (let e = el; e && e.nodeType === 1 && e !== document.body; e = e.parentElement)
      p.unshift(e.tagName + ':' + [...(e.parentElement ? e.parentElement.children : [])].indexOf(e)); return p.join('/'); };
  const ownText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const textRect = el => { const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect(); };
  const boxOf = el => { for (let e = el.parentElement; e && e !== document.body && !e.dataset.scene; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if ((cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.backgroundImage !== 'none' || parseFloat(cs.borderTopWidth) > 0)
          && cs.display !== 'inline') return e; } return null; };
  // what an ancestor with overflow hidden lets through (a .rise mask, a camera window): only that part is on screen
  // and a clip-path inset() (a .wipe) on the element or an ancestor
  const clipOf = el => { const c = { l: -1e9, t: -1e9, r: 1e9, b: 1e9 };
    const keep = (l, t, r, b) => { c.l = Math.max(c.l, l); c.t = Math.max(c.t, t); c.r = Math.min(c.r, r); c.b = Math.min(c.b, b); };
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const cs = getComputedStyle(e), q = e.getBoundingClientRect();
      if (e !== el && /hidden|clip/.test(cs.overflowX + cs.overflowY)) keep(q.left, q.top, q.right, q.bottom);
      const m = /^inset\(([^)]*)\)/.exec(cs.clipPath);
      if (m) {
        const v = m[1].split(/\s+round\s+/)[0].trim().split(/\s+/);
        const [t, r, b, l] = [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
        const px = (s, size) => s.endsWith('%') ? parseFloat(s) / 100 * size : parseFloat(s) || 0;
        keep(q.left + px(l, q.width), q.top + px(t, q.height), q.right - px(r, q.width), q.bottom - px(b, q.height));
      }
    }
    return c; };
  const cut = (q, c) => { const l = Math.max(q.left, c.l), t = Math.max(q.top, c.t);
    const rr = Math.min(q.left + q.width, c.r), bb = Math.min(q.top + q.height, c.b);
    // wholly clipped gives 0, not a negative size (a negative area made every overlap test pass)
    return { left: l, top: t, width: Math.max(0, rr - l), height: Math.max(0, bb - t), right: rr, bottom: bb }; };
  const scope = [...(on ? on.querySelectorAll('*') : []), ...document.querySelectorAll('body > *:not([data-scene]) , body > *:not([data-scene]) *')];
  const out = [];
  for (const el of new Set(scope)) {
    if (el.closest('script, style, svg *')) continue;
    const a = alpha(el); if (a < 0.05) continue;
    const isText = ownText(el), isChar = el.hasAttribute('data-character');
    if (!isText && !isChar && !el.classList.contains('prop')) continue;
    const clip = clipOf(el), r = cut(isText ? textRect(el) : el.getBoundingClientRect(), clip);
    if (r.width < 1 || r.height < 1) continue;  // wholly masked: not on screen this frame
    // for overlaps, the line box: a Thai font's glyph box is far taller than the line it sits on, so two
    // stacked lines' glyph boxes always touch. Block-level text uses its own box; inline text its glyph box, inset.
    const disp = getComputedStyle(el).display, fs = parseFloat(getComputedStyle(el).fontSize);
    let lb = r;
    if (isText && disp !== 'inline') {
      const b = el.getBoundingClientRect();
      lb = cut({ left: Math.max(b.left, r.left), top: b.top, width: Math.min(b.right, r.right) - Math.max(b.left, r.left), height: b.height }, clip);
    } else if (isText) {
      const k = (r.height / (el.getBoundingClientRect().height || r.height)) * fs * .18;
      lb = { left: r.left, top: r.top + k, width: r.width, height: Math.max(1, r.height - 2 * k) };
    }
    const scale = el.offsetWidth ? el.getBoundingClientRect().width / el.offsetWidth : 1;
    const box = isText ? boxOf(el) : null, br = box ? box.getBoundingClientRect() : null;
    // under something opaque: probe the start, middle and end of the text's mid-line. Text that is meant to be
    // seen and is covered is a finding of its own ("hidden"), and isn't also counted as a collision
    const opaqueOver = (x, y) => {
      const top = document.elementFromPoint(Math.min(W - 1, Math.max(0, x)), Math.min(H - 1, Math.max(0, y)));
      if (!top || el.contains(top) || top.contains(el)) return null;
      for (let e = top; e && e !== document.body; e = e.parentElement) {
        if (e.contains(el)) return null;
        const cs = getComputedStyle(e), bg = cs.backgroundColor.match(/[\d.]+/g);
        const solid = (bg && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && (bg.length < 4 || +bg[3] > .9)) || cs.backgroundImage !== 'none';
        const er = e.getBoundingClientRect();
        if (solid && alpha(e) > .9 && er.width * er.height > 3600) return name(e);  // debris and sparks pass over, they don't hide
      }
      return null;
    };
    const midY = r.top + r.height / 2;
    const over = isText ? [r.left + 6, r.left + r.width / 2, r.right - 6].map(x => opaqueOver(x, midY)).filter(Boolean) : [];
    const covered = over.length > 0, coveredBy = over[0] || null;
    out.push({ id: path(el), name: name(el), text: isText, char: isChar, persistent: !el.closest('[data-scene]'),
      caption: el.id === 'caption', covered, coveredBy, x: r.left, y: r.top, w: r.width, h: r.height,
      lx: lb.left, ly: lb.top, lw: lb.width, lh: lb.height,
      font: isText ? parseFloat(getComputedStyle(el).fontSize) * scale : 0,
      box: br && { x: br.left, y: br.top, w: br.width, h: br.height, name: name(box) },
      skip: ['frame', 'spill', 'collide', 'hidden', 'small', 'safe', 'cut-jump', 'teleport'].filter(c => skip(el, c)) });
  }
  return out;
}"""


# when each finite animation in the shown scene starts, and how long it runs (seconds)
EVENTS = """() => document.getAnimations().map(a => a.effect.getTiming())
  .filter(t => Number.isFinite(t.iterations) && t.duration > 0 && t.duration < 2000)
  .map(t => [(+t.delay || 0) / 1000, (+t.duration) / 1000 * (+t.iterations || 1)])"""


def durations(project: Path, spec: str | None, fps: int) -> list[tuple[str, float]]:
    pairs = lexicon.load(project / "lexicon.tsv")
    out = []
    for s in script.parse(project / "script.md"):
        clip = voice._clip(lexicon.apply(s["speech"], pairs), project / ".bloom" / "voice", spec, None)[3]
        speak = voice.duration(clip) if clip.exists() else 5.0
        out.append((s["id"], round((cli.PAD_IN + speak + cli.PAD_OUT + s["hold"]) * fps) / fps))
    return out


def inter(a: dict, b: dict) -> float:
    """Overlap of two texts' line boxes, in px²."""
    w = min(a["lx"] + a["lw"], b["lx"] + b["lw"]) - max(a["lx"], b["lx"])
    h = min(a["ly"] + a["lh"], b["ly"] + b["lh"]) - max(a["ly"], b["ly"])
    return max(0.0, w) * max(0.0, h)


def check(items: list[dict], W: int, H: int) -> list[tuple[str, str, str]]:
    """(check, element, detail) for one frame."""
    found = []
    texts = [i for i in items if i["text"] and not i.get("covered")]
    for i in items:
        if (i["text"] or i["char"]) and "frame" not in i["skip"]:
            over = max(-i["x"], -i["y"], i["x"] + i["w"] - W, i["y"] + i["h"] - H)
            if over > 4:
                found.append(("frame", i["name"], f"{over:.0f} px outside the frame"))
        if i["text"] and i["box"] and "spill" not in i["skip"]:
            b = i["box"]
            over = max(b["x"] - i["x"], b["y"] - i["y"], i["x"] + i["w"] - (b["x"] + b["w"]), i["y"] + i["h"] - (b["y"] + b["h"]))
            if over > 4:
                found.append(("spill", i["name"], f"{over:.0f} px out of {b['name']}"))
        if i["text"] and i.get("covered") and "hidden" not in i["skip"]:
            found.append(("hidden", i["name"], f"covered by {i['coveredBy']}"))
        if i["text"] and 0 < i["font"] < 28 and "small" not in i["skip"]:
            found.append(("small", i["name"], f"{i['font']:.0f} px on the frame"))
        wide = W > H  # 16:9: title-safe 5 % all round; vertical: under the app's header and button column
        out = (i["x"] < W * .05 or i["x"] + i["w"] > W * .95 or i["y"] < H * .05 or i["y"] + i["h"] > H * .95) if wide \
            else (i["y"] < 150 or i["x"] + i["w"] > W - 110)
        if i["text"] and not i["caption"] and "safe" not in i["skip"] and out:
            found.append(("safe", i["name"], "in the platform overlay zone"))
    for k, a in enumerate(texts):
        for b in texts[k + 1:]:
            if a["id"].startswith(b["id"] + "/") or b["id"].startswith(a["id"] + "/"):
                continue  # one inside the other
            if "collide" in a["skip"] or "collide" in b["skip"]:
                continue
            area = inter(a, b)
            if area > 0.12 * min(a["lw"] * a["lh"], b["lw"] * b["lh"]):
                found.append(("collide", a["name"], f"overlaps {b['name']}"))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--voice", help="the --voice the build uses, for the real scene lengths")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--brand", default="daisy", help="the brand mark Bloom adds when it renders (daisy | daisy-end | none)")
    ap.add_argument("--step", type=float, default=0.25, help="seconds between sampled frames")
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    scenes = durations(a.project, a.voice, a.fps)
    findings: dict[tuple, dict] = {}

    def note(check_, scene, t, el, detail):
        k = (check_, scene, el)
        f = findings.setdefault(k, {"check": check_, "severity": SEVERITY[check_], "scene": scene, "element": el,
                                    "detail": detail, "from": t, "to": t})
        f["to"] = t

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        prepare(page, a.project / "scenes.html", (W, H), a.brand, sum(d for _, d in scenes))
        clock, last_persistent = 0.0, None
        for sid, dur in scenes:
            if not page.evaluate(SHOW, [sid, dur]):
                note("frame", sid, 0, "section", "script.md has this scene but scenes.html has no section")
                continue
            ts = [round(k * a.step, 3) for k in range(int(dur / a.step) + 1)] + [dur - 1 / a.fps]
            # every entrance, in its own frames: an animation that lasts less than a step falls between samples
            for start, length in page.evaluate(EVENTS):
                if 0 <= start < dur and length < 2:
                    ts += [round(start + k / a.fps, 3) for k in range(1, int(length * a.fps) + 2, 2)]
            for t in sorted(set(x for x in ts if x < dur)):
                frames = []
                for dt in (0.0, 1 / a.fps):  # two consecutive frames: layout now, motion between them
                    page.evaluate(SEEK, [sid, t + dt, "ตัวอย่างคำบรรยาย ทดสอบความยาวของบรรทัด", [1, 0.5], clock + t + dt])
                    frames.append({i["id"]: i for i in page.evaluate(PROBE, [W, H])})
                for c, el, detail in check(list(frames[0].values()), W, H):
                    note(c, sid, t, el, detail)
                for key, i in frames[0].items():
                    j = frames[1].get(key)
                    if j and "teleport" not in i["skip"] and j["name"] == i["name"]:  # a counting number re-centres; not a move
                        move = ((i["x"] - j["x"]) ** 2 + (i["y"] - j["y"]) ** 2) ** 0.5
                        if move > 250:
                            note("teleport", sid, t, i["name"], f"moved {move:.0f} px in one frame")
                if t == 0 and last_persistent:  # what stays across the cut must not jump at it
                    for key, i in frames[0].items():
                        j = last_persistent.get(key)
                        if i["persistent"] and j and "cut-jump" not in i["skip"]:
                            move = ((i["x"] - j["x"]) ** 2 + (i["y"] - j["y"]) ** 2) ** 0.5
                            if move > 30:
                                note("cut-jump", sid, 0.0, i["name"], f"jumps {move:.0f} px at the cut into this scene")
            page.evaluate(SEEK, [sid, dur - 1 / a.fps, "", [1, 0.5], clock + dur - 1 / a.fps])
            last_persistent = {i["id"]: i for i in page.evaluate(PROBE, [W, H]) if i["persistent"]}
            clock += dur
        browser.close()

    # a size or position that lasts a single sample is an entrance passing through (a card scaling up from
    # 0.4x): worth an error when it leaves the frame, not a warning about reading size
    rows = [f for f in findings.values() if f["severity"] == "error" or f["to"] - f["from"] >= a.step * 1.5]
    rows = sorted(rows, key=lambda f: (f["severity"] != "error", f["check"], f["scene"], f["from"]))
    out = a.project / ".bloom" / "audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    errors = [f for f in rows if f["severity"] == "error"]
    for f in rows:
        when = f"@{f['from']:.2f}s" + (f"–{f['to']:.2f}s" if f["to"] > f["from"] else "")
        print(f"{f['severity']:5} {f['check']:8} {f['scene']:<8} {when:<14} {f['element']} — {f['detail']}")
    print(f"{len(errors)} errors, {len(rows) - len(errors)} warnings · {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
