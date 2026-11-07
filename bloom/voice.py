"""Text -> speech.

Pick a voice with `--voice <provider>[:<variant>]` (or BLOOM_VOICE):

  omnivoice[:<instruct>]   default. k2-fsa/OmniVoice, runs locally (Apple Silicon, CUDA or CPU), free.
                           Model weights are CC-BY-NC: non-commercial use only.
  omnivoice:@<name>        your own voice, cloned from a profile made with `bloom voice record <name>`.
  elevenlabs[:<model_id>]  hosted, needs ELEVENLABS_API_KEY. Default model eleven_v3, the one that speaks Thai.
  say[:<voice>]            macOS built-in, default Kanya (Thai). Offline, robotic, always there.

Clips are cached by provider + settings + text, so re-rendering after changing only the
animation never synthesizes (or bills) the same line twice.
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import thainum

PROVIDERS = ("omnivoice", "elevenlabs", "say")

# OmniVoice: every scene clones one reference voice, so the voice stays the same across scenes.
# The reference is a voice profile (`@name`), or else designed once from the instruct and cached.
ANCHOR_TEXT = "วันนี้มีเรื่องสั้น ๆ มาเล่าให้ฟัง ฟังจบแล้วเอาไปใช้ได้เลย"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def home() -> Path:
    """Bloom's own folder (BLOOM_HOME, default ~/.bloom): voice profiles and the global lexicon,
    outside every repo, because a voice is personal data."""
    return Path(_env("BLOOM_HOME", str(Path.home() / ".bloom")))


def profiles_dir() -> Path:
    return Path(_env("BLOOM_VOICES", str(home() / "voices")))


def profile(name: str) -> tuple[Path, str]:
    """A profile's reference recording and the exact words spoken in it."""
    d = profiles_dir() / name
    ref, txt = d / "ref.wav", d / "ref.txt"
    if not (ref.exists() and txt.exists()):
        raise FileNotFoundError(f"no voice profile {name!r} in {profiles_dir()}: run `bloom voice record {name}` first")
    return ref, txt.read_text(encoding="utf-8").strip()


def default_provider() -> str:
    if importlib.util.find_spec("omnivoice"):
        return "omnivoice"
    if _env("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if shutil.which("say"):
        return "say"
    raise RuntimeError("no voice provider: install omnivoice, set ELEVENLABS_API_KEY, or run on macOS for `say`")


def resolve(spec: str | None) -> tuple[str, str]:
    """'elevenlabs:eleven_flash_v2_5' -> ('elevenlabs', 'eleven_flash_v2_5'), defaults filled in."""
    provider, _, variant = (spec or _env("BLOOM_VOICE") or default_provider()).partition(":")
    if provider not in PROVIDERS:
        raise ValueError(f"unknown voice provider {provider!r}, expected one of {PROVIDERS}")
    default = {"omnivoice": _env("BLOOM_OV_INSTRUCT", "male"),
               "elevenlabs": _env("ELEVENLABS_MODEL_ID", "eleven_v3"),
               "say": _env("BLOOM_SAY_VOICE", "Kanya")}[provider]
    return provider, variant or default


def _settings(provider: str, variant: str) -> str:
    """Everything besides the text that changes the audio; part of the cache key."""
    if provider == "omnivoice":
        ref_id = ANCHOR_TEXT
        if variant.startswith("@"):  # a re-recorded profile changes the key, so it re-voices
            ref, text = profile(variant[1:])
            ref_id = f"{ref}:{ref.stat().st_size}:{ref.stat().st_mtime}|{text}"
        return f"{variant}|{ref_id}||{_env('BLOOM_OV_STEPS', '32')}|{_env('BLOOM_OV_SPEED')}"
    if provider == "elevenlabs":
        return f"{variant}|{_env('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')}"
    return f"{variant}|{_env('BLOOM_SAY_RATE', '175')}"


def _clip(text: str, cache: Path, spec: str | None, fit: float | None, take: int = 0) -> tuple[str, str, str, Path]:
    provider, variant = resolve(spec)
    if provider == "omnivoice":
        text = thainum.spell(text)  # say and ElevenLabs read digits themselves; OmniVoice garbles them
    fitted = f"|{fit:.3f}s" if fit else ""
    retake = f"|take{take}" if take else ""  # take 0 keeps the key every earlier cache was made with
    key = hashlib.sha1(f"{provider}|{_settings(provider, variant)}|{text}{fitted}{retake}".encode()).hexdigest()[:16]
    return provider, variant, text, Path(cache) / f"{provider}-{key}.wav"


def cached(text: str, cache: Path, spec: str | None = None, fit: float | None = None, take: int = 0) -> bool:
    return _clip(text, cache, spec, fit, take)[3].exists()


def synth(text: str, cache: Path, spec: str | None = None, fit: float | None = None, take: int = 0) -> Path:
    """Speak `text`, return a 48 kHz mono WAV path inside `cache`.

    `fit` (seconds) makes the line exactly that long, for re-voicing a picture that is already
    animated: OmniVoice paces itself to it; other voices are time-stretched to it. `take` > 0
    asks for another take of the same line (OmniVoice draws it with a different seed).
    """
    return synth_many([text], cache, spec, [fit], takes=[take])[0]


def synth_many(texts: list[str], cache: Path, spec: str | None = None, fits: list[float | None] | None = None,
               progress=None, takes: list[int] | None = None) -> list[Path]:
    """Speak every line; return their clip paths in the same order as `texts`.

    OmniVoice lines go through the GPU BLOOM_OV_BATCH at a time, and the voice's reference recording
    is prepared once for the run instead of once per line. A line's take can differ with the batch
    it was made in; the cache keeps whichever take came first. `fits` gives each line an exact
    length (or None); `progress(done, total)` is called as clips land.
    """
    fits = list(fits) if fits else [None] * len(texts)
    takes = list(takes) if takes else [0] * len(texts)
    items = [(*_clip(t, cache, spec, f, k), f, k) for t, f, k in zip(texts, fits, takes)]
    todo, seen = [], set()
    for it in items:  # (provider, variant, text, out, fit, take); the same line twice is made once
        if not it[3].exists() and it[3] not in seen:
            seen.add(it[3])
            todo.append(it)
    if todo:
        Path(cache).mkdir(parents=True, exist_ok=True)
        if todo[0][0] == "omnivoice":
            _omnivoice_batches(todo, Path(cache), progress)
        else:
            for n, it in enumerate(todo, 1):
                _one(*it)
                if progress:
                    progress(n, len(todo))
    return [it[3] for it in items]


def _one(provider: str, variant: str, text: str, out: Path, fit: float | None, take: int = 0) -> None:
    """One line from `say` or ElevenLabs (both fast enough that batching buys nothing)."""
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        if provider == "elevenlabs":
            raw = Path(tmp) / "raw.mp3"
            raw.write_bytes(_elevenlabs(text, variant))
        else:
            raw = Path(tmp) / "raw.aiff"
            subprocess.run(["say", "-v", variant, "-r", _env("BLOOM_SAY_RATE", "175"), "-o", str(raw), text], check=True)
        work = time.perf_counter() - t0
        _finish(raw, out, fit)
    _learn(provider, variant, work, duration(out))


def _finish(raw: Path, out: Path, fit: float | None) -> None:
    """48 kHz mono, fitted to `fit` seconds if given, written under a temp name first so a failed
    run never leaves a half clip in the cache."""
    af = ["-af", _fit_filter(duration(raw), fit)] if fit else []
    part = out.with_suffix(".part.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), *af, "-ar", "48000", "-ac", "1", str(part)], check=True)
    part.rename(out)


# ---- how long synthesis takes on this machine -----------------------------------------------

SPEED_FILE = Path.home() / ".cache/bloom/speed.json"
# seconds of work per second of speech, measured on an Apple M1, until this machine has timed itself
DEFAULT_RTF = {"omnivoice@32": 4.8, "omnivoice@16": 2.6, "elevenlabs": 0.4, "say": 0.15}
CHARS_PER_SECOND = 15.0  # Thai at a natural narration pace
MODEL_LOAD = 12.0        # seconds to load OmniVoice, once per run


def _speed_key(provider: str, variant: str = "") -> str:
    """Speed depends on the voice too: OmniVoice re-reads the reference clip for every line, so a
    13 s recording of your own voice costs about twice what the 5 s designed voices do."""
    base = f"omnivoice@{_env('BLOOM_OV_STEPS', '32')}" if provider == "omnivoice" else provider
    return f"{base}:{variant}" if variant else base


def _speeds() -> dict:
    try:
        return json.loads(SPEED_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _learn(provider: str, variant: str, work: float, audio: float) -> None:
    """Remember this machine's real speed per voice (a running average), so the next estimate is its own."""
    if audio <= 0:
        return
    speeds, key = _speeds(), _speed_key(provider, variant)
    rtf = work / audio
    speeds[key] = round(0.5 * speeds[key] + 0.5 * rtf if key in speeds else rtf, 3)
    try:
        SPEED_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPEED_FILE.write_text(json.dumps(speeds))
    except OSError:
        pass  # an estimate is a convenience; never fail a build over it


def estimate(texts: list[str], spec: str | None = None) -> float:
    """Seconds this machine needs to synthesize `texts` (pass only the lines not cached yet)."""
    if not texts:
        return 0.0
    provider, variant = resolve(spec)
    speeds, base = _speeds(), _speed_key(provider)
    rtf = speeds.get(_speed_key(provider, variant), speeds.get(base, DEFAULT_RTF.get(base, 4.8)))
    load = MODEL_LOAD if provider == "omnivoice" and not _ov_model.cache_info().currsize else 0.0
    return load + sum(len(t) for t in texts) / CHARS_PER_SECOND * rtf


def fmt_seconds(s: float) -> str:
    s = max(1, round(s))
    return f"{s} s" if s < 90 else f"{s // 60} min {s % 60:02d} s"


def _fit_filter(actual: float, target: float) -> str:
    """Stretch to `target` seconds (no-op within 1 %), then pad/trim to it exactly."""
    tempo = actual / target
    stretch = f"atempo={tempo:.5f}," if abs(tempo - 1) > 0.01 else ""
    return f"{stretch}apad,atrim=0:{target:.3f}"


@functools.cache
def _ov_model():
    # keep library noise out of Bloom's output: torch.distributed's macOS "Redirects" notice is logged
    # while torch imports, so its logger is switched off first (a disabled logger stays silent whatever
    # level torch then sets); Hugging Face's download / weight-loading progress bars go too
    import logging

    logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").disabled = True
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    import torch
    import transformers

    transformers.utils.logging.set_verbosity_error()
    transformers.utils.logging.disable_progress_bar()
    from omnivoice import OmniVoice

    if torch.cuda.is_available():
        return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=torch.float32)


# Lines per GPU pass. On an M1 the GPU is already full with one line: batches of 2/4/8 measured 1.0x/0.85x/0.72x
# the speed of single lines (7 Nov 2026). Batching pays on CUDA cards; set BLOOM_OV_BATCH there.
DEFAULT_BATCH = 1


def _ov_generate(texts: list[str], take: int = 0, **kw) -> list:
    import torch

    torch.manual_seed(int(_env("BLOOM_OV_SEED", "7")) + take)  # same lines + settings + take -> same audio
    speed = _env("BLOOM_OV_SPEED")
    return _ov_model().generate(text=texts, language="th", num_step=int(_env("BLOOM_OV_STEPS", "32")),
                                speed=float(speed) if speed else None, **kw)


def _ov_anchor(instruct: str, cache: Path) -> Path:
    """Design the voice once from the instruct; every line then clones this one take."""
    anchor = cache / f"omnivoice-anchor-{hashlib.sha1(_settings('omnivoice', instruct).encode()).hexdigest()[:16]}.wav"
    if not anchor.exists():
        import soundfile as sf

        sf.write(anchor, _ov_generate([ANCHOR_TEXT], instruct=instruct)[0], 24000)
    return anchor


@functools.cache
def _ov_prompt(variant: str, cache: str, settings: str):
    """The voice's reference, loaded and tokenized once per run; OmniVoice would redo that for
    every line. `settings` only keys the cache, so a re-recorded profile gets a fresh prompt."""
    if variant.startswith("@"):
        ref, text = profile(variant[1:])
    else:
        ref, text = _ov_anchor(variant, Path(cache)), ANCHOR_TEXT
    return _ov_model().create_voice_clone_prompt(ref_audio=str(ref), ref_text=text)


def _empty_gpu_cache() -> None:
    import torch

    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    elif torch.cuda.is_available():
        torch.cuda.empty_cache()


def _omnivoice_batches(todo: list[tuple], cache: Path, progress=None) -> None:
    """Make `todo` lines in GPU batches. Out of memory halves the batch and retries the same lines."""
    import soundfile as sf

    variant = todo[0][1]
    prompt = _ov_prompt(variant, str(cache), _settings("omnivoice", variant))
    todo = sorted(todo, key=lambda it: (it[5], len(it[2])))  # one take per batch (it shares a seed); similar lengths
    size, done = max(1, int(_env("BLOOM_OV_BATCH", str(DEFAULT_BATCH)))), 0
    while done < len(todo):
        chunk = [it for it in todo[done:done + size] if it[5] == todo[done][5]]
        fits = [it[4] for it in chunk]
        t0 = time.perf_counter()
        try:
            audios = _ov_generate([it[2] for it in chunk], take=chunk[0][5], voice_clone_prompt=[prompt] * len(chunk),
                                  duration=fits if any(fits) else None)
        except RuntimeError as e:
            if "out of memory" not in str(e).lower() or size == 1:
                raise
            size //= 2
            _empty_gpu_cache()
            continue
        work = time.perf_counter() - t0
        with tempfile.TemporaryDirectory() as tmp:
            for k, (it, audio) in enumerate(zip(chunk, audios)):
                raw = Path(tmp) / f"raw{k}.wav"
                sf.write(raw, audio, 24000)
                _finish(raw, it[3], it[4])
        _learn("omnivoice", variant, work, sum(len(a) for a in audios) / 24000)
        done += len(chunk)
        if progress:
            progress(done, len(todo))


def _elevenlabs(text: str, model: str) -> bytes:
    if not _env("ELEVENLABS_API_KEY"):
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    voice = _env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": model}).encode(),
        headers={"xi-api-key": _env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as e:  # surface ElevenLabs' own reason (quota, voice, model)
        raise RuntimeError(f"ElevenLabs {e.code}: {e.read().decode(errors='replace')[:300]}") from None


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    )
    return float(out.stdout.strip())
