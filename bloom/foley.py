"""Automatic foley: sound-effect cues read off a rendered video, for pictures Bloom didn't draw.

Bloom's own pages say where their effects go (data-sfx). A video from another tool doesn't, so
this watches the picture instead: per frame, how many pixels changed. Something starting to
move after a still moment is an entrance or a transition, sized into whoosh / swish / pop / tick.
A run of tiny changes is typing, one key click per changed frame. Known scene cuts get their
own whoosh from the build, so detected cues right next to a cut are dropped and never stack.
Given the caption times, the rows where captions change are found and ignored, so a caption
swapping lines makes no sound.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

W, H = 270, 480      # analysis size: a typed character is still visible, and diffing stays cheap
N = W * H
THRESH = 24          # a pixel changed when it moves more than this (0-255); below is codec noise
NOISE = 6            # changed pixels under this count as a still frame
TYPE_PX = 400        # a typed character or two changes fewer pixels than this
SIZES = ((0.30 * N, "whoosh"), (0.05 * N, "swish"), (0.008 * N, "pop"), (0, "tick"))
GAP = 0.15           # seconds between two detected cues, at least
CUT_GUARD = 0.35     # no detected cue this close to a known scene cut
WHOOSH_LEAD = 0.25   # a whoosh starts this early so it peaks with the motion
MAX_TYPING = 2.5     # tiny changes going on longer than this are idle motion (a bobbing mascot), not typing


def _frames(video: Path):
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={W}:{H},format=gray",
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    while len(chunk := proc.stdout.read(N)) == N:
        yield np.frombuffer(chunk, np.uint8).astype(np.int16)
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg could not decode {video}")


def caption_rows(video: Path, times: list[float], fps: float = 30) -> np.ndarray:
    """Boolean mask of the rows where captions change: rows that change at most caption switches."""
    at = {f for t in times for f in (int(t * fps), int(t * fps) + 1)}
    hits, prev = np.zeros(N, int), None
    for k, frame in enumerate(_frames(video)):
        if prev is not None and k in at:
            hits += np.abs(frame - prev) > THRESH
        prev = frame
    rows = ((hits >= max(2, 0.3 * len(times))).reshape(H, W).mean(axis=1) > 0.02)
    rows = np.convolve(rows, np.ones(13), mode="same") > 0  # pad the band by 6 rows each side
    return np.repeat(rows, W)


def changes(video: Path, ignore: np.ndarray | None = None) -> np.ndarray:
    """Changed-pixel count per frame at analysis size (frame 0 counts as 0), outside `ignore`."""
    keep = ~ignore if ignore is not None else slice(None)
    counts, prev = [0], None
    for frame in _frames(video):
        if prev is not None:
            counts.append(int(np.count_nonzero((np.abs(frame - prev) > THRESH)[keep])))
        prev = frame
    return np.array(counts)


def detect(video: Path, fps: float = 30, cuts: tuple[float, ...] = (), captions: list[float] = ()) -> list[dict]:
    """Sound-effect cues [{"sfx", "t"}] for `video`. Nothing within CUT_GUARD of `cuts`; caption rows,
    found from the caption switch times in `captions`, are ignored."""
    px = changes(video, caption_rows(video, list(captions), fps) if len(captions) >= 3 else None)

    def still(k: int) -> bool:
        return k >= len(px) or px[k] < NOISE

    def surge(k: int) -> bool:  # something big arriving even while other things move
        return px[k] > 0.05 * N and px[k] > 4 * px[k - 1]

    cues, last, i = [], -1.0, 1
    while i < len(px):
        if not (surge(i) or (px[i] >= NOISE and all(still(k) for k in range(max(0, i - 3), i)))):
            i += 1
            continue
        t, peak = i / fps, int(px[i:i + 6].max())
        if peak <= TYPE_PX:  # small: typing if it keeps going, else a lone tick
            j, keys = i, []
            while j < len(px) and px[j] <= TYPE_PX and not (still(j) and still(j + 1)):
                if px[j] >= NOISE:
                    keys.append(j / fps)
                j += 1
            if len(keys) >= 4 and keys[-1] - keys[0] <= MAX_TYPING:
                cues += [{"sfx": "click", "t": k} for k in keys]
            elif peak >= 60 and t - last >= GAP:
                cues.append({"sfx": "tick", "t": t})
                last = t
            i = j + 1
            continue
        name = next(n for size, n in SIZES if peak >= size)
        if t - last >= GAP:
            cues.append({"sfx": name, "t": t - (WHOOSH_LEAD if name == "whoosh" else 0.0)})
            last = t
        j = i + 1  # one cue per burst of motion, unless something big surges in mid-way
        while j < len(px) and not (still(j) and still(j + 1) and still(j + 2)) and not surge(j):
            j += 1
        i = max(j, i + 1)
    return [c for c in cues if all(abs(c["t"] - cut) > CUT_GUARD for cut in cuts)]
