"""Voice clips on a timeline + music ducked under them + sound effects -> one normalized track."""
from __future__ import annotations

import subprocess
from pathlib import Path


def master(clips: list[tuple[Path, float]], total: float, out: Path,
           music: Path | None = None, sfx: Path | None = None) -> Path:
    """clips = [(wav, start_seconds)]. Writes a stereo 48 kHz WAV exactly `total` seconds long.

    The voice is normalized first, so music and effects sit at the same distance under it in
    every video. Music (generated, or any file, looped) is levelled and ducked by the voice;
    effects play at their own level, undimmed.
    """
    args = ["ffmpeg", "-v", "error", "-y"]
    for wav, _ in clips:
        args += ["-i", str(wav)]
    n = len(clips)
    graph = [f"[{i}]adelay={int(start * 1000)}:all=1[c{i}]" for i, (_, start) in enumerate(clips)]
    graph.append("".join(f"[c{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0,loudnorm=I=-16:TP=-2:LRA=7[vo]")
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
    graph.append("".join(layers) + f"amix=inputs={len(layers)}:normalize=0,"
                 f"apad,atrim=0:{total:.3f},alimiter=limit=0.9,loudnorm=I=-16:TP=-1.5:LRA=11,"
                 "aformat=channel_layouts=stereo[a]")
    args += ["-filter_complex", ";".join(graph), "-map", "[a]", "-ar", "48000", str(out)]
    subprocess.run(args, check=True)
    return out


def mux(video: Path, audio: Path, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    return out
