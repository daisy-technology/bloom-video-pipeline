---
name: bloom-story-cast
description: Cast a Bloom video story — choose the visual style, the character, the narrator's voice, the font and the music so they tell the same story the same way, and make up to three contrasting versions (e.g. emergency news broadcast, glitch documentary, pixel survival diary) to compare. Use it when someone asks for "หลายแบบ", "3 เวอร์ชัน", "เปลี่ยนสไตล์/ตัวละคร/เสียง", "which voice fits", "make versions to compare", or as step 4 of bloom-story.
---

# Story cast

A version is five choices that must agree: style (palette, layout, motion), character (who is on screen), voice (who speaks), music (the bed's mood) and font. A grandpa's voice reads as a mistake on a neon glitch page and as a story in a grandpa's living room.

## Archetypes that work

| Version | Style | Character | Voice (`--voice`) | Music (`--mood`) | Font |
|---|---|---|---|---|---|
| Emergency broadcast | red/black, ticker, "BREAKING", hard cuts, shake on hits | an anchor or a worried mascot at a desk | `omnivoice:male, middle-aged, low pitch` | `tense` | Kanit / Prompt (bold) |
| Glitch documentary | dark navy, data lines, map and cable diagrams, glitch on cuts | an object as narrator (a router, a satellite, a cable) | `omnivoice:female, young adult` | `lofi` or `calm` | Mitr / Chonburi titles |
| Pixel survival diary | 8-bit room, day counter, small objects failing | a kid, a pet or a mascot living through it | `omnivoice:male, child, high pitch` or `female, child, high pitch` | `chip` | Mali / Itim |
| Warm explainer | pastel, rounded cards | a friendly animal | `omnivoice:female, young adult` | `playful` or `bright` | Mali / Kodchasan |
| Grandparent's story | sepia, photos, slow pushes | an elderly character | `omnivoice:male, elderly, low pitch` | `calm` | Sriracha |

Characters are original pixel sprites (`bloom-character`) with one silhouette, one signature accessory and a palette of 6–10 colours. The script's particles match the voice: ครับ for a man or a boy, ค่ะ for a woman or a girl, none for a newsreader.

## Three versions to compare

1. Keep **the same facts and the same beats** (same `research.md`, same ladder). The narration may change person and register (a kid's diary says "หนู/ผม"), but not what it claims.
2. Set the versions far apart on every axis: style, character, voice gender and age, music mood, font. Two versions that differ only in colour give nothing to compare.
3. Give each version its own project folder `scripts/<topic>-<style>/` with `script.md`, `scenes.html` and `fonts/`, and put the exact build command in a comment at the top of script.md.
4. Voice on a GPU when there is one: `uv run bloom build scripts/<topic>-<style> --voice "<voice>" --mood <mood> --on <remote>` (`uv run bloom remote list`). Three projects with `--on` run one after another on the remote, or you can use `bloom batch`-style sequencing. The voice takes most of the time.

## Picture checklist per version

- every beat is acted out with a prop from `bloom-story/assets/props.*` (or a new one added to the kit), its result landing on the words (`when.py`), and the character reacting (a face, a shake). The prop is the event, and the character watches it happen
- with props on screen the character steps aside (smaller, at the edge or below the prop) and returns to full size for the hook and the ending

- the hook frame reads with the sound off (big text, one image)
- sources are visible in each factual scene (`.src`, small, at the bottom, above the caption)
- one big move per scene, in a gap of the voice (see Impact in `bloom-character`)
- `peek.py` passes, and its sheet looks like the style named here
