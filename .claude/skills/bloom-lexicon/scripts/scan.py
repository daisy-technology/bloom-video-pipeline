"""List the words a Thai voice is likely to say wrong in a script, before anything is voiced.

    uv run python .claude/skills/bloom-lexicon/scripts/scan.py scripts/<project> [--voice "<voice>"]

Reads script.md (or a spec project's), skips what the lexicons (shared, global, project) and {shown|spoken}
already cover, and prints each risky word with why, a respelling to try, and the `bloom say` line that
tries it. Risky: a loanword with a silent letter (ไฟล์, ฟิล์ม: TTS may read the silenced letter or the wrong
tone), an English word (spelled out letter by letter), a Thai abbreviation with a dot (น. is read นาฬิกา).
Numbers aren't listed: Bloom spells them out itself.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from bloom import lexicon, script  # noqa: E402

SILENT = re.compile(r"[ก-ฮ][ิุ]?์")  # one consonant (and its vowel) silenced by ์: ไฟล์ → ไฟ, สไลด์ → สไล
# English loanwords silence a final consonant (ไฟล์, สไลด์, ไลน์, ซอร์ส); Sanskrit-style silent letters
# (พากย์, อารมณ์, สัปดาห์) are native words the voice already says well, so they aren't listed
LOAN = re.compile(r"[ลดรนสตคกฟซมบพ][ิุ]?์")
ENGLISH = re.compile(r"\b[A-Za-z][A-Za-z.+#-]*[A-Za-z+#]\b|\b[A-Za-z]\b")
ABBREV = re.compile(r"(?:[ก-ฮ]\.){1,3}")


def words(lines: list[str]) -> list[list[str]]:
    """Thai has no spaces between words: split each line with Chromium's word segmenter (Intl.Segmenter)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        out = b.new_page().evaluate("""ls => { const s = new Intl.Segmenter('th', {granularity: 'word'});
            return ls.map(l => [...s.segment(l)].filter(x => x.isWordLike).map(x => x.segment)); }""", lines)
        b.close()
    return out


def risky(text: str, tokens: list[str], covered: set[str]) -> list[tuple[str, str, str]]:
    """(word, why, respelling to try) for one line of narration, after {shown|spoken} and the lexicons."""
    said = text  # what the voice will be asked to say: {shown|spoken} already resolved to the spoken side
    out, seen = [], set()
    for w in tokens:
        if not LOAN.search(w) or w in seen or w not in said or any(c in w for c in covered):
            continue
        seen.add(w)
        out.append((w, "English loanword with a silent letter: the voice may read it (ไฟล์ → \"five\") or miss the tone", SILENT.sub("", w)))
    for m in ENGLISH.finditer(said):
        w = m.group(0)
        if w in seen or w in covered:
            continue
        seen.add(w)
        out.append((w, "English: spelled out letter by letter", "its Thai spelling (ทับศัพท์), e.g. Excel → เอ็กเซล"))
    for m in ABBREV.finditer(said):
        w = m.group(0)
        if w not in seen and w not in covered:
            seen.add(w)
            out.append((w, "abbreviation: read as a word (น. → นาฬิกา)", "the full word, or {shown|spoken} where it appears"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--voice", default="omnivoice:female, young adult, very high pitch", help="the voice to try fixes in")
    a = ap.parse_args()
    covered = {shown for shown, _ in lexicon.load(a.project / "lexicon.tsv")}
    found = 0
    scenes = script.parse(a.project / "script.md")
    spoken = [script.untagged(s["speech"]) for s in scenes]  # the voice's text, not the captions
    for s, said, tokens in zip(scenes, spoken, words(spoken)):
        for word, why, try_ in risky(said, tokens, covered):
            found += 1
            line = s["text"] if len(s["text"]) < 60 else s["text"][:57] + "…"
            print(f"{s['id']:<10} {word:<14} {why}\n{'':<10} try: {try_}\n"
                  f"{'':<10} hear it: uv run python -m bloom say \"{line.replace(word, try_ if ' ' not in try_ else word)}\" "
                  f"--voice \"{a.voice}\" --takes 2\n")
    print(f"{found} word(s) to check" if found else "nothing risky: every word is plain Thai or already in a lexicon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
