"""Lay voice clips on a timeline, duck an optional music/source bed under them, normalize loudness."""
from __future__ import annotations

import subprocess
from pathlib import Path


def narration(clips: list[tuple[Path, float]], total: float, out: Path, bed: Path | None = None) -> Path:
    """clips = [(wav, start_seconds)]. Writes a stereo 48 kHz WAV exactly `total` seconds long."""
    args = ["ffmpeg", "-v", "error", "-y"]
    for wav, _ in clips:
        args += ["-i", str(wav)]
    graph = [f"[{i}]adelay={int(start * 1000)}:all=1[c{i}]" for i, (_, start) in enumerate(clips)]
    graph.append("".join(f"[c{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[vo]")
    if bed:
        args += ["-stream_loop", "-1", "-i", str(bed)]
        b = len(clips)
        graph += [
            "[vo]asplit[vo][sc]",
            f"[{b}]volume=0.35[bed]",
            "[bed][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[duck]",
            "[vo][duck]amix=inputs=2:normalize=0[vo]",
        ]
    graph.append(f"[vo]apad,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[a]")
    args += ["-filter_complex", ";".join(graph), "-map", "[a]", "-ar", "48000", str(out)]
    subprocess.run(args, check=True)
    return out
