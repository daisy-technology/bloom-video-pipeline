---
name: bloom-sound
description: Score a Bloom video for impact — decide which sound effect lands on which motion (hit, riser, sting, sparkle, zip, thud, whoosh…), time it with data-sfx tokens like "riser hit@end", place the big moves in the gaps of the voice, direct the voice's delivery with tags ([laughter], [surprise-wa]), and check the master (-14 LUFS, true peak under -1 dBTP) by numbers. Use it whenever a Bloom video needs more punch, impact, sound design, SFX, a better mix or a livelier voice, when someone says the video feels flat, quiet or lifeless, asks "ใส่เสียงให้มันปัง", "เพิ่ม sound effect", "เสียงเบา", "ให้ตัวละครพูดมีอารมณ์", or when building any scenes.html with motion that should be heard.
---

# Bloom sound

You design the sound: what plays, where, and how loud by role. Bloom produces it. It synthesizes every effect and the music (nothing to license, no keys), places the effects from `data-sfx` on the page, ducks the music around them, levels the voice, masters the mix to -14 LUFS, and prints the measured result. This skill is adapted from the `sound` and `motion-direction` skills of [langchain-ai/design-agent](https://github.com/langchain-ai/design-agent) for Bloom's pipeline.

## How a Bloom video gets scored

1. Start from the voice. A Bloom video is cut to its voice: each scene lasts its voice clip plus 0.35 s before and 0.55 s after, and the voice starts 0.35 s into every scene. Work out roughly where the words fall (Thai runs at about 15 characters a second; the build prints each line's pace) and keep the big moves off the important words.
2. Mark every beat while you build the picture. Each move the eye follows gets one sound on the same element, timed by token:

   | `data-sfx` | When |
   |---|---|
   | `pop` | as the element's first animation starts |
   | `hit@end` | as it ends: the landing (all iterations) |
   | `zip@.18 thud@.86` | 0.18 s and 0.86 s into it (a jump: take-off, landing) |
   | `riser sparkle@end` | the riser spans the whole animation and stops on its end; the sparkle starts there |

   **Only an element's first animation times its sounds.** The impact kit (`bloom-character/assets/impact.css`) lists each move's landing animation first, so `hit@end` lands on the contact frame.
3. Preview without voicing. `uv run python .claude/skills/bloom-character/scripts/peek.py scripts/<name>` lists every scene's sounds (`sounds hello: hit @0.30s`) and fails on an unknown effect or a bad token. Compare those times with where the words fall.
4. Build, and read the last lines: `effects: 9 (3 whoosh, 2 hit, …)` and `loudness: -14.0 LUFS, true peak -1.4 dBTP`. If the result is off target, the build says so.
5. Hand over with one line on what you did (where the hits are, what the voice performs). The person's ear decides. You can't listen, so report numbers and never say "sounds good".

## Which sound for which motion

Match the sound to the motion's physics:

| Picture | Effect | Level |
|---|---|---|
| A heavy landing, a slam, a stamp that matters | `hit` (crack, knock, falling body) | loudest |
| The final card, the logo, the one line | `sting` (bright chord over a soft hit) | loud |
| A landing with weight, a jump coming down | `thud` | loud |
| A build into a reveal (charge, zoom, gather) | `riser`, sized to the animation | under the hit it leads to |
| A reveal, something magic, a hat shown off | `sparkle` (rising bells) | quiet |
| A pop-in, a bubble, a small arrival | `pop` | medium |
| Stretch, rise, take-off | `zip` | quiet |
| A fall, an exit | `drop` | quiet |
| A spring, a wobble, squash and stretch | `boing` | medium |
| Letters or items arriving | `blip` (or `tick`) | quietest |
| Typing | `type` with `--n` steps | quietest |
| Scene change | `whoosh`, added by the build, peaking on the cut | n/a |

## Judgment

- Let the voice lead. Put the slam before the first word (the voice starts at 0.35 s), the reveal on a phrase break, and the jump and the closing sting after the last word. If a big hit must sit under speech, move it or use a quieter effect.
- Match the density to the picture. One designed hit per scene is enough; decoration (sparkle, blip) can come more often because it is quiet. Leave silence where the picture rests. A cue on every element is noise, so every cue should trace to a motion you can point at.
- The drop is louder than the build. `bloom/sound.py` sets levels by role (`LEVEL_DB`); don't fight them with more effects. **A riser always leads into something** (`riser hit@end`, `riser sparkle@end`) and never ends in nothing.
- Align sounds by the landing rather than the start. Moves in the impact kit take `--at`, the moment they land, and the sound uses `@end`. Shake the camera (`.shake` on the section) only on a real hit, and let captions stay still (they sit outside the sections).
- The music makes room on its own: the bed dips for a breath before a `hit`, ducks under a `riser`, and stays low under a `sting`/`sparkle`/`chime` tail. There is nothing to set.
- The master is measured: -14 LUFS integrated (±1) and a true peak at or under -1 dBTP on the MP4, which matches what Spotify, YouTube and short-video apps normalize to. Use `--lufs -16` for a quieter delivery and `--lufs off` for the old level.

## The music bed

Pick the style that fits the character, then let the bed sit under the voice: `~chip` (8-bit, for pixel art and game-like characters), `~playful` (marimba and claps, for cute and funny), `~lofi` (soft keys and vinyl, for calm explainers), or `~calm` / `~tense` / `~bright`. Set it per scene in script.md, or for the whole video with `--mood`. To let the person choose, build two or three with `--mood <style> --out output/<style>`. The voice is cached, so each one costs only the render and the mix.

## Music that follows the video

A music file (`--music media/music.mp3`, an Artlist track or your own) can't change its arrangement, so Bloom shapes its level to the story. Each scene sits at its mood's level (`~calm` back, `~bright` full), the last scene drops under the closing question, and the end cut stops it. A spec's draft can place cues on words (`## music` table: `turn@ขาด | drop`, `duck`, `lift`, `stop`). Licensed tracks stay out of git (`scripts/*/media/*.mp3` is ignored); record where they came from in the spec.

## Another voice, same picture

`uv run python .claude/skills/bloom-sound/scripts/revoice.py scripts/<name> --from-voice "<old>" --to-voice "<new>" [--out scripts/<copy>]` moves every timed beat in a hand-written page to the new voice's pace, phrase by phrase (make the new clips first with `--voice-only`). Spec projects don't need it: their beats are written against words and land wherever the voice says them.

To fix a word said wrong (ไฟล์ read as "five"), add it once to Bloom's shared lexicon: `uv run python -m bloom lexicon add --shared "ไฟล์" "ไฟ"`. From the next run, every voice and every video says it that way, the captions keep the real spelling, and only the lines that contain it are voiced again. The `bloom-lexicon` skill has the loop and the respelling patterns.

## The voice for impact

- **Write the performance into the text** where the delivery changes: `[laughter] ดีใจจังเลยค่ะ`, `ว้าว [surprise-wa] สวยมาก`, `[sigh] เหนื่อยจัง`. Use one or two per line. Captions never show them.
- OmniVoice performs `laughter`, `sigh`, `surprise-ah/-oh/-wa/-yo`, `question-ah/-oh/-ei/-yi` and `dissatisfaction-hnn`. ElevenLabs v3 takes free direction (`[excited]`, `[whispers]`). `say` takes none. A tag the voice can't do is dropped with a note and never spoken; ElevenLabs' `[laughs]`/`[sighs]`/`[gasps]` are translated for OmniVoice.
- Try a tagged line before a full build: `uv run bloom say "ดีใจจัง [laughter]" --voice "omnivoice:female, child, high pitch"`. OmniVoice draws a fresh take with `--takes 3`; keep the one that sounds right with `--retake` on the build.
- Pace is a number. The build prints `ch/s` per line and marks `(rushed)` over 19 and `(drags)` under 10. Fix a rushed line by cutting words, not by speeding up the voice.
- The mouth follows the voice. Bloom sets `html[data-mouth]` (0/1/2) per frame from the real audio, and the character's `.talk` / `.talk-half` layers show it, so the mouth rests in pauses and after the line. `.voice-pulse` on the sprite swells it slightly on loud syllables.

## Checklist

- every big move has its sound on the same element, timed with `@end` or seconds, and peek.py lists it where you meant
- no `hit` or `sting` sits on an important word
- one designed hit per scene at most, a sting only on the final card
- the build's loudness line has no "off target"
- tags only where the delivery changes, and only ones the chosen voice performs
