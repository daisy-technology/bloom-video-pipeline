"""Your own voice in Bloom: record a reference clip, check it against cloning best practice, try it.

  bloom voice record me                 read the sentence shown; saved to ~/.bloom/voices/me/
  bloom voice add me take.wav --text …  use a recording made elsewhere (QuickTime, a phone)
  bloom voice check me                  length, level, clipping, room noise, pauses, transcript match
  bloom voice test me                   say a test line in the cloned voice, play it, score it
  bloom build <project> --voice omnivoice:@me

OmniVoice clones locally: the recording never leaves the machine. Its model weights are CC-BY-NC,
so a cloned voice is for non-commercial videos; use ElevenLabs voice cloning for client work.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

from . import asr, lexicon, voice

# Read in the voice you want back: cloning copies pace and energy, not just timbre.
# About 15 s at a natural pace, so the whole take is voice. Plain Thai, no English, no numbers, no ครับ/ค่ะ
# (add your own particle and edit ref.txt to match). It covers the sounds a clone gets wrong first:
# clusters (ตร กร คร พร), ร against ล, all five tones, the เอีย and เอือ vowels, every final consonant class.
SENTENCE = ("วันนี้จะมาเล่าเรื่องสั้น ๆ ให้ฟัง ใช้เวลาไม่นาน แต่เอาไปใช้ได้จริงตั้งแต่พรุ่งนี้ "
            "เริ่มจากตรวจกระดาษทุกแผ่นให้ครบ เรียงลำดับให้ถูก แล้วค่อยกรอกข้อมูลลงระบบทีละขั้น "
            "ถ้าพร้อมแล้วก็ไปกันเลย")
RECORD_SECONDS = 20  # longer than the read, so a slow reader isn't cut off; the silence after is trimmed
TEST_LINE = "ระบบจะใช้เสียงนี้อ่านบทของวิดีโอทุกตัว ถ้าฟังแล้วยังไม่เหมือน ลองอัดใหม่อีกครั้ง"


def _save(name: str, src: Path, text: str) -> Path:
    """48 kHz mono, rumble removed, silence trimmed to 0.2 s at both ends, plus the exact transcript.

    The only clean-up is an 80 Hz high-pass: fan, AC and mains hum (100 Hz in 50 Hz countries) sit
    there, below the lowest notes of a voice, and it is the one filter every voice chain uses.
    "Silence" is anything within 10 dB of this recording's own room noise, so a late start
    trims away in a noisy room too (a fixed -45 dB threshold keeps it all once the room is louder).
    """
    d = voice.profiles_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    raw = d / "raw.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", "highpass=f=80", "-ar", "48000", "-ac", "1",
                    str(raw)], check=True)
    thr = min(-20.0, max(-60.0, measure(raw)["floor_db"] + 10))
    cut = f"silenceremove=start_periods=1:start_threshold={thr:.0f}dB:start_silence=0.2"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"{cut},areverse,{cut},areverse",
                    str(d / "ref.wav")], check=True)
    raw.unlink()
    (d / "ref.txt").write_text(text.strip() + "\n", encoding="utf-8")
    return d


def record(name: str, seconds: int = RECORD_SECONDS, device: str = "0", text: str = SENTENCE,
           lexicon_file: Path | None = None) -> bool:
    if sys.platform == "darwin":
        source = ["-f", "avfoundation", "-i", f":{device}"]
    elif sys.platform.startswith("linux"):
        source = ["-f", "alsa", "-i", device if device != "0" else "default"]
    else:
        raise SystemExit("recording works on macOS and Linux; record with any app, then `bloom voice add`")
    print("Quiet room, mic 15–20 cm away, speak up, read it the way you want videos to sound.")
    print("Read only the passage (no greeting before it), once, at a natural pace, then stay quiet until it stops:\n")
    print(f"    {text}\n")
    for n in (3, 2, 1):
        print(f"  {n}…", flush=True)
        time.sleep(1)
    print(f"● recording, up to {seconds} s (stops by itself)", flush=True)
    take = voice.profiles_dir() / name / "take.wav"
    take.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *source, "-t", str(seconds), "-ac", "1", "-ar", "48000", str(take)],
                   check=True)
    _save(name, take, text)
    take.unlink()
    return check(name, lexicon_file)


def add(name: str, recording: Path, text: str, lexicon_file: Path | None = None) -> bool:
    _save(name, Path(recording), text)
    return check(name, lexicon_file)


VOICE_BAND = 150  # Hz; noise below this is hum under the voice, which neither masks speech nor carries into a clone


def measure(wav: Path) -> dict:
    """Length, peak, room noise floor, voice level above it, and how much of the clip is speech.
    Floor, level and speech share are measured above VOICE_BAND, where noise actually masks words."""
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768
    spec = np.fft.rfft(x)
    spec[np.fft.rfftfreq(len(x), 1 / sr) < VOICE_BAND] = 0
    band = np.fft.irfft(spec, len(x))
    win = int(0.05 * sr)
    rms = np.sqrt(np.mean(band[: len(band) // win * win].reshape(-1, win) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    # the room is heard only in pauses: the 0.2 s kept at each end is ~4 % of a good take, so take the
    # quietest 2 %, not a higher percentile that lands on soft speech in a continuous reading
    floor = float(np.percentile(db, 2))
    voice_db = float(np.percentile(db, 90))  # the voice's loud parts, robust to a single click
    return {"seconds": len(x) / sr, "peak_db": 20 * math.log10(float(np.max(np.abs(x))) + 1e-9),
            "floor_db": floor, "snr_db": voice_db - floor, "speech": float(np.mean(db > floor + 10))}


def verdicts(m: dict, transcript_cer: float | None) -> list[tuple[str, str, str, str]]:
    """(check, value, ok | warn | fail, what to do) per best practice."""
    def rate(good, okay):
        return "ok" if good else ("warn" if okay else "fail")
    s, p, snr, sp = m["seconds"], m["peak_db"], m["snr_db"], m["speech"]
    rows = [
        ("length", f"{s:.1f} s", rate(10 <= s <= 17, 6 <= s <= 20), "10–17 s of speech: read the whole passage at a natural pace"),
        ("loudest peak", f"{p:.1f} dBFS", rate(-12 <= p <= -1, -20 <= p <= -0.3),
         "aim for about -6: move closer if quiet, back off or lower input gain if clipping"),
        # gain moves voice and room together, so judge the gap between them, not the room's level
        ("voice above room", f"{snr:.0f} dB", rate(snr >= 30, snr >= 20),
         "get closer (15 cm), speak up, switch off fans and AC, or use a headset mic"),
        ("speech, not pauses", f"{sp:.0%}", rate(sp >= 0.6, sp >= 0.45), "read straight through, no long pauses"),
    ]
    if transcript_cer is not None:
        rows.append(("words match ref.txt", f"CER {transcript_cer:.2f}", rate(transcript_cer <= 0.10, transcript_cer <= 0.20),
                     "re-record, or edit ref.txt to exactly what you said"))
    return rows


def check(name: str, lexicon_file: Path | None = None) -> bool:
    ref, text = voice.profile(name)
    cer = None
    if asr.available():  # Whisper writes "Wi-Fi", "API" its own way: compare after the lexicon too
        heard = asr.transcribe(ref)
        cer = min(asr.cer(text, heard), asr.cer(text, lexicon.apply(heard, lexicon.load(lexicon_file))))
    rows = verdicts(measure(ref), cer)
    mark = {"ok": "✓", "warn": "!", "fail": "✗"}
    print(f"\nvoice profile '{name}' ({ref})")
    for label, value, state, advice in rows:
        print(f"  {mark[state]} {label:<20} {value:<12}" + ("" if state == "ok" else f"  → {advice}"))
    if cer is None:
        print("  · words match ref.txt  skipped: needs whisper-cli and its model (run bench/tts_bench.py once)")
    good = all(r[2] != "fail" for r in rows)
    print("\n" + (f"ready: bloom build <project> --voice omnivoice:@{name}   (try it first: bloom voice test {name})"
                  if good else "fix the ✗ items and record again"))
    return good


def test(name: str, text: str = TEST_LINE, play: bool = True) -> Path:
    voice.profile(name)  # fail early with the profile message
    text = lexicon.apply(text, lexicon.load())  # the same words a video would say
    spec, cache = f"omnivoice:@{name}", voice.profiles_dir() / name / "cache"
    if voice.cached(text, cache, spec):
        print("this line was already made with this recording: playing it again "
              "(--text \"…\" says something new; re-recording the profile makes it fresh)")
        wav = voice.synth(text, cache, spec)
    else:
        print(f"synthesizing in the cloned voice, about {voice.fmt_seconds(voice.estimate([text], spec))} "
              "on this machine…", flush=True)
        t0 = time.time()
        wav = voice.synth(text, cache, spec)
        print(f"done in {voice.fmt_seconds(time.time() - t0)}")
    if asr.available():
        print(f"Whisper hears it with CER {asr.cer(text, asr.transcribe(wav)):.2f} (lower is clearer)")
    if play and shutil.which("afplay"):
        subprocess.run(["afplay", str(wav)])
    print(wav)
    return wav


def devices() -> None:
    """The microphones ffmpeg can record from, with the index `record --device` takes."""
    if sys.platform != "darwin":
        print("on Linux: arecord -l (use the card name as --device)")
        return
    out = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, encoding="utf-8", errors="replace").stderr
    mics = out.split("audio devices:")[-1] if "audio devices:" in out else ""
    for line in mics.splitlines():
        if "] [" in line:
            print("  " + line.split("] ", 1)[1])  # "[0] MacBook Pro Microphone"
    print("record with one: bloom voice record <name> --device <number>")


def listing() -> None:
    root = voice.profiles_dir()
    names = sorted(p.parent.name for p in root.glob("*/ref.wav")) if root.exists() else []
    if not names:
        print(f"no voice profiles in {root} yet: bloom voice record <name>")
    for n in names:
        print(f"  @{n:<12} {measure(root / n / 'ref.wav')['seconds']:.1f} s   bloom build <project> --voice omnivoice:@{n}")
