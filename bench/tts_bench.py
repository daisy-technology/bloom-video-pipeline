"""Thai TTS benchmark: the same sentences through every voice Bloom can use.

Each voice is scored on
  RTF   synthesis seconds per second of audio, after a warm-up (lower is faster; < 1 is faster than real time)
  CER   character error rate of a Whisper round trip: what whisper.cpp hears vs. what was written.
        It measures intelligibility, not naturalness or warmth. Listen to the clips for those.
  cost  ElevenLabs credits, read from the account before and after each model (local voices: 0)

  uv run python bench/tts_bench.py                    # every voice this machine can run
  uv run python bench/tts_bench.py --only omnivoice   # one provider (say | omnivoice | elevenlabs)

Needs whisper-cli (`brew install whisper-cpp`); downloads ggml-large-v3-turbo (1.6 GB) once to ~/.cache/bloom.
Writes output/bench/: <voice>/<n>.mp3, results.json, report.md, listen.html.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bloom import asr, voice  # noqa: E402

SENTENCES = [
    ("everyday", "วันนี้อากาศดี เหมาะกับการออกไปเดินเล่นที่สวนสาธารณะตอนเย็น"),
    ("formal", "กรุณายืนยันตัวตนภายในสิบห้านาที มิฉะนั้นระบบจะยกเลิกคำขอโดยอัตโนมัติ"),
    ("numbers", "ราคาเริ่มต้นที่ 1,250 บาท ส่งฟรีทั่วประเทศภายใน 3 วัน"),
    ("english", "ทีมใช้ Python กับ ffmpeg ตัดต่อวิดีโอ แล้วอัปโหลดขึ้น YouTube"),
    ("question", "แล้วถ้าระบบล่มตอนตีสามล่ะ ใครจะรู้ก่อน"),
    ("clusters", "โรงกลั่นแต่ละแห่งเรียงบรรทัดในแบบฟอร์มไม่เหมือนกัน"),
]

# (label, voice spec, env overrides, license / terms)
VOICES = [
    ("macOS say · Kanya", "say:Kanya", {}, "free; Apple system voice"),
    ("OmniVoice · 32 steps", "omnivoice:female", {"BLOOM_OV_STEPS": "32"}, "free, local; weights CC-BY-NC"),
    ("OmniVoice · 16 steps", "omnivoice:female", {"BLOOM_OV_STEPS": "16"}, "free, local; weights CC-BY-NC"),
    ("ElevenLabs · eleven_v3", "elevenlabs:eleven_v3", {}, "credits; free plan needs attribution"),
    ("ElevenLabs · multilingual_v2", "elevenlabs:eleven_multilingual_v2", {}, "credits; Thai not in its language list"),
    ("ElevenLabs · flash_v2_5", "elevenlabs:eleven_flash_v2_5", {}, "credits; Thai not in its language list"),
    ("ElevenLabs · turbo_v2_5", "elevenlabs:eleven_turbo_v2_5", {}, "credits; Thai not in its language list"),
]

# ---- scoring: bloom.asr (Whisper round trip) ----------------------------------------------


def credits_used() -> int | None:
    """Characters used this billing period, or None when the key can't read the subscription."""
    try:
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription",
                                     headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(json.load(r)["character_count"])
    except Exception:
        return None

# ---- run -----------------------------------------------------------------------------------


def available(spec: str) -> bool:
    provider = spec.split(":")[0]
    if provider == "say":
        return bool(shutil.which("say"))
    if provider == "elevenlabs":
        return bool(os.environ.get("ELEVENLABS_API_KEY"))
    return importlib.util.find_spec("omnivoice") is not None


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def run_voice(label: str, spec: str, env: dict, out: Path) -> dict:
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    folder = out / slug(label)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as cache:
            if not spec.startswith("elevenlabs"):  # load the model / design the anchor voice outside the clock
                voice.synth("ทดสอบเสียง", Path(cache), spec)
            before = credits_used() if spec.startswith("elevenlabs") else 0
            rows = []
            for i, (kind, text) in enumerate(SENTENCES, 1):
                t = time.perf_counter()
                wav = voice.synth(text, Path(cache), spec)
                took = time.perf_counter() - t
                dur = voice.duration(wav)
                heard = asr.transcribe(wav)
                mp3 = folder / f"{i}-{kind}.mp3"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "96k", str(mp3)], check=True)
                rows.append({"kind": kind, "text": text, "heard": heard, "cer": round(asr.cer(text, heard), 3),
                             "synth_s": round(took, 2), "audio_s": round(dur, 2), "mp3": str(mp3.relative_to(out))})
                print(f"  {kind:<9} cer {rows[-1]['cer']:.2f}  {took:5.1f}s for {dur:4.1f}s  heard: {heard}", flush=True)
            after = credits_used() if spec.startswith("elevenlabs") else 0
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    synth, audio = sum(r["synth_s"] for r in rows), sum(r["audio_s"] for r in rows)
    return {"label": label, "spec": spec, "env": env, "rows": rows,
            "rtf": round(synth / audio, 2), "cer": round(sum(r["cer"] for r in rows) / len(rows), 3),
            "credits": None if before is None or after is None else after - before,
            "chars": sum(len(t) for _, t in SENTENCES)}


def report(results: list[dict], out: Path) -> None:
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    terms = {label: t for label, _, _, t in VOICES}
    lines = ["# Thai TTS benchmark", "",
             f"{len(SENTENCES)} sentences, {results[0]['chars']} characters. CER = Whisper large-v3-turbo round trip, lower is better.", "",
             "| Voice | Mean CER | RTF | Credits | Terms |", "|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: r["cer"]):
        credits = "0" if r["credits"] == 0 else ("n/a" if r["credits"] is None else str(r["credits"]))
        lines.append(f"| {r['label']} | {r['cer']:.3f} | {r['rtf']:.2f} | {credits} | {terms.get(r['label'], '')} |")
    lines += ["", "## Per sentence (CER)", "", "| Voice | " + " | ".join(k for k, _ in SENTENCES) + " |",
              "|---|" + "---|" * len(SENTENCES)]
    for r in results:
        lines.append(f"| {r['label']} | " + " | ".join(f"{x['cer']:.2f}" for x in r["rows"]) + " |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cells = []
    for i, (kind, text) in enumerate(SENTENCES):
        players = "".join(
            f'<div class="v"><b>{html.escape(r["label"])}</b><audio controls preload="none" src="{r["rows"][i]["mp3"]}"></audio>'
            f'<small>CER {r["rows"][i]["cer"]:.2f} · heard: {html.escape(r["rows"][i]["heard"])}</small></div>'
            for r in results)
        cells.append(f"<section><h2>{kind}</h2><p>{html.escape(text)}</p>{players}</section>")
    (out / "listen.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Thai TTS benchmark</title>"
        "<style>body{font-family:'Noto Sans Thai',sans-serif;max-width:900px;margin:2em auto;padding:0 16px}"
        ".v{display:grid;grid-template-columns:240px 1fr;gap:4px 12px;align-items:center;margin:8px 0}"
        ".v small{grid-column:2;color:#666}audio{width:100%}</style>"
        "<h1>Thai TTS benchmark</h1>" + "".join(cells), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated providers: say,omnivoice,elevenlabs")
    ap.add_argument("--out", type=Path, default=Path("output/bench"))
    a = ap.parse_args()
    asr.ensure_model()
    only = set(a.only.split(",")) if a.only else None
    results = []
    for label, spec, env, _ in VOICES:
        if only and spec.split(":")[0] not in only:
            continue
        if not available(spec):
            print(f"skip {label}: not available here")
            continue
        print(f"{label}")
        try:
            results.append(run_voice(label, spec, env, a.out))
        except Exception as e:  # one failing voice (quota, model access) must not sink the rest
            print(f"  failed: {e}")
    if results:
        # merge with earlier runs, so `--only elevenlabs` adds rows instead of wiping the local voices
        old = a.out / "results.json"
        keep = [r for r in json.loads(old.read_text(encoding="utf-8"))] if old.exists() else []
        fresh = {r["label"] for r in results}
        order = [label for label, *_ in VOICES]
        merged = sorted([r for r in keep if r["label"] not in fresh] + results,
                        key=lambda r: order.index(r["label"]) if r["label"] in order else len(order))
        report(merged, a.out)
        print((a.out / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
