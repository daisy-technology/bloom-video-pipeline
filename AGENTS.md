# Working on Bloom (for any coding agent)

Bloom turns a Thai script into a finished video. These rules apply to every agent and every person working in this repo: Claude Code, Codex, Cursor, Copilot, Gemini CLI or anything else. `CLAUDE.md` and `GEMINI.md` only point here.

## Setup once per clone

```sh
uv sync && uv run playwright install chromium
git config core.hooksPath .githooks     # the commit hook below
uv run python tests/test_bloom.py       # prints "ok"
```

## Making a video: draft, approval, spec, build

Never start by writing HTML. A video goes through four steps, and the second one belongs to the person:

1. Draft. Run `uv run python -m bloom draft scripts/<name>` (add `--size 1080x1920` for vertical). Fill in `scripts/<name>/draft.md`: the settings, the cast table, each scene's narration (`> …`) and its beats table (`on | do | what | args`), and the music cues. `uv run python -m bloom compose --catalog` lists every component and verb, which is all you need to write a draft.
2. Review. Stop and ask the person to read `draft.md`, and change it until they're happy. **Set `status: approved` only when they say it's approved.**
3. Spec. `uv run python -m bloom spec scripts/<name>` turns the approved draft into `video.toon` and `script.md`. It refuses an unapproved draft and names any line it can't use.
4. Build. `uv run python -m bloom build scripts/<name>` makes the voice, generates `scenes.html` from the spec and the voice's timing, renders, mixes, and writes the MP4, captions and review page to `output/`.

Later changes follow the same path: edit the draft, get approval, run `bloom spec`, build.

## Rules

- **Never edit generated files by hand.** In a spec project, `scenes.html`, `script.md` and `fonts/` come from `video.toon`, and `video.toon` comes from the approved `draft.md`. If something on screen is wrong, fix the draft or the component that drew it.
- **Add what the catalog lacks as a component.** Add it once in `bloom/compose/components.py`, with a test in `tests/test_bloom.py`, so every later video can use it. Don't hand-write it into one page.
- **Land beats on words.** Write `on: ขาด`, not `on: 4.2`, so a new voice or a reworded line never needs re-timing.
- **Fix a word said wrong in the lexicon**, not by rewording the script: `uv run python -m bloom lexicon add --shared "<shown>" "<spoken>"` (ไฟล์ → ไฟ) writes `bloom/lexicon.tsv`, which every machine and agent gets. Captions keep the real spelling, and every later video says the word right. Before voicing a new script, run `uv run python .claude/skills/bloom-lexicon/scripts/scan.py scripts/<name>` to list the words likely to go wrong. The `bloom-lexicon` skill has the whole loop.
- **End every video on a hook:** a question to the viewer, or the next part teased and cut off on the reveal, then `end | cut` or `end | fade`. The music stops with the picture.
- **Leave branding to Bloom.** Every render gets the Bloom and Daisy Technology mark: small and translucent in a corner for the whole video (`--brand daisy`, the default), only in the last 3 seconds (`--brand daisy-end`), or not at all (`--brand none`). Don't draw logos into pages; brand assets live in `bloom/compose/assets/brand/`.
- **Leave banding to Bloom too.** Smooth gradients and soft shadows step into bands in 8-bit video, so every render is debanded in 16 bits and dithered back to 8 before encoding (on by default; `--no-deband` turns it off), and the encoder runs with `aq-mode=3`. Don't add noise or grain to pages yourself.
- **Check before you render.** For any page, generated or hand-written (the older projects in `scripts/`):
  - `uv run python .claude/skills/bloom-motion/scripts/seekcheck.py scripts/<name> --size WxH --voice "<voice>"` must exit 0
  - `uv run python .claude/skills/bloom-visual-audit/scripts/audit.py scripts/<name> --size WxH --voice "<voice>"` must show 0 errors
- **Commit only sources.** Anything Bloom can make again stays out of git: renders (`output/`), caches (`.bloom/`), generated files, sprite sheets cut from renders, voice clips. Licensed or generated audio (Artlist, stock) never goes in the repo; the spec records where it came from.

## The commit hook

`.githooks/pre-commit` runs `uv run python -m bloom guard` on what's staged and refuses:

- audio in a project's `media/`
- generated files
- a `video.toon` that isn't exactly what its approved `draft.md` says
- files over 10 MB outside `docs/`

It applies to everyone who commits, whatever tool they use. Fix the cause instead of skipping the hook with `--no-verify`.

## Where things are

| | |
|---|---|
| `bloom/` | the pipeline: voice, render, sound, mix; `bloom/compose/` turns draft and spec into pages |
| `bloom/compose/assets/` | the runtime kits (motion, iso), fonts, brand |
| `.claude/skills/bloom-*` | the craft guides (story, motion, long take, sound, visual, audit), in plain Markdown that any agent can read |
| `scripts/` | video projects: a spec project keeps only `draft.md`, `video.toon` and its source media |
| `bench/` | comparisons and reports |
| `tests/test_bloom.py` | `uv run python tests/test_bloom.py` prints `ok` |
