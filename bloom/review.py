"""Find the lines the voice may have said wrong, and a page to review and fix them.

After a dub or build, Whisper transcribes every line's clip. A line is flagged when what Whisper
heard is far from both the shown and the spoken text: Whisper writes English terms the way they
are shown ("API", "ภ.ง.ด. 90"), so a line is only suspect when it matches neither. The flag points at
lines to listen to; your ears decide. Fixes, from the page's copy buttons:

  bloom say "…"                      hear a line (and other takes of it) before changing anything
  bloom lexicon add "พาธ" "พาด"       say a word differently in every video from now on
  … --retake 12                      draw line 12 again, when only that take came out wrong
"""
from __future__ import annotations

import difflib
import html
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import asr, lexicon, voice

FLAG_AT = 0.15  # character error rate above which a line is worth a listen


def update_takes(path: Path, retake: str | None = None, use: str | None = None) -> dict[str, int]:
    """Line takes kept beside the video ({"12": 1}, take numbers from 0). `retake` "12,17" draws those
    lines once more; `use` "4=2,5=3" picks takes by the number an audition page shows (from 1)."""
    try:
        takes = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        takes = {}
    for key in [k.strip() for k in (retake or "").split(",") if k.strip()]:
        takes[key] = takes.get(key, 0) + 1
    for pair in [x for x in (use or "").split(",") if "=" in x]:
        n, k = (v.strip() for v in pair.split("=", 1))
        takes[n] = max(0, int(k) - 1)
    if retake or use:
        path.write_text(json.dumps(takes, indent=1), encoding="utf-8")
    return takes


def heard(wavs: list[Path], cache: Path) -> list[str]:
    """What Whisper hears in each clip, cached by clip name: a re-run only transcribes clips that changed."""
    try:
        known = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    for w in wavs:
        if Path(w).name not in known:
            known[Path(w).name] = asr.transcribe(Path(w))
    cache.write_text(json.dumps(known, ensure_ascii=False, indent=0), encoding="utf-8")
    return [known[Path(w).name] for w in wavs]


def check(lines: list[dict], heard_cache: Path, flag_at: float = FLAG_AT) -> list[dict]:
    """lines = [{"n", "start", "shown", "spoken", "wav"}]; adds "heard", "score" and "flag" to each."""
    for ln, h in zip(lines, heard([ln["wav"] for ln in lines], heard_cache)):
        ln["heard"] = h
        ln["score"] = round(min(asr.cer(ln["shown"], h), asr.cer(ln["spoken"], h)), 3)
        ln["flag"] = ln["score"] > flag_at
    return lines


def _marked(reference: str, heard: str) -> str:
    """`heard` as HTML, with the parts that differ from `reference` marked."""
    out = []
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, reference, heard, autojunk=False).get_opcodes():
        chunk = html.escape(heard[j1:j2])
        out.append(chunk if op == "equal" else f"<mark>{chunk}</mark>")
    return "".join(out) or "<em>(nothing heard)</em>"


def page(lines: list[dict], out_html: Path, video: Path, title: str, voice_spec: str, retake: str) -> Path:
    """Write the review page. `retake` is the exact re-run command with `{n}` where the line number goes."""
    here = out_html.parent
    rel = lambda p: html.escape(os.path.relpath(p, here))  # noqa: E731
    bloom = f"uv run --project {Path(__file__).resolve().parent.parent} bloom"
    flagged = [ln for ln in lines if ln["flag"]]
    cards = []
    for ln in sorted(lines, key=lambda ln: (not ln["flag"], ln["n"])):
        ref = ln["shown"] if asr.cer(ln["shown"], ln["heard"]) <= asr.cer(ln["spoken"], ln["heard"]) else ln["spoken"]
        cmds = [("Hear it again, other takes", f'{bloom} say "{ln["spoken"]}" --voice {voice_spec} --takes 3'),
                ("Say a word differently, everywhere", f'{bloom} lexicon add "<word as shown>" "<how to say it>"'),
                ("Draw this line again", retake.format(n=ln["n"], id=ln.get("id", ln["n"])))]
        cmd_html = "".join(
            f'<div class="cmd"><span>{html.escape(label)}</span><code>{html.escape(c)}</code>'
            f'<button type="button" class="copy">Copy</button></div>' for label, c in cmds)
        cards.append(f"""
      <article class="line{' flagged' if ln['flag'] else ''}" data-flag="{int(ln['flag'])}">
        <header>
          <button type="button" class="seek" data-t="{ln['start']:.2f}">#{ln['n']} · {int(ln['start'] // 60)}:{ln['start'] % 60:04.1f}</button>
          <span class="badge {'bad' if ln['flag'] else 'ok'}">{'may be wrong' if ln['flag'] else 'sounds fine'} · CER {ln['score']:.2f}</span>
        </header>
        <dl>
          <dt>Shown</dt><dd lang="th">{html.escape(ln['shown'])}</dd>
          <dt>Spoken</dt><dd lang="th">{html.escape(ln['spoken'])}</dd>
          <dt>Heard</dt><dd lang="th">{_marked(ref, ln['heard'])}</dd>
        </dl>
        <audio controls preload="none" src="{rel(ln['wav'])}"></audio>
        <details><summary>Fix it</summary>{cmd_html}</details>
      </article>""")
    out_html.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · voice review</title>
<style>
  :root {{ --bg: #f6f6f3; --card: #fff; --fg: #1d211f; --muted: #5f665f; --line: #deded8; --bad: #b23a2e;
          --good: #2e7a46; --mark: #ffd9a8; --font: "Noto Sans Thai", system-ui, sans-serif; --mono: ui-monospace, Menlo, monospace; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg: #151816; --card: #1e2320; --fg: #ebebe5; --muted: #a3aaa2;
          --line: #333a34; --bad: #ff7b6b; --good: #6fcf8a; --mark: #6b4a12; color-scheme: dark; }} }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.6 var(--font); }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px max(16px, env(safe-area-inset-left, 0px)) 64px; display: grid; gap: 18px; }}
  h1 {{ margin: 0; font-size: clamp(22px, 3vw, 30px); line-height: 1.2; }}
  .sum {{ margin: 0; color: var(--muted); }}
  .sum b {{ color: var(--bad); }}
  video {{ width: 100%; max-height: 52vh; background: #000; border-radius: 10px; }}
  .bar {{ position: sticky; top: 0; z-index: 2; display: flex; gap: 8px; padding: 10px 0; background: var(--bg); }}
  .bar button, .seek, .copy {{ font: inherit; font-size: 13px; border: 1px solid var(--line); background: var(--card);
          color: var(--fg); border-radius: 999px; padding: 4px 12px; cursor: pointer; }}
  .bar button[aria-pressed="true"] {{ background: var(--fg); color: var(--bg); border-color: var(--fg); }}
  button:focus-visible {{ outline: 2px solid var(--fg); outline-offset: 2px; }}
  .lines {{ display: grid; gap: 12px; }}
  .line {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; display: grid; gap: 8px; min-width: 0; }}
  .line.flagged {{ border-left: 4px solid var(--bad); }}
  .line header {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }}
  .badge {{ font: 600 12px var(--mono); }}
  .badge.bad {{ color: var(--bad); }} .badge.ok {{ color: var(--good); }}
  dl {{ margin: 0; display: grid; grid-template-columns: 70px minmax(0, 1fr); gap: 2px 10px; }}
  dt {{ color: var(--muted); font-size: 13px; }} dd {{ margin: 0; overflow-wrap: anywhere; }}
  mark {{ background: var(--mark); color: inherit; border-radius: 3px; padding: 0 1px; }}
  audio {{ width: 100%; height: 34px; }}
  details summary {{ cursor: pointer; color: var(--muted); font-size: 13px; }}
  .cmd {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; align-items: center; margin-top: 8px; }}
  .cmd span {{ grid-column: 1 / -1; font-size: 12px; color: var(--muted); }}
  .cmd code {{ font: 12px var(--mono); background: var(--bg); border-radius: 6px; padding: 6px 8px; overflow-x: auto; white-space: nowrap; }}
  body.only-flagged .line[data-flag="0"] {{ display: none; }}
</style>
</head>
<body class="{'only-flagged' if flagged else ''}">
<div class="wrap">
  <header>
    <h1>{html.escape(title)}</h1>
    <p class="sum">Voice <code>{html.escape(voice_spec)}</code> · {len(lines)} lines ·
      {f'<b>{len(flagged)} may be wrong</b>' if flagged else 'none flagged'}. Whisper's view, not the final word: listen, then fix what you hear.</p>
  </header>
  <video id="video" controls playsinline preload="metadata" src="{rel(video)}"></video>
  <div class="bar" role="group" aria-label="Show">
    <button type="button" data-show="flagged" aria-pressed="{str(bool(flagged)).lower()}">May be wrong ({len(flagged)})</button>
    <button type="button" data-show="all" aria-pressed="{str(not flagged).lower()}">All lines ({len(lines)})</button>
  </div>
  <div class="lines">{''.join(cards)}</div>
</div>
<script>
  const video = document.getElementById("video");
  for (const b of document.querySelectorAll(".seek")) b.addEventListener("click", () => {{
    video.currentTime = parseFloat(b.dataset.t); video.play(); video.scrollIntoView({{block: "nearest"}});
  }});
  for (const b of document.querySelectorAll(".bar button")) b.addEventListener("click", () => {{
    document.body.classList.toggle("only-flagged", b.dataset.show === "flagged");
    for (const o of document.querySelectorAll(".bar button")) o.setAttribute("aria-pressed", String(o === b));
  }});
  for (const b of document.querySelectorAll(".copy")) b.addEventListener("click", async () => {{
    const code = b.previousElementSibling;
    try {{ await navigator.clipboard.writeText(code.textContent); b.textContent = "Copied"; }}
    catch {{ getSelection().selectAllChildren(code); b.textContent = "Press ⌘C"; }}
    setTimeout(() => (b.textContent = "Copy"), 1500);
  }});
</script>
</body>
</html>
""", encoding="utf-8")
    return out_html


def audition_page(entries: list[dict], out_html: Path, voice_spec: str, use: str) -> Path:
    """Takes of a few lines side by side, one choice per line, and the command that keeps the choices.
    entries = [{"n", "shown", "spoken", "tempo", "current", "takes": [(take, wav, heard)]}], takes from 0;
    the picks ("4=3,5=2", numbered from 1 as the page shows them) are appended to `use`."""
    here = out_html.parent
    cards = []
    for e in entries:
        rows = "".join(
            f'<div class="take"><label><input type="radio" name="l{e["n"]}" value="{k + 1}"{" checked" if k == e["current"] else ""}>'
            f' Take {k + 1}{" <small>in the video now</small>" if k == e["current"] else ""}</label>'
            f'<audio controls preload="none" src="{html.escape(os.path.relpath(w, here))}"></audio>'
            f'<span class="h" lang="th">{html.escape(h)}</span></div>' for k, w, h in e["takes"])
        pace = f" · spoken {e['tempo']:.2f}x to keep up" if e["tempo"] > 1.001 else ""
        cards.append(f'<article><h2>#{e["n"]}{pace}</h2><p lang="th">{html.escape(e["shown"])}</p>'
                     f'<p class="h" lang="th">says: {html.escape(e["spoken"])}</p>{rows}</article>')
    out_html.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pick a take</title>
<style>
 :root {{ --bg:#f6f6f3; --card:#fff; --fg:#1d211f; --muted:#5f665f; --line:#deded8; --accent:#a8700a; --font:"Noto Sans Thai",system-ui,sans-serif; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#151816; --card:#1e2320; --fg:#ebebe5; --muted:#a3aaa2; --line:#333a34; --accent:#f2b632; color-scheme:dark; }} }}
 body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 var(--font); }}
 .wrap {{ max-width:900px; margin:0 auto; padding:24px 16px 120px; display:grid; gap:14px; }}
 h1 {{ margin:0; font-size:26px; }} h2 {{ margin:0; font-size:17px; }} p {{ margin:0; }} .h {{ color:var(--muted); font-size:13px; }}
 article {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; display:grid; gap:8px; min-width:0; }}
 .take {{ display:grid; grid-template-columns:200px 240px minmax(0,1fr); gap:4px 12px; align-items:center; border-top:1px solid var(--line); padding-top:8px; }}
 .take label {{ cursor:pointer; white-space:nowrap; }} .take input {{ accent-color:var(--accent); }} small {{ color:var(--accent); }}
 audio {{ width:100%; height:32px; }}
 .bar {{ position:fixed; inset:auto 0 0 0; background:var(--card); border-top:1px solid var(--line); padding:10px 16px; display:flex; gap:10px; align-items:center; }}
 .bar code {{ flex:1; min-width:0; overflow-x:auto; white-space:nowrap; font:12px ui-monospace,Menlo,monospace; color:var(--muted); }}
 button {{ font:inherit; font-size:14px; border:1px solid var(--line); background:var(--card); color:var(--fg); border-radius:999px; padding:6px 14px; cursor:pointer; }}
 @media (max-width:640px) {{ .take {{ grid-template-columns:1fr; }} }}
</style></head><body><div class="wrap">
<h1>Pick a take</h1>
<p class="h">Voice <code>{html.escape(voice_spec)}</code>. Each take is voiced exactly as the video will use it: same pace, same place. Choose one per line, then run the command at the bottom (or tell Claude the take numbers). The video is re-mixed with your picks, and later runs keep them.</p>
{"".join(cards)}</div>
<div class="bar"><code id="cmd"></code><button type="button" id="copy">Copy command</button></div>
<script>
const use = {json.dumps(use).replace("</", "<\\/")}, cmd = document.getElementById("cmd"), copy = document.getElementById("copy");
const update = () => (cmd.textContent = use + [...document.querySelectorAll("input:checked")].map(r => r.name.slice(1) + "=" + r.value).join(","));
document.addEventListener("change", update); update();
copy.addEventListener("click", async () => {{
  try {{ await navigator.clipboard.writeText(cmd.textContent); copy.textContent = "Copied"; }}
  catch {{ getSelection().selectAllChildren(cmd); copy.textContent = "Press ⌘C"; }}
  setTimeout(() => (copy.textContent = "Copy command"), 1500); }});
</script></body></html>""", encoding="utf-8")
    return out_html


def summary(lines: list[dict], out_html: Path) -> None:
    flagged = [ln for ln in lines if ln["flag"]]
    print(f"  {len(flagged)} of {len(lines)} lines may be wrong" + (":" if flagged else ""))
    for ln in flagged[:8]:
        print(f"    #{ln['n']} heard \"{ln['heard'][:70]}\"")
    print(f"  review: {out_html}")


def say(text: str, spec: str | None, takes: int = 1, play: bool = True, project_lexicon: Path | None = None) -> list[Path]:
    """Hear `text` as a video would say it (lexicon applied), in `takes` takes, with what Whisper hears."""
    spoken = lexicon.apply(text, lexicon.load(project_lexicon))
    if spoken != text:
        print(f"spoken as: {spoken}")
    cache = Path.home() / ".cache/bloom/say"
    wavs = []
    for take in range(takes):
        cached = voice.cached(spoken, cache, spec, take=take)
        if not cached:
            print(f"take {take + 1}: synthesizing, about {voice.fmt_seconds(voice.estimate([spoken], spec))}…", flush=True)
        wav = voice.synth(spoken, cache, spec, take=take)
        note = ""
        if asr.available():
            h = asr.transcribe(wav)
            note = f"  heard: {h}  (CER {min(asr.cer(text, h), asr.cer(spoken, h)):.2f})"
        print(f"take {take + 1}: {voice.duration(wav):.1f} s{note}", flush=True)
        if play and shutil.which("afplay"):
            subprocess.run(["afplay", str(wav)])
        wavs.append(wav)
    return wavs
