---
name: bloom-motion
description: Make a Bloom video move like an animated film instead of a slideshow of infographic cards — a world bigger than the frame with a camera that pushes, pans and cuts on the beat, parallax depth, match cuts and things carried across scenes, Thai kinetic typography split by word, lines and routes that draw on, objects travelling on arcs, numbers and charts that count and grow, particles and living backgrounds, and a motion language (easing, timing, personality) set once — all seek-safe for Bloom's frame-by-frame renderer, checked by a script that catches motion that breaks when frames render out of order (Math.random, SMIL, timers, state in bloomSeek). Use it whenever building or reworking a scenes.html, turning a static or "slide-like" Bloom video into an animated one, adding GSAP, Lottie, canvas, three.js or shaders to a Bloom page, or when someone says "ทำให้เป็นแอนิเมชัน", "ภาพนิ่งเกินไป", "เหมือนสไลด์", "ให้มันขยับ", "ใส่ motion", "กล้องเคลื่อน", "ตัวหนังสือวิ่ง", "kinetic type", "make it animated", "more motion", "camera move", "transition between scenes", even if they don't say "motion".
---

# Bloom motion

A Bloom video is a web page seeked frame by frame. `bloom-visual` decides how one frame looks and gives the base animation principles. This skill decides how the video moves: where the camera goes, how one scene becomes the next, how type, lines, numbers and particles arrive, and how to build all of it so the renderer draws the same frame every time. The craft numbers come from the iart.ai motion skill packs (motion-design, kinetic-typography, data-animation, explainer-video, web-animation, webgl, javascript-animation), translated to Bloom's 1080×1920 Thai shorts and its seek renderer.

Order of authority: the person's request, then the project's style, then the story's beats (`bloom-story`), then this skill.

## Slides or animation: the difference

A Bloom video reads as slides when every scene has the same layout (headline on top, a card in the middle, the character at the bottom), elements pop in and then nothing moves, the camera stays put, and each cut swaps the whole layout with nothing carried over. It reads as animation when the camera moves through a place, things travel, draw, count and react on the words that name them, and each cut continues something from the last scene.

Diagnose before changing anything: run `scripts/seekcheck.py` (section 6). Its motion strip shows each scene's rhythm with one character per quarter second: `' '` still, `.` under 1 % of the frame changing (an idle loop, a ticker), `:` some, `#` a lot. After the strip it prints the scene's longest quiet stretch. A quiet stretch over about 3 s while the voice talks is dead air: only a loop is moving, and the scene is a slide. `:` everywhere with no `#` means motion without events.

## 1. Set the motion language first

Before animating anything, pick one personality for the video and write it as tokens on `:root` (the kit's `motion.css` has the defaults). Every duration is a multiple of the unit. Use at most two curves, one for arriving and one for leaving.

| Personality | Unit | Overshoot | Stagger | For |
|---|---|---|---|---|
| Calm / documentary | .6 s | 0 % | 100–120 ms | doc, science, money, serious news |
| Clean / informative | .4 s | 0–3 % | 60–80 ms | explainers, how-to |
| Playful | .25 s | 10–20 % | 40–60 ms | kids, diary, comedy, pixel characters |
| Energetic / breaking | .2 s | 15–30 % on hits | 30–40 ms | alerts, hype, countdowns |

Take the personality from the story's feeling and the character (`bloom-story-cast`), and keep it for the whole video. A documentary that bounces like a cartoon breaks its own voice. Never overshoot on numbers or serious content.

## 2. Map the motion before writing CSS

Get the word times (`uv run python .claude/skills/bloom-story/scripts/when.py scripts/<project> --voice "<voice>"`), then write a short beat map as a comment at the top of each section:

```html
<section data-scene="cable">
<!-- motion: 0.0 cut-on-action from sun (the blast's direction continues) · camera wide on the sea floor
     2.1 "สายเคเบิล" cable draws left→right, light flows        · camera pans along it (1.4 s)
     5.8 "ขาด" the cable snaps, debris, hit                     · punch-in 1.12, router's face falls
     8.4 ">99%" counts up, holds                                  · camera holds still while it's read
     -0.6 the cut: the ship sails out right → next scene enters from the left -->
```

- Give each moment one hero: the thing changing state. Everything else is support (smaller, slower, quieter) or texture (ambient, low contrast).
- While the voice talks, make a change every 2–4 s at uneven intervals: a state change, a camera move, a cut, a count.
- The result lands on its words (within 0.5 s), and the trigger comes a little before.
- Hold still while text or a number is read, and at the end (≥ 1.5 s).

## 3. Turn a layout into a scene

The steps are ordered by how much each one changes the feel. Recipes and numbers are in `references/recipes.md`.

1. Make the scene a place. Draw the world bigger than the frame (the sea floor with the cable on it, the street with the stall, the bedroom) and move a camera over it: `data-cam="0 1 540 960, 2.1 1.2 300 1100, 5.8 1.35 620 1100"` (time, zoom, the point to frame). Give it depth with `data-depth` layers (sky 0.2, middle 0.6, stage 1). Make one move per beat, eased in-out, covering ≤ 1/3 of the frame.
2. Carry something across every cut: a match cut (the same shape, place or direction on both sides), a cut on action (cut mid-move and continue it), or a persistent element outside the sections, keyed per scene (`data-cam-<scene>`). Hard cuts are the default. Use one transition family (`.in-*`/`.out-*` in the kit) plus one accent for the turn.
3. Make things travel and draw. Lines draw on (`.draw`, `pathLength="1"`), data flows along wires (`.flow`), and objects travel on arcs (`.along`), never in a straight diagonal glide.
4. Bring type in with the voice. Headlines rise line by line (`.rise`), sentences arrive word by word (`data-split="word"` + `.words`, Thai-safe), and the word that matters lands on its beat (`.hit-word`). Text stays still while it's read.
5. Numbers count and charts grow. Use the props kit's `count` and bars that grow, run one counter at a time, and hold the final value.
6. Add texture where the world is alive: dust in a lit room, embers by the sun, snow, a drifting background, confetti for a win (`canvas[data-particles]`). Use it in one or two places a frame, and never over text being read.
7. Make the character act with the event (`bloom-character`'s impact kit): it reacts when the prop changes, not on a loop.

The first test runs added three rules:

- Fill the frame. A camera in a big world tends to leave a small subject in a dark, empty frame. At every key moment the hero should take a good share of the stage zone (330–1100). When it doesn't, push in or bring the world closer; don't add decoration.
- Give the hero appeal. A thing with a face, a gait or a reaction (a banknote that runs, a router whose eyes go ✕) carries a story better than a well-drawn diagram. Use the project's character, or make the travelling object a character.
- Keep the project's frame. If the video has a header band (title + source line), every reworked scene keeps it in the same place and style, so the cuts between reworked and untouched scenes don't show.

**Every video ends on a hook.** The rule and the words are in `bloom-story-structure` → End on a hook. In the picture:

- If there is a next part, tease it in the last scene with `.tease` (a dark silhouette that never resolves) or `.peek` (a slit that opens a little), as a mystery the next part answers. Cut off on the reveal with `.end-cut` and `data-sfx="hit cut"` (or `sting cut`) at the moment it would show. Picture and music stop together, and silence and black hold for the scene's `+` hold.
- If there is no next part, the closing question arrives word by word and holds still 0.5–1 s, then ends with `.end-cut` (`hit cut`, sharp) or `.end-fade` (`data-sfx="fade"`, `--len` .8–1.2 s, quiet).
- Nothing moves, loops or plays after the cut. The black is the ending.

Keep what works. The props kit (`bloom-story/assets/props.*`) and the impact kit (`bloom-character/assets/impact.css`) already move on their beats. Put them in the world and move the camera around them instead of rebuilding them.

## 4. The kit

Paste `bloom/compose/assets/motion.css` into the page's `<style>` after the impact and props CSS, and `bloom/compose/assets/motion.js` into a `<script>` at the end of `<body>`, after `props.js`. Both read `--at` (seconds from the scene start), like the other kits.

| Want | Use |
|---|---|
| headline, line by line | `<h1 data-stagger><span class="rise"><span>line 1</span></span><span class="rise"><span>line 2</span></span></h1>` |
| sentence, word by word | `<p class="words" data-split="word" style="--at: 2.1s">…</p>` (`.words.pop` for playful) |
| a word landing on its beat | `<span class="hit-word" style="--at: 5.8s">ขาด</span>` |
| a line / route / outline drawing | `<svg class="draw" style="--at: 2.1s; --len: 1.2s"><path pathLength="1" …></svg>` |
| something travelling a path | `<div class="along turns" style="--path: path('M0 0 C…'); --at: 3s">` |
| light or data flowing in a line | `<path class="flow" …>` |
| camera: several moves in a scene | `<div class="world" data-cam="t k cx cy, …">` + `data-depth` layers inside |
| camera: one push or pull | `.push-in` / `.pull-out` with `--fx --fy --k --len` |
| a cut with a transition | `.in-whip` / `.in-push` / `.in-dip` on the scene's wrapper, `.out-*` on a wrapper inside it |
| particles | `<canvas data-particles="dust" data-n="80" data-seed="3" data-color="#fff #ffd166">` (`confetti` with `data-at`) |
| hand-drawn wobble | `.boil` (re-drawn every 4 frames) |
| the ending | `.tease` / `.peek` for the next part; `<div class="end-cut" data-sfx="hit cut" style="--at: 6.2s">` or `<div class="end-fade" data-sfx="fade" style="--at: 6s; --len: 1s">` last in the final section |
| your own JS motion | `window.BM`: `prog`, `ease`, `spring` (closed form), `rand(seed, i)` |

**Use one moving class per element.** Each class sets `animation`, so a second one replaces the first. To combine an entrance and an exit, or a kit move and an impact move, nest wrappers; nested moves add up.

## 5. Seek-safe: the contract

Bloom pauses every animation, sets it to the frame's time, then calls `window.bloomSeek(scene, t)`. It also splits the scenes across several browsers that each start mid-video. So **every frame must be a pure function of (scene, t)**:

- CSS keyframes and Web Animations made at load are safe; Bloom seeks them.
- Canvas, WebGL, GSAP, Lottie and shaders must draw from `t` inside `bloomSeek` (chain onto any earlier `bloomSeek`, as the kits do). Recipes are in `references/seek-drivers.md`.
- Not safe: `Math.random`, `Date.now`, `performance.now`, `requestAnimationFrame`, timers, CSS transitions, values carried from the last frame (`x += v`, `mixer.update(dt)`, a damped lerp), SVG `<animate>` without the kit, `<video>`. Use `BM.rand(seed, i)`, closed-form motion or keyframes instead.
- Vendor libraries into the project folder. A CDN link can fail on the render machine.

## 6. Check

1. Seek safety. A render needs this check to pass:
   ```sh
   uv run python .claude/skills/bloom-motion/scripts/seekcheck.py scripts/<project> --voice "<voice>"
   ```
   It draws every sampled frame in order, then again with the scenes in reverse on a fresh browser, and compares the pictures. On a difference it names the likely cause, saves the differing pairs to `.bloom/seekcheck/`, and exits 1. It also prints the motion strip per scene. **Get to zero differences before a render.**
2. Layout: run `bloom-visual-audit` (text off the frame, collisions, jumps at cuts). Camera moves and travelling things cause most of its findings; fix them there.
3. Look: run `bloom-visual/scripts/frames.py` at the beat-map times, plus a frame every 0.5 s through the busiest scene. Score the frames against the rubric below.
4. Render (`bloom build`; the voice is cached) and watch it once at full speed. Motion problems (floaty, stiff, too busy) only show in playback.

| Dimension (0–10) | 10 looks like |
|---|---|
| Motion language | one personality, durations on the unit, two curves, no default `ease` |
| Camera and space | a place the camera moves through; one move per beat; parallax; nothing glides more than a third of the frame unbroken |
| Continuity | something carries across each cut; screen direction kept; one transition family |
| Beat timing | every result within 0.5 s of its words; a change every 2–4 s; holds when text or numbers are read and at the end |
| Craft | arrivals ease out, exits are faster and ease in; draw-ons, arcs and counts instead of pop-ins; Thai never split mid-cluster |
| Restraint | one hero a moment; one wow a video; ambient motion low and only where the world is alive |
| Ending | a hook: the next part teased and cut off on the reveal, or a question held then cut or faded; music stops with the picture |

Report as `scene @time — issue → fix`, most severe first. A pass is 8+ on every row.

## 7. Reworking an existing Bloom video

When the video already works and should become animated:

1. **Keep `script.md` as it is** (facts, words, delivery tags). The voice clips are cached by their text, so the rework renders only the picture and the comparison stays fair. When the rework is for comparison (a bench), put it in a new folder (`scripts/<name>-motion/`) with the same `script.md` and copy `.bloom/voice` across; otherwise edit in place.
2. Take a baseline: `seekcheck.py` for the motion strip, a frame sheet of the current video, and `when.py` for word times.
3. Write the beat map (section 2) for every scene, then rebuild each scene with section 3. Keep the project's palette, font, character and props; change the staging, camera, cuts and how things arrive.
4. Check (section 6) until seekcheck and the audit are clean, then render.
5. Compare before and after: the frame sheets side by side, both motion strips, and the rubric scores. Describe what changed in each scene in one line.
