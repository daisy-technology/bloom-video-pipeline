"""How the voice says what the text shows: one lexicon Bloom remembers for every video.

A lexicon is a TSV, one `shown<TAB>spoken` pair per line (# for comments):

    API	เอพีไอ
    บางขุนเทียน	บาง ขุน เทียน

Every dub and build reads three layers, each overriding the one before on the same shown text:
Bloom's shared lexicon (bloom/lexicon.tsv, in the repo: corrections every machine, person and agent
gets), the person's global lexicon (~/.bloom/lexicon.tsv), and a project lexicon when there is one
(`dub --lexicon`, or lexicon.tsv next to a script.md). This is how Bloom learns: OmniVoice can't be retrained, but a word fixed here once is
said right in every later video, and only the lines containing it are voiced again.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import thainum, voice

HEADER = "# How the voice says what the text shows: one shown<TAB>spoken per line; the longest match wins."
THAI_ONLY = re.compile(r"[฀-๿]+")
THAI_CHAR = "[฀-๿]"
TAG = re.compile(r"\[[a-z][a-z, -]*\]")  # a delivery tag (bloom/script.py): the voice performs it
ENGLISH_WORDS = re.compile(r"[A-Za-z.][A-Za-z .\-]*")  # letters only: a code with digits keeps its spaces


SHARED = Path(__file__).parent / "lexicon.tsv"  # versioned with Bloom: fixes that hold for every voice


def global_path() -> Path:
    return voice.home() / "lexicon.tsv"


def read(path: Path | None) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    entries = {}
    for row in Path(path).read_text(encoding="utf-8").splitlines():
        if "\t" in row and not row.startswith("#"):
            shown, spoken = (x.strip() for x in row.split("\t", 1))
            if shown:
                entries[shown] = spoken
    return entries


def load(*paths: Path | None) -> list[tuple[str, str]]:
    """Bloom's shared lexicon, the global one, then each path in turn (a later file wins on the same shown),
    longest shown first."""
    merged: dict[str, str] = {}
    for path in (SHARED, global_path(), *paths):
        merged.update(read(path))
    return sorted(merged.items(), key=lambda kv: -len(kv[0]))


def _joined(m: re.Match, spoken: str) -> str:
    """The ทับศัพท์ in place of the English word: joined to Thai, but kept apart from a Latin letter or a
    sign it was written against, so the two don't fuse."""
    before = m.string[m.start() - 1:m.start()] if m.start() else ""
    return f" {spoken} " if before and not before.isspace() and not re.match(THAI_CHAR, before) else spoken


def apply(text: str, pairs: list[tuple[str, str]]) -> str:
    """What the voice should say for `text`: lexicon first, then numbers (baht, codes) as Thai words.
    Delivery tags ([laughter]) pass through untouched: each stands aside as one private-use character."""
    tags = [m.group(0) for m in TAG.finditer(text)]
    if tags:
        it = iter(range(len(tags)))
        text = TAG.sub(lambda m: chr(0xE000 + next(it)), text)
        said = _apply(text, pairs)
        return re.sub("[\ue000-\ue0ff]", lambda m: tags[ord(m.group(0)) - 0xE000], said)
    return _apply(text, pairs)


def _apply(text: str, pairs: list[tuple[str, str]]) -> str:
    for shown, spoken in pairs:
        if THAI_ONLY.fullmatch(shown):  # a Thai word respelt in place (เลขที่ -> เลข ที่): no pauses around it
            text = text.replace(shown, spoken)
            continue
        if ENGLISH_WORDS.fullmatch(shown) and THAI_ONLY.fullmatch(spoken.replace(" ", "")):
            # an English word said in Thai script (ทับศัพท์, Excel -> เอ็กเซล): the spaces written around it in
            # Thai text are only there because of the Latin letters, and said aloud they are pauses, so it
            # joins the Thai on either side ("เลือกไฟล์เอ็กเซลที่…"). A space before a number stays
            text = re.sub(f"(?:(?<={THAI_CHAR}) )?{re.escape(shown)}(?: (?={THAI_CHAR}))?", lambda m, s=spoken: _joined(m, s), text)
            continue
        # a foreign term or abbreviation gets spaces so it doesn't fuse with the Thai around it. A space
        # is a pause in Thai, though, so none between a name and the number it names (ทร.03-07 is
        # "ทอ รอ ศูนย์สามศูนย์เจ็ด", not "ทอ รอ … ศูนย์สาม")
        text = re.sub(re.escape(shown), lambda m, s=spoken: f" {s}" + ("" if m.string[m.end():m.end() + 1].isdigit() else " "), text)
    # brackets, and dashes between words; a hyphen inside a word or number stays (Wi-Fi, 03-07):
    # the voice says a hyphenated word as written, not as two separate words
    text = re.sub(r"(\d)\s+-\s+(\d)", r"\1 ถึง \2", text)  # a range: ข้อ 2 - 9 -> ข้อ สอง ถึง เก้า
    text = re.sub(r"[()\[\]_]|(?<!\w)-|-(?!\w)", " ", text)  # an underscore is never said
    return re.sub(r"\s+", " ", thainum.spell(text)).strip()


def add(shown: str, spoken: str, path: Path | None = None) -> Path:
    path = Path(path) if path else global_path()
    entries = read(path)
    entries[shown.strip()] = spoken.strip()
    _write(path, entries)
    return path


def remove(shown: str, path: Path | None = None) -> bool:
    path = Path(path) if path else global_path()
    entries = read(path)
    if entries.pop(shown.strip(), None) is None:
        return False
    _write(path, entries)
    return True


def _write(path: Path, entries: dict[str, str]) -> None:
    """Keep the file's own comments, rewrite the pairs, and swap the file in whole (never half-written)."""
    comments = [r for r in path.read_text(encoding="utf-8").splitlines() if r.startswith("#")] \
        if path.exists() else [HEADER]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(comments + [f"{s}\t{t}" for s, t in entries.items()]) + "\n", encoding="utf-8")
    tmp.replace(path)
