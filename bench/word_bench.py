"""Which spelling makes the voice say a word the way *you* say it?

  uv run python bench/word_bench.py "Wi-Fi" --mine my-word.wav \\
      --spellings ไวไฟ วายฟาย ไว-ไฟ --voices omnivoice:@me --takes 2 \\
      --context "เปิด {} ที่บ้าน" --out word-bench.html

Every candidate is synthesized on its own, trimmed, and compared with your recording of the word:
MFCC features with the loudness band dropped and the mean removed (so the microphone and the
level don't count), aligned by dynamic time warping (so speed doesn't count either). What is left
is how it sounds: lower distance = closer to you. Whisper's reading is shown beside it. The page
plays your clip, then every candidate best first, alone and inside the context sentence.

Inside a sentence the word is found by subsequence DTW: your clip slides along the sentence and the
stretch that matches best is scored. It may be half to twice as long as your word, and when the
sentence's text is known, only the part where the word should be is searched: a voice speaks at a
fairly steady pace, so the share of text before the word is about the share of time before it
(without this, a similar-sounding word at the end of a line could pass for yours). So the context sentence gets a
distance too, and so can clips you already have: `--clips "#5 take 3=b.wav=<its text>"` ranks,
say, a dub's audition takes by how close their word is to yours.

`--mine` can also cut the word out of a voice profile's recording: `--mine @me`, using
Whisper's word timings to find it.
"""
from __future__ import annotations

import argparse
import html
import os
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bloom import asr, voice  # noqa: E402

SR = 16000
CACHE = Path.home() / ".cache/bloom/wordbench"
SLOPE = np.array([[1, 1], [1, 2], [2, 1]])  # in a sentence the word may be half to twice as long as yours


def load(wav: Path) -> np.ndarray:
    import librosa

    y, _ = librosa.load(str(wav), sr=SR, mono=True)
    return librosa.effects.trim(y, top_db=30)[0]


def features(y: np.ndarray) -> np.ndarray:
    import librosa

    m = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=20)[1:]  # drop c0: loudness
    return m - m.mean(axis=1, keepdims=True)  # cepstral mean removal: mic and channel


def span(text: str, words: list[str], pad: float = 0.15) -> tuple[float, float] | None:
    """Where one of `words` should be in a clip of `text`, as shares of its length, padded either side."""
    timed = lambda t: sum(unicodedata.category(c) != "Mn" for c in t)  # noqa: E731 - tone marks and vowel signs take no time
    for w in words:
        i = text.find(w)
        if i >= 0:
            n = timed(text)
            return max(0.0, timed(text[:i]) / n - pad), min(1.0, timed(text[:i + len(w)]) / n + pad)
    return None


def distance(a: np.ndarray, b: np.ndarray, within: bool = False, where: tuple[float, float] | None = None) -> float:
    """How different `a` sounds from `b`, lower is closer. within=True finds `a` inside a longer `b`
    (a word in a sentence), searching only `where` (shares of b) when given, and scores the best stretch."""
    import librosa

    fb = features(b)
    if where:
        m = fb.shape[1]
        fb = fb[:, int(where[0] * m):max(int(where[1] * m), int(where[0] * m) + 1)]
    cost, path = librosa.sequence.dtw(X=features(a), Y=fb, metric="euclidean", subseq=within,
                                      step_sizes_sigma=SLOPE if within else None)
    return float(cost[tuple(path[0])] / len(path))


def cut_from_profile(name: str, word: str, out: Path) -> Path:
    """Find `word` in a profile's reference with Whisper's word timings and cut it out."""
    ref, _ = voice.profile(name)
    with tempfile.TemporaryDirectory() as d:
        w16 = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ref), "-ar", str(SR), "-ac", "1", str(w16)], check=True)
        lines = subprocess.run(["whisper-cli", "-m", str(asr.MODEL), "-l", "th", "-ml", "1", "-sow", "-np", "-f", str(w16)],
                               capture_output=True, encoding="utf-8", errors="replace", check=True).stdout.splitlines()
    key = asr.normalize(word)
    for line in lines:
        if "-->" in line and key and key in asr.normalize(line.split("]", 1)[1]):
            t0, t1 = (sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.strip().split(":"))))
                      for t in line[1:line.index("]")].split("-->"))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t0 - 0.05):.2f}", "-to", f"{t1 + 0.05:.2f}",
                            "-i", str(ref), "-ar", str(SR), "-ac", "1", str(out)], check=True)
            return out
    raise SystemExit(f"Whisper didn't hear {word!r} in @{name}'s recording; record the word alone and pass --mine file.wav")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("word", help="the word as captions show it, e.g. Wi-Fi")
    ap.add_argument("--mine", required=True, help="your recording of the word (wav), or @profile to cut it from one")
    ap.add_argument("--spellings", nargs="+", required=True)
    ap.add_argument("--voices", nargs="+", default=["omnivoice:@me"])
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--context", default="{}", help='a sentence around the word, e.g. "หน้าหลัก {} รวมระบบงาน"')
    ap.add_argument("--clips", nargs="*", default=[], metavar="LABEL=WAV[=TEXT]",
                    help="clips you already have to rank too, e.g. a dub's audition takes; the word is found inside "
                         "each, near where TEXT has it when given")
    ap.add_argument("--out", type=Path, default=Path("word-bench.html"))
    a = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    mine = Path(a.mine) if not a.mine.startswith("@") else \
        cut_from_profile(a.mine[1:], a.word, CACHE / f"mine-{a.mine[1:]}-{asr.normalize(a.word) or 'word'}.wav")
    you = load(mine)
    print(f"your {a.word}: {len(you) / SR:.2f} s, Whisper hears \"{asr.transcribe(mine)}\"", flush=True)

    rows = []
    total = len(a.spellings) * len(a.voices) * (a.takes + 1)
    n = 0
    for spec in a.voices:
        for spelling in a.spellings:
            in_context = voice.synth(a.context.format(spelling), CACHE, spec)
            dc = distance(you, load(in_context), within=True, where=span(a.context.format(spelling), [spelling]))
            n += 1
            for take in range(a.takes):
                wav = voice.synth(spelling, CACHE, spec, take=take)
                n += 1
                d = distance(you, load(wav))
                rows.append({"spelling": spelling, "voice": spec, "take": take + 1, "d": d, "wav": wav,
                             "ctx": in_context, "dc": dc, "heard": asr.transcribe(wav)})
                print(f"  {n:>2}/{total}  {spec:<20} {spelling:<14} take {take + 1}  distance {d:6.2f}  "
                      f"(in a sentence {dc:5.2f})  heard \"{rows[-1]['heard']}\"", flush=True)
    clips = []
    for item in a.clips:
        label, path, text = (item.split("=", 2) + [""])[:3]
        clips.append({"label": label, "wav": Path(path), "heard": asr.transcribe(Path(path)),
                      "d": distance(you, load(Path(path)), within=True, where=span(text, [*a.spellings, a.word]))})
        print(f"  clip {label:<14} distance {clips[-1]['d']:6.2f}  heard \"{clips[-1]['heard']}\"", flush=True)
    clips.sort(key=lambda c: c["d"])

    # rank by each spelling+voice's average over its takes: one take can differ from the next by as
    # much as two spellings do, so the single closest take is partly luck; the average is what a
    # lexicon entry gives you on every line it touches
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["spelling"], r["voice"]), []).append(r)
    for g in groups.values():
        for r in g:
            r["avg"] = sum(x["d"] for x in g) / len(g)
    rows.sort(key=lambda r: (r["avg"], r["d"]))
    here = a.out.resolve().parent
    rel = lambda p: html.escape(os.path.relpath(p, here))  # noqa: E731
    body = "".join(
        f"<tr><td class=n>{i}</td><td lang=th><b>{html.escape(r['spelling'])}</b></td><td><code>{html.escape(r['voice'])}</code> · take {r['take']}</td>"
        f"<td class=n>{r['avg']:.1f}</td><td class=n>{r['d']:.1f}</td><td><audio controls preload=none src=\"{rel(r['wav'])}\"></audio></td>"
        f"<td><audio controls preload=none src=\"{rel(r['ctx'])}\"></audio></td><td class=n>{r['dc']:.1f}</td>"
        f"<td lang=th class=h>{html.escape(r['heard'])}</td></tr>"
        for i, r in enumerate(rows, 1))
    top = rows[0]
    clip_table = "" if not clips else (
        "<h2>Clips you already have</h2><p>Your word found inside each clip and scored there. Compare these with each other: "
        "a word inside a sentence scores on its own scale, not the word-alone one above.</p>"
        "<div class=box><table><thead><tr><th>#</th><th>Clip</th><th>Distance</th><th>Listen</th><th>Whisper heard</th></tr></thead><tbody>"
        + "".join(f"<tr><td class=n>{i}</td><td><b>{html.escape(c['label'])}</b></td><td class=n>{c['d']:.1f}</td>"
                  f"<td><audio controls preload=none src=\"{rel(c['wav'])}\"></audio></td><td lang=th class=h>{html.escape(c['heard'])}</td></tr>"
                  for i, c in enumerate(clips, 1))
        + "</tbody></table></div>")
    best_clip = f" Closest clip: <b>{html.escape(clips[0]['label'])}</b> ({clips[0]['d']:.1f})." if clips else ""
    a.out.write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(a.word)} · word bench</title>
<style>
 :root{{--bg:#f6f6f3;--card:#fff;--fg:#1d211f;--muted:#5f665f;--line:#deded8;--accent:#a8700a;--font:"Noto Sans Thai",system-ui,sans-serif}}
 @media (prefers-color-scheme:dark){{:root{{--bg:#151816;--card:#1e2320;--fg:#ebebe5;--muted:#a3aaa2;--line:#333a34;--accent:#f2b632;color-scheme:dark}}}}
 body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--font)}}
 .wrap{{max-width:1180px;margin:0 auto;padding:24px 16px 60px;display:grid;gap:16px}}
 h1{{margin:0;font-size:clamp(22px,3vw,30px)}} h2{{margin:8px 0 0;font-size:19px}} p{{margin:0;color:var(--muted);max-width:75ch}}
 .you{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}}
 .box{{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}}
 table{{border-collapse:collapse;width:100%;min-width:900px;font-size:14px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:middle}}
 thead th{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
 .n{{font-variant-numeric:tabular-nums}} .h{{color:var(--muted)}} audio{{height:32px;width:190px}}
 tbody tr:first-child{{background:color-mix(in srgb,var(--accent) 14%,transparent)}}
</style></head><body><div class=wrap>
<h1>How should the voice say “{html.escape(a.word)}”?</h1>
<p>Each candidate spelling, in each voice, compared with how <b>you</b> say it: the sound itself, not Whisper's spelling. Lower distance = closer to you. Listen to the top few before deciding: the score is a guide.</p>
<div class=you><b>You:</b><audio controls src="{rel(mine)}"></audio><span>Closest on average: <b lang=th>{html.escape(top['spelling'])}</b> with <code>{html.escape(top['voice'])}</code> (average distance {top['avg']:.1f} over {a.takes} takes).{best_clip}</span></div>
<div class=box><table><thead><tr><th>#</th><th>Spelling</th><th>Voice</th><th>Average</th><th>This take</th><th>Word</th><th>In a sentence</th><th>Sentence distance</th><th>Whisper heard</th></tr></thead>
<tbody>{body}</tbody></table></div>
{clip_table}</div></body></html>""", encoding="utf-8")
    print(f"\nclosest on average: {top['spelling']} with {top['voice']} ({top['avg']:.1f})"
          + (f"; closest clip: {clips[0]['label']} ({clips[0]['d']:.1f})" if clips else "") + f" -> {a.out}")


if __name__ == "__main__":
    main()
