---
name: bloom-story
description: Turn a topic, a question or no idea at all into a Bloom video story — find the angle, check it against real research, shape it into a hook-to-payoff script.md, and cast it (visual style, character, voice, music) in up to three contrasting versions to compare. Use it whenever someone wants to make a video but needs an idea or a story, asks "ช่วยคิดเรื่อง", "อยากทำคลิปเรื่อง…", "ทำเป็นเรื่องเล่า", "เขียนสคริปต์ให้หน่อย", "make it shocking / emotional / funny", "what if…", "based on real research", or wants several versions of one story to choose from. It routes to the sub-skills bloom-story-idea, bloom-story-research, bloom-story-structure, bloom-story-cast and bloom-story-review.
---

# Bloom story

A Bloom video is a story told to a voice: `script.md` is what is said, and `scenes.html` is what is seen. This skill takes a spark to a script worth voicing before anyone spends minutes of GPU on it. It borrows the workflow of [story-skills](https://github.com/danjdewhurst/story-skills) (premise workshop, research ledger, plot structure, reader panel) and the storytelling skills listed in Indeed's career guide (directness, attention to detail, empathy, creativity, editing, timing, humour…), cut down to what a 30–90 second vertical video needs.

The person owns the story. Offer options and tests, ask when a choice is theirs, and never present invention as fact.

## The pipeline

| Step | Sub-skill | Output (in the project folder) |
|---|---|---|
| 1. Find the story | `bloom-story-idea` | `story.md`: the angle, the one-sentence promise, the hook, the turn, the audience and the feeling |
| 2. Check it is true | `bloom-story-research` | `research.md`: every claim the video makes, with its source and verdict. **Gate**: if nothing really supports the core premise, stop and ask whether to change the topic |
| 3. Shape it | `bloom-story-structure` | `script.md`: scenes in beats, timed for the voice, with `{shown\|spoken}`, delivery tags and on-screen sources |
| 4. Cast it | `bloom-story-cast` | one to three versions, each with its own visual style, character, voice and music, as `scenes.html` + a build command |
| 4b. Act it out | this skill, "Show it happening" below | every beat staged with a prop that changes state on the words that say it, with the character reacting |
| 5. Review and compare | `bloom-story-review` | a scored review of each version and, for a bench, `bench/story/<topic>/report.md` |

Then build with the usual tools: `bloom-character` for the sprite and the impact moves, `bloom-visual` for how every frame looks (composition, the 12 principles, icons, anti-slop), `bloom-motion` for how the video moves (a camera through a world, cuts that carry over, kinetic type, draw-ons; checked seek-safe), `bloom-sound` for the sound, and `bloom build` to render. Before every render, run `bloom-visual-audit` and get zero errors (nothing out of the frame, spilling, overlapping or jumping at a cut), then check key frames with `bloom-visual/scripts/frames.py`.

## Ground rules

- **Ask before inventing the topic.** If the person has no idea, run step 1 of `bloom-story-idea` (questions) before generating anything.
- **True means sourced.** A video that says "research shows" cites the research on screen and in `research.md`. When the person asks for real research and none supports the premise, say so and ask whether to change the topic or reframe it as clearly labelled speculation. Don't quietly soften the claim and carry on.
- **Shocking but true.** "Make it scary" asks for framing (stakes, pace, sound, a concrete person losing something). Keep each number at the size its source gives, and label a scenario as a scenario ("ถ้า…", "นักวิจัยประเมินว่า…").
- **One promise per video.** If the story takes two sentences to explain, it is two videos.
- **Private work stays private** (see `bloom-character`): anonymize before writing.

## Show it happening (the default)

Don't settle for a character standing beside text that repeats the narration. In a Bloom story video, **every beat acts out its consequence on screen**, so the viewer sees the thing go wrong instead of reading that it did. For "วันที่ 1 สแกนจ่ายไม่ได้", show a phone at a food stall: the QR is scanned, a spinner turns, then a red ✕ "ทำรายการไม่สำเร็จ" appears, the phone shakes with a buzz, and the character's face falls.

Each beat gets three states:

1. Before: the normal thing, working (a phone with a QR, a cable with light running, a router's green eyes, a calendar on day 1).
2. Trigger: the cause arriving (the scan, the solar blast flying, the break in the cable). Start it with or just before the words that name it.
3. Result: the visible consequence, landing on or just after those words (✕ and "ทำรายการไม่สำเร็จ", the cable cut with sparks, Earth's aurora, the counter stopping at 38 days, a repair ship that takes the rest of the scene to arrive). Give it its sound (`buzz` for a failure, `hit` for a break, `chime` for a success) and the character's reaction (a face from the impact kit, a shake).

Act out numbers too: they count up to their value while they are said (a `count` prop), and durations tick on a calendar.

The props are in `assets/props.css` and `assets/props.js`; paste both into the page (see the header of each). They are `qr` (pay by QR, fail or `data-ok`), `pos` (card declined), `chat` (a message that never sends), `sea` (a sea-floor cable that breaks; `data-ship` sails a repair ship in), `sun` (a solar blast hitting Earth; `data-miss` crossing behind it), `cal` (days counting), `count` (any number counting, with prefix, suffix and decimals), `offline` (a place whose signal turns into ✕) and `odds` (a range filling on a bar). Each takes `--at`, the moment its result lands. The counters take `data-t0`/`data-at` in seconds, as `-1.5` from the scene's end, or as `60%` of the scene. Add a new prop to the kit instead of drawing a one-off in a page, so the next story can use it.

**Time it to the words.** Once the voice exists (from a `--voice-only` run or any build), `uv run python .claude/skills/bloom-story/scripts/when.py scripts/<project> --voice "<voice>"` prints when each phrase is spoken in every scene. Put each result on its phrase and re-render. The voice is cached, so only the picture is made again.

**Keep text to a headline and the source.** The prop and the narration carry the meaning, and the caption already shows the words.

Icons are files, drawn once with `bloom-visual/scripts/icons.py` (Twemoji SVG, or PNG through the web-asset-generator skill), so the laptop and the Mac render the same picture. Props take them as `data-icon`: `qr` shows the shop, `sun` sets Earth on fire, `sea` erupts a volcano before the cut, and `offline` uses a globe.

## When the person wants several versions

Make the versions differ in what they are meant to compare: style, character, voice and music. Keep the facts and the story beats the same so the comparison is fair. `bloom-story-cast` has the contrast table, and `bloom-story-review` has the bench procedure. Build the voices on the remote GPU when one is set up (`uv run bloom remote list`, then `--voice-on <name>` or `--on <name>`).
