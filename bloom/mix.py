"""Voice clips on a timeline + music ducked under them + sound effects -> one normalized track."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


VOICE_LUFS = -16.0  # how loud the voice ends up
REF_LUFS = -23.0    # every voice is brought here first, so one compressor setting fits them all


def _lufs(probe: list[str], graph: list[str], label: str) -> float:
    """Integrated loudness of `label` in a filter graph, in LUFS: an analysis pass that writes nothing."""
    r = subprocess.run([*probe, "-filter_complex", ";".join([*graph, f"{label}loudnorm=print_format=json[m]"]),
                        "-map", "[m]", "-f", "null", "-"], capture_output=True, text=True, check=True)
    i = float(json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"])
    return i if i > -70 else REF_LUFS  # silence: leave its level alone


def master(clips: list[tuple[Path, float]], total: float, out: Path,
           music: Path | None = None, sfx: Path | None = None) -> Path:
    """clips = [(wav, start_seconds)]. Writes a stereo 48 kHz WAV exactly `total` seconds long.

    The voice is levelled the way a voice-over is mastered: measured, brought to REF_LUFS, compressed in
    two gentle stages (syllable level, then sharp attacks), made up to VOICE_LUFS, and limited only for
    what little is left. One loudnorm pass used to do all of this while riding the gain; OmniVoice's
    peaks sit about 21 dB over its average loudness, so its limiter cut 11% of the speech, by up to
    7 dB, and that was heard as crackle. On the same dub the limiter now touches 2.5%, by at most
    3.6 dB. Music and effects then sit at the same distance under
    the voice in every video: music (generated, or any file, looped) is levelled and ducked by the
    voice; effects play at their own level, undimmed.
    """
    inputs = [x for wav, _ in clips for x in ("-i", str(wav))]
    n = len(clips)
    graph = [f"[{i}]adelay={int(start * 1000)}:all=1[c{i}]" for i, (_, start) in enumerate(clips)]
    graph.append("".join(f"[c{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0[raw]")
    probe = ["ffmpeg", "-hide_banner", "-nostats", *inputs]
    graph.append(f"[raw]volume={REF_LUFS - _lufs(probe, graph, '[raw]'):.2f}dB,"
                 "acompressor=threshold=0.125:ratio=2.5:attack=10:release=150,"  # evens out loud and soft syllables
                 "acompressor=threshold=0.2:ratio=8:attack=0.5:release=40:detection=peak[comp]")  # rounds off sharp attacks
    graph.append(f"[comp]volume={VOICE_LUFS - _lufs(probe, graph, '[comp]'):.2f}dB,"
                 "alimiter=limit=0.79:attack=2:release=60:level=false[vo]")
    args = ["ffmpeg", "-v", "error", "-y", *inputs]
    layers = ["[vo]"]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
        graph += [
            "[vo]asplit[vo][sc]",
            f"[{n}]aformat=channel_layouts=mono,loudnorm=I=-26:TP=-6[bed]",
            "[bed][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=500[duck]",
        ]
        layers.append("[duck]")
        n += 1
    if sfx:
        args += ["-i", str(sfx)]
        layers.append(f"[{n}]")
    graph.append("".join(layers) + f"amix=inputs={len(layers)}:normalize=0,apad,atrim=0:{total:.3f},"
                 "alimiter=limit=0.84:attack=2:release=60:level=false,aformat=channel_layouts=stereo[a]")
    args += ["-filter_complex", ";".join(graph), "-map", "[a]", "-ar", "48000", str(out)]
    subprocess.run(args, check=True)
    return out


def mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    return out
