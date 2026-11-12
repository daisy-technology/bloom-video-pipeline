"""Voice clips on a timeline + music ducked under them + sound effects -> one mastered track.

The mix is built with the voice at VOICE_LUFS and everything placed against it, then mastered
as a whole to the delivery loudness (DELIVERY_LUFS, -14 LUFS integrated, true peak under
-1 dBTP: what Spotify, YouTube and the short-video apps play back at), and measured on the file
that ships, because a master is measured, not assumed.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


VOICE_LUFS = -18.0  # how loud the voice sits in the mix: 2 dB under -16 leaves its peaks room without squashing
REF_LUFS = -23.0    # every voice is brought here first, so one compressor setting fits them all
DELIVERY_LUFS = -14.0  # the finished file, integrated
TRUE_PEAK = -1.5       # dBTP on the mastered WAV: AAC adds a few tenths, and the delivery ceiling is -1
# Presence for small speakers: rumble off under 70 Hz, a little less boxiness at 300 Hz, 2 dB of
# consonants around 4 kHz. Linear filters only, so they add no distortion (see test_master).
PRESENCE = "highpass=f=70,equalizer=f=300:t=q:w=1:g=-1.5,equalizer=f=4200:t=q:w=1:g=2"


def _lufs(probe: list[str], graph: list[str], label: str) -> float:
    """Integrated loudness of `label` in a filter graph, in LUFS: an analysis pass that writes nothing."""
    r = subprocess.run([*probe, "-filter_complex", ";".join([*graph, f"{label}loudnorm=print_format=json[m]"]),
                        "-map", "[m]", "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace", check=True)
    i = float(json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"])
    return i if i > -70 else REF_LUFS  # silence: leave its level alone


def master(clips: list[tuple[Path, float]], total: float, out: Path,
           music: Path | None = None, sfx: Path | None = None, bed_gain: Path | None = None,
           lufs: float | None = None) -> Path:
    """clips = [(wav, start_seconds)]. Writes a stereo 48 kHz WAV exactly `total` seconds long.

    `bed_gain` is a mono 48 kHz WAV of gains for the music (bloom.sound.gain_curve): the bed dips
    and ducks around the big effects. `lufs` masters the result to that loudness (see `loud`);
    without it the voice ends at VOICE_LUFS.

    The voice is levelled the way a voice-over is mastered: measured, brought to REF_LUFS, compressed
    gently on its loud syllables (10 ms attack), made up to VOICE_LUFS, and limited only for what
    little is left. Both ways this went wrong sounded like a broken microphone. One loudnorm pass rode
    the gain, and with OmniVoice's peaks 21 dB over its average its limiter cut 11% of the speech by up
    to 7 dB. A fast peak compressor (0.5 ms, 8:1) then fixed that but bent every loud wave (2.4%
    distortion on a voice-pitch tone). Now: 0.4% distortion, and the limiter touches 1% of the speech.
    Music and effects then sit at the same distance under
    the voice in every video: music (generated, or any file, looped) is levelled and ducked by the
    voice; effects play at their own level, undimmed.
    """
    inputs = [x for wav, _ in clips for x in ("-i", str(wav))]
    n = len(clips)
    # 48 kHz from the start, so the limiters see the peaks the file will hold (a 24 kHz clip resampled
    # after its limiter came out with peaks 2.8 dB over it, and the final limiter then ate its loudness)
    graph = [f"[{i}]aresample=48000,adelay={int(start * 1000)}:all=1[c{i}]" for i, (_, start) in enumerate(clips)]
    graph.append("".join(f"[c{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,{PRESENCE}[raw]")
    probe = ["ffmpeg", "-hide_banner", "-nostats", *inputs]
    graph.append(f"[raw]volume={REF_LUFS - _lufs(probe, graph, '[raw]'):.2f}dB,"
                 "acompressor=threshold=0.125:ratio=2.5:attack=10:release=150[comp]")  # evens out loud and soft syllables
    graph.append(f"[comp]volume={VOICE_LUFS - _lufs(probe, graph, '[comp]'):.2f}dB,"
                 "alimiter=limit=0.79:attack=5:release=100:level=false[vo]")
    # Two passes, every input of the second a finite file `total` long. One graph that split the voice
    # into the mix and the ducking key, with a looping bed, stalled about one run in two (ffmpeg 9,
    # Nov 2026): it spun at full CPU and never ended. Reading the voice twice needs no split at all.
    vo_file, bed_file = out.with_name(out.stem + ".voice.wav"), out.with_name(out.stem + ".bed.wav")
    graph.append(f"[vo]apad=whole_dur={total:.3f},atrim=0:{total:.3f}[v]")
    _ff(["-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[v]", "-ar", "48000",
         "-c:a", "pcm_f32le", str(vo_file)], total)
    args, layers, mix_graph, n = ["-v", "error", "-y", "-i", str(vo_file)], ["[0]"], [], 1
    if music:
        _ff(["-v", "error", "-y", "-stream_loop", "-1", "-i", str(music), "-t", f"{total:.3f}",
             "-ac", "1", "-ar", "48000", "-c:a", "pcm_f32le", str(bed_file)], total)
        mono = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono"
        args += ["-i", str(vo_file), "-i", str(bed_file)]  # the voice again: the key that ducks the bed
        mix_graph.append(f"[2]loudnorm=I=-26:TP=-6,aresample=48000,{mono}[bed]")
        n = 3
        if bed_gain:  # the bed makes room for the big effects
            args += ["-i", str(bed_gain)]
            mix_graph.append(f"[{n}]{mono}[gain];[bed][gain]amultiply[bed2]")
            n += 1
        mix_graph.append(f"[{'bed2' if bed_gain else 'bed'}][1]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=500[duck]")
        layers.append("[duck]")
    if sfx:
        args += ["-i", str(sfx)]
        layers.append(f"[{n}]")
    mix_graph.append("".join(layers) + f"amix=inputs={len(layers)}:normalize=0,apad=whole_dur={total:.3f},atrim=0:{total:.3f},"
                     "alimiter=limit=0.84:attack=5:release=100:level=false,aformat=channel_layouts=stereo[a]")
    mixed = out.with_name(out.stem + ".premaster.wav") if lufs is not None else out
    try:
        _ff([*args, "-filter_complex", ";".join(mix_graph), "-map", "[a]", "-ar", "48000", str(mixed)], total)
    finally:
        vo_file.unlink(missing_ok=True)
        bed_file.unlink(missing_ok=True)
    if lufs is not None:
        loud(mixed, out, lufs)
        mixed.unlink()
    return out


def _ff(args: list[str], total: float) -> None:
    """ffmpeg, with a deadline: a stalled graph fails the build instead of hanging it."""
    subprocess.run(["ffmpeg", *args], check=True, timeout=max(120.0, total * 4))


def measure(path: Path) -> dict:
    """{"i": integrated LUFS, "tp": true peak dBTP, "lra": LU} of a file's audio, from ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace", check=True)
    summary = r.stderr[r.stderr.rfind("Summary:"):]

    def num(pattern: str) -> float:
        m = re.search(pattern, summary)
        return float(m.group(1)) if m and m.group(1) != "-inf" else float("-inf")

    return {"i": num(r"I:\s*(-?[\d.]+|-inf)\s*LUFS"), "lra": num(r"LRA:\s*(-?[\d.]+)\s*LU"),
            "tp": num(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS")}


def loud(src: Path, out: Path, lufs: float = DELIVERY_LUFS, true_peak: float = TRUE_PEAK) -> dict:
    """Master `src` to `lufs` integrated: one gain for the whole file, so the mix keeps its dynamics,
    and a 4x-oversampled limiter that only shaves the few peaks the gain pushes past `true_peak`.
    (A dynamic loudnorm rides the gain instead, and on a voice that sounded like a broken microphone.)
    Returns the measurement of the input."""
    m = measure(src)
    gain = lufs - m["i"] if m["i"] > -70 else 0.0  # silence: nothing to bring up
    limit = 10 ** (true_peak / 20)
    for _ in range(3):  # a mix that is mostly peaks loses loudness to the limiter: give that back and go again
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af",
                        f"volume={gain:.2f}dB,aresample=192000,alimiter=limit={limit:.4f}:attack=1:release=60:level=false,"
                        "aresample=48000", "-ar", "48000", str(out)], check=True)
        got = measure(out)["i"] if gain else lufs
        if abs(got - lufs) <= 0.5:
            break
        gain += lufs - got
    return m


def report(path: Path, lufs: float = DELIVERY_LUFS) -> tuple[dict, bool]:
    """The delivered file's loudness, and whether it is on target: within 1 LU, true peak at or under -1 dBTP."""
    m = measure(path)
    return m, abs(m["i"] - lufs) <= 1.0 and m["tp"] <= -1.0


def mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    return out
