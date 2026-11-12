---
name: bloom-lexicon
description: Fix how Bloom's voice says a word, once, for every voice and every later video — find words the Thai voice will say wrong (English loanwords with a silent letter like ไฟล์ read as "five", English words spelled out letter by letter, abbreviations like น. read as นาฬิกา), try a respelling with `bloom say`, and keep the fix in the right lexicon (Bloom's shared one in the repo, the person's own, or the project's) so the captions keep the real spelling and only the lines that contain the word are voiced again. Use it whenever someone says a word is pronounced wrong — "อ่านผิด", "ออกเสียงผิด", "พากย์เพี้ยน", "คำนี้ไม่ใช่", "X ไม่ใช่ Y", "ไฟล์ ไม่ใช่ five", "mispronounced", "says it wrong", "pronunciation" — when a build's Whisper check or review page flags a line, and before voicing any new script that has loanwords, English or abbreviations.
---

# Bloom lexicon

OmniVoice can't be retrained, but it reads whatever text it's given, and the lexicon changes that text. A word the voice says wrong is respelled for the voice only, so the captions still show the real word. One fix covers every voice and every later video, and only the lines that contain the word are voiced again.

## Three layers

For the same word, each layer overrides the one before it:

| Layer | File | Use it for | How |
|---|---|---|---|
| Shared | `bloom/lexicon.tsv` (in the repo) | a general Thai fix any voice needs (ไฟล์ → ไฟ). Every machine, person and agent gets it once it's committed | `uv run python -m bloom lexicon add --shared "<shown>" "<spoken>"` |
| Personal | `~/.bloom/lexicon.tsv` | a preference of this person's only | `… lexicon add "<shown>" "<spoken>"` |
| Project | `scripts/<name>/lexicon.tsv` | a name or term in one video (a person, a shop) | `… lexicon add --file scripts/<name>/lexicon.tsv …` |

**Default to the shared layer**, because a word one voice says wrong is usually wrong in the others too. Add a comment line above the entry in `bloom/lexicon.tsv` saying what went wrong (`# ไฟล์ was read as "five"`).

To choose between the lexicon and `{shown|spoken}`: use the lexicon for a word that should always be said one way, and `{shown|spoken}` in the script for one place where the reading depends on context: a year versus an amount (`{2012|สองพันสิบสอง}`), a code, one abbreviation in one sentence.

## The loop

1. Find the word.
   - The person tells you ("ไฟล์ ไม่ใช่ Five"): that's the word.
   - Before voicing a new script, run the scanner. It lists English loanwords with a silent letter, English words and abbreviations that no lexicon or `{shown|spoken}` covers yet, each with a respelling to try:
     ```sh
     uv run python .claude/skills/bloom-lexicon/scripts/scan.py scripts/<name>
     ```
   - After a build, open `output/<name>.review.html`. Whisper writes loanwords in English letters ("Bloom", "Render"), which is not an error. A dropped syllable ("ลูมเป็น" for "บลูมเป็น") or a different word is.
2. Respell it with the patterns below.
3. Hear it in the video's voice, two takes. Only the person can judge by ear; Whisper's CER is a hint, not a verdict.
   ```sh
   uv run python -m bloom say "<the line, with the respelling>" --voice "<the video's voice>" --takes 2
   ```
4. Keep it: `bloom lexicon add --shared "<shown>" "<spoken>"`, plus the comment line explaining it.
5. Rebuild.
   - Only the lines containing the word are voiced again.
   - A spec project lands its beats on words, so it stays in sync by itself.
   - For a hand-written page, re-run seekcheck, the audit and `when.py`, since the line's length may change slightly.

## Respelling Thai for the voice

| Problem | Example | Respell |
|---|---|---|
| English loanword with a silent final letter, read aloud or with the wrong tone | ไฟล์ read as "five" or ไฟล้ | drop the silenced letter: ไฟล์ → ไฟ, สไลด์ → สไล, ไลน์ → ไล, ซอร์ส → ซอส, โฟร์ → โฟ |
| English in Latin letters, spelled out | Excel, OmniVoice | its Thai spelling: เอ็กเซล, ออมนิวอยซ์; an acronym letter by letter: API → เอพีไอ |
| Abbreviation with a dot, read as a word | น. → นาฬิกา, ก.ค. | the full word (นาฬิกา only when it means o'clock), or `{shown|spoken}` |
| Wrong tone on a loanword | ไฟล้ | write out the tone you hear in the word: add or change the tone mark in the spoken form |
| A long name run together | บางขุนเทียน | space the syllables: บาง ขุน เทียน |
| Numbers | 1,250 · 22.19 | nothing: Bloom spells amounts out itself; codes and years go in `{shown|spoken}` |

Sanskrit-style silent letters in native words (พากย์, อารมณ์, สัปดาห์, อาทิตย์) are already said well, and the scanner leaves them alone.

## Rules

- **Never change what's shown**: captions keep the correct spelling, and only the spoken side changes.
- One fix per word, in the right layer. Don't fix the same word in a project and in the shared file.
- A respelling that sounds right in one voice and wrong in another goes back to the person. Tell them, and keep it in the voice's project lexicon instead of the shared one.
