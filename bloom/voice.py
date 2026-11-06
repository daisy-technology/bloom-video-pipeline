"""Text -> speech.

Pick a voice with `--voice <provider>[:<variant>]` (or BLOOM_VOICE):

  omnivoice[:<instruct>]   default. k2-fsa/OmniVoice, runs locally (Apple Silicon, CUDA or CPU), free.
                           Model weights are CC-BY-NC: non-commercial use only.
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
import urllib.error
import urllib.request
from pathlib import Path

PROVIDERS = ("omnivoice", "elevenlabs", "say")

# OmniVoice: every scene clones one reference voice, so the voice stays the same across scenes.
# Without BLOOM_OV_REF, that reference is designed once from BLOOM_OV_INSTRUCT and cached.
ANCHOR_TEXT = "วันนี้มีเรื่องสั้น ๆ มาเล่าให้ฟัง ฟังจบแล้วเอาไปใช้ได้เลย"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


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
    default = {"omnivoice": _env("BLOOM_OV_INSTRUCT", "female"),
               "elevenlabs": _env("ELEVENLABS_MODEL_ID", "eleven_v3"),
               "say": _env("BLOOM_SAY_VOICE", "Kanya")}[provider]
    return provider, variant or default


def _settings(provider: str, variant: str) -> str:
    """Everything besides the text that changes the audio; part of the cache key."""
    if provider == "omnivoice":
        ref = _env("BLOOM_OV_REF")
        ref_id = f"{ref}:{os.path.getsize(ref)}:{os.path.getmtime(ref)}" if ref else ANCHOR_TEXT
        return f"{variant}|{ref_id}|{_env('BLOOM_OV_REF_TEXT')}|{_env('BLOOM_OV_STEPS', '32')}|{_env('BLOOM_OV_SPEED')}"
    if provider == "elevenlabs":
        return f"{variant}|{_env('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')}"
    return f"{variant}|{_env('BLOOM_SAY_RATE', '175')}"


def synth(text: str, cache: Path, spec: str | None = None) -> Path:
    """Speak `text`, return a 48 kHz mono WAV path inside `cache`."""
    provider, variant = resolve(spec)
    key = hashlib.sha1(f"{provider}|{_settings(provider, variant)}|{text}".encode()).hexdigest()[:16]
    out = Path(cache) / f"{provider}-{key}.wav"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        if provider == "omnivoice":
            _omnivoice(text, variant, raw, Path(cache))
        elif provider == "elevenlabs":
            raw = raw.with_suffix(".mp3")
            raw.write_bytes(_elevenlabs(text, variant))
        else:
            raw = raw.with_suffix(".aiff")
            subprocess.run(["say", "-v", variant, "-r", _env("BLOOM_SAY_RATE", "175"), "-o", str(raw), text], check=True)
        # write to a temp name first so a failed run never leaves a half clip in the cache
        part = out.with_suffix(".part.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "48000", "-ac", "1", str(part)], check=True)
        part.rename(out)
    return out


@functools.cache
def _ov_model():
    import torch
    from omnivoice import OmniVoice

    if torch.cuda.is_available():
        return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=torch.float32)


def _ov_generate(**kw):
    import torch

    torch.manual_seed(int(_env("BLOOM_OV_SEED", "7")))  # same text + settings -> same take
    speed = _env("BLOOM_OV_SPEED")
    return _ov_model().generate(language="th", num_step=int(_env("BLOOM_OV_STEPS", "32")),
                                speed=float(speed) if speed else None, **kw)[0]


def _omnivoice(text: str, instruct: str, out: Path, cache: Path) -> None:
    import soundfile as sf

    ref, ref_text = _env("BLOOM_OV_REF"), _env("BLOOM_OV_REF_TEXT")
    if ref and not ref_text:
        raise ValueError("BLOOM_OV_REF needs BLOOM_OV_REF_TEXT: the exact words spoken in the reference clip")
    if not ref:
        anchor = cache / f"omnivoice-anchor-{hashlib.sha1(_settings('omnivoice', instruct).encode()).hexdigest()[:16]}.wav"
        if not anchor.exists():
            sf.write(anchor, _ov_generate(text=ANCHOR_TEXT, instruct=instruct), 24000)
        ref, ref_text = str(anchor), ANCHOR_TEXT
    sf.write(out, _ov_generate(text=text, ref_audio=ref, ref_text=ref_text), 24000)


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
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
