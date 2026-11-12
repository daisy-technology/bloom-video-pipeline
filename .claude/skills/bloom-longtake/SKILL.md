---
name: bloom-longtake
description: Make a 16:9 (1920×1080) Bloom video as one long take — a single clean isometric world the camera travels through without cutting, each narrated scene a station that builds on its words and stays built, ending on a hook — for introducing what something is and what it does (the default "intro" mode), and also product demos and walkthroughs, how-it-works explainers, and release / what's-new videos, for YouTube and a README or website hero. It sets up the project (scripts/new.py: template, iso world kit, motion kit, script skeleton per mode), lays out the world and the camera route, and checks it seek-safe and clean at 16:9. Use it whenever someone wants a horizontal / landscape / 16:9 / YouTube / README / website / hero / product / project / company / app / open-source intro video with Bloom, says "วิดีโอแนะนำ", "แนะนำโปรเจกต์", "แนะนำตัว", "แนะนำผลิตภัณฑ์", "คลิปแนะนำ 16:9", "intro video", "explainer", "demo video", "walkthrough", "what's new", "release video", "one shot", "long take", "ไม่ตัดฉาก", "กล้องเคลื่อนต่อเนื่อง", even if they don't say "long take".
---

# Bloom long take

A long take is one shot in which the camera travels without cutting. For a 16:9 video that introduces something, it is the clearest form: the viewer is taken through the subject stop by stop and at the end sees all of it assembled. In Bloom it works like this:

- One world, outside every section. Bloom hides every section except the current one, and anything outside them stays on screen across the cuts. The world (the floor, the blocks, the screens, the labels pinned to them) therefore lives outside the sections, and the cuts between narrated scenes never show.
- A station per scene. Each `## scene` in `script.md` is a stop on the route. The station builds as its words are said (`data-after="scene@t"`) and **stays built in every later scene**.
- A camera route. The world carries one camera key list per scene (`data-cam-<scene>`). Each scene's first key equals the previous scene's last, so the picture never jumps. Keys can name a place (`#station`).
- Screen space only for reading. The header, the closing question and the captions sit in sections, in fixed bands. Labels for things in the world are pinned to them (`data-pin`) and travel with the camera.

This skill builds on `bloom-motion` (motion language, kit, seek safety, the ending rule) and `bloom-story` (what to say). Read `bloom-motion` first if you haven't; this skill covers what changes for 16:9 and one continuous world. The default look is clean isometric UI, the simple, quiet arcade/UI feel the person picked. Change it only when they ask or the project has its own brand.

## 1. Start the project

```sh
uv run python .claude/skills/bloom-longtake/scripts/new.py scripts/<name> --mode intro   # or demo | explainer | release
```

It writes `scenes.html` (the template with `bloom/compose/assets/iso.js` and the motion kit inlined), a `script.md` that is a working 3-scene example with the chosen mode's outline in a comment, and the Mitr font. Rewrite both for the subject and keep the structure. Render with `--size 1920x1080`; every checker takes the same flag.

## 2. Write the script to a route (the modes)

Pick the mode from what the person wants the viewer to leave with. Each mode is a route through the world; `references/modes.md` has the full outlines, lengths and per-mode craft.

| Mode | The viewer leaves knowing | Route |
|---|---|---|
| intro (default) | what it is, what it does, why it matters to them | hook → what it is → 2–4 things it does, each shown working → hook out |
| demo | how to use it | the result first → screen by screen, one click and its effect per stop → hook out |
| explainer | how it works inside | the question → in → each stage of the machine → out → hook out |
| release | what changed | the biggest change → each change as before/after → tease the next version |

These rules hold in every mode:

- **Show each feature working instead of listing it.** A station is a thing that changes state as its words are said (a file going in, a voice coming out). If a line can't be shown, cut it or make it a station.
- One idea per station, 5–12 s each. An intro runs 45–90 s, a YouTube video 1–3 min, a README hero 30–60 s.
- **Hook in the first 2 s**, with the sound off: the first frame must already move.
- **End on a hook** (`bloom-story-structure` → End on a hook): a question to the viewer, or the next part teased and cut off on the reveal, then `.end-cut` / `.end-fade` with the music stopping. In a long take the strongest last image is the pull-out: the camera rises and shows every station built at once, then the question, then black.

## 3. Lay out the world and the route

`bloom/compose/assets/iso.js` turns a few attributes into a clean 2:1 isometric world (top face lightest, left the colour, right darkest; no perspective; layered back to front automatically):

```html
<div class="world iso" data-unit="56" data-origin="1700 520"
     data-cam-what="0 1 #s1, 1.4 1 #s2" data-cam-does1="0 1 #s2, 1.4 1.1 #s3">
  <div data-tile="-2 -2 22 10" style="--c: var(--floor)"></div>                       <!-- the ground -->
  <div id="s2" data-box="8 0 0 3 2 3" style="--c: var(--c2)" class="build" data-after="what@1.4"></div>
  <div data-face="right 11 0.2 2.4" class="face screen grow" data-after="what@2">…</div>  <!-- a screen on its side -->
  <div data-pin="9.5 1 3.4" class="tag grow" data-after="what@1.6" data-until="does1@.6">ชื่อ</div>
</div>
```

- Lay the route left to right (progress), or along a road the camera follows. Space stations 5–7 units apart so each fills the frame at zoom 1 with room for its label.
- **One move per beat.** Travel in the first 1–1.5 s of a scene (while the voice draws breath), then hold close with a slow push or drift while the words land. Keep moves ≤ 1/3 of the frame unless the camera rises or pulls back to show context.
- Build in the order of the words: base first, then what sits on it, then its screen and label (`data-after` times from `when.py`). `.build` raises a block from its base, `.grow` pops in a screen or label, and `.appear` fades text up. `data-until` lets a label leave when the camera moves on, so old labels don't pile up at the frame edge.
- Things that run on across cuts (a clip playing on a screen in the world, a line typing, a counter): drive them from the third argument of `bloomSeek(scene, t, now)`, which is the video's clock. Never drive them from a table of scene lengths copied into the page, because it goes stale when the voice changes. Example clips are sprite sheets (`ffmpeg -ss <s> -t 4 -i in.mp4 -vf "fps=10,scale=216:384,tile=8x5" -frames:v 1 sheet.jpg`) shown one frame at a time with `background-position`; a `<video>` element can't be seeked frame-exactly.
- Text people read stays flat: pinned labels (`data-pin`) and the header. Faces (`data-face`) carry screens and signs as decoration only, because skewed text is hard to read.
- Palette: a pale ground, 2–3 block colours and one accent from the subject (its logo, its site), with one light direction. Clean means few colours, generous empty floor, soft shadows, and no glow or gradients on blocks.
- Chapter breaks (long videos only): at most one a minute, made as a deliberate camera move instead of a cut. The camera pushes into a screen in the world and the next chapter's world is inside it, or it rises into the sky and comes down on the next area.

## 4. 16:9 frame and platforms

| Zone (1920×1080) | Use |
|---|---|
| outer 5 % (96 px sides, 54 px top/bottom) | title-safe: the player's title overlay and progress bar sit here, so no text |
| top-left 120–600 × 80–260 | the header: what this station is (title + one line), only when it helps |
| centre | the world and the current station |
| bottom 900–1010 | Bloom's captions (`#caption`), centred, ≤ 2 lines |

- README or website hero: it often autoplays muted. Burn in the captions, make the first frame already show the subject, and keep it under 60 s. The black after the hook gives a clean loop point.
- YouTube: the end screen's clickable cards appear in the last 5–20 s on the right two-thirds. If the person will add end-screen elements, follow the hook with a calm end plate (≥ 20 s, brand in the left third, the right two-thirds quiet) and tell them so; the video must be ≥ 25 s. Type sizes at 1080p: headline 64–96 px, labels 30–40, nothing under 24.

## 5. Check

Run the usual checks at 16:9:

```sh
uv run python .claude/skills/bloom-motion/scripts/seekcheck.py scripts/<name> --size 1920x1080 --voice "<voice>"
uv run python .claude/skills/bloom-visual-audit/scripts/audit.py scripts/<name> --size 1920x1080 --voice "<voice>"
uv run python .claude/skills/bloom-visual/scripts/frames.py scripts/<name> --size 1920x1080 --cols 4 <scene>:t,… …
```

- **No visible cut.** The audit's `cut-jump` check watches the world across every cut; zero findings means the take is unbroken. Also compare the last frame of each scene with the first frame of the next on the sheet.
- seekcheck must pass. Its motion strip under-reads calm camera moves over a pale world (the pixel changes are small), so judge the quiet stretches on the frame sheet rather than by the number alone.
- audit must show 0 errors. Its `safe` check covers the 16:9 title-safe band.
- Render with `uv run python -m bloom build scripts/<name> --size 1920x1080 --voice "<voice>"`, then watch it once at full speed, because the camera's pace decides whether a long take works.

Rubric (0–10, pass 8+): one unbroken take (or declared chapter moves only) · every station shown working on its words · the world accumulates and the pull-out shows it all · camera calm and readable (one move per beat, holds while text is read) · clean look (few colours, flat readable text, no clutter at the frame edge) · ends on a hook with picture and music stopping together.
