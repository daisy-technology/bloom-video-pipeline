# Motion recipes for Bloom scenes

The numbers come from the iart.ai motion packs (motion-design, kinetic-typography, data-animation, explainer-video, web-animation, webgl, map-animation, javascript-animation), adjusted for a 1080×1920 Thai-narrated short. Every recipe is seek-safe as written. The kit classes are in `bloom/compose/assets/motion.css` and `bloom/compose/assets/motion.js`.

## Contents
1. Kinetic type (Thai)
2. Lines, paths, shapes
3. Numbers and data
4. Diagrams, maps, isometric
5. Camera and depth
6. Cuts
7. Particles and backgrounds
8. Pacing to the voice

## 1. Kinetic type (Thai)

- **Split by word, never by code point.** Thai stacks vowels and tone marks on a consonant, and a per-character split tears them apart. Use `data-split="word"` (Intl.Segmenter, Thai dictionary) for phrases, and `data-split="char"` (grapheme clusters) only for a word or two.
- Five reveals, by register:

| Reveal | Kit | Duration, stagger | Reads as |
|---|---|---|---|
| Mask rise, line by line | `.rise` per line inside `[data-stagger]` | .6 s expo-out, lines 80–100 ms | the standard for headlines; calm, premium |
| Word fade-rise | `.words` + `data-split="word"` | .5 s, words 50–70 ms | a sentence arriving as it's said |
| Word pop | `.words.pop` | .26 s back-out, 40–60 ms | playful, kids, comedy |
| Clip wipe | `.wipe` | .6 s | a label, a stamp, a source line |
| Blur-in | `.blurin` | .7 s | a dreamy or reveal beat; one per frame, because it's costly |

- Cap a stagger near 0.8 s in total: `(count − 1) × stagger + duration`. With a longer one, the end of the line arrives after the voice has moved on.
- Thai inside a mask loses the bottoms of ุ ู and the tops of tone marks. `.rise` pads .22 em below; keep headline line-height at 1.2+ and test the frame.
- Land a word that matters as it is spoken (`when.py` gives the time). `.hit-word` turns it the accent colour with a small 1.12 scale at `--at`.
- **Don't move text being read.** Text arrives, holds still while it's read, then leaves. Put no looping wobble on a headline.
- Words can be the shape: rows of the phrase clipped into the object ("สายเคเบิล" repeated along the cable) merge the label and the thing.
- Bloom draws the captions. Keep the caption band 1550–1780 clear, and keep captions to at most two lines.

## 2. Lines, paths, shapes

- Draw-on: put `pathLength="1"` on every path and `.draw` on the SVG (or the path). Durations: an icon 0.4–0.6 s, a route or cable 0.8–1.2 s, a logo 0.6–1.2 s per path. Split compound paths (several `M`) into separate paths, or they draw all at once. Draw the outline first, then `.fill-after`.
- For a hand drawing, use `.draw.hand` (linear, because an eased long stroke lurches), at about 0.15–0.25 s per letter. To move a pen, give it `offset-path` on the same path with the same timing.
- Flow along a line (data in a cable, traffic on a road): `.flow` (dash 8 8, offset −16 per 0.6 s, linear, infinite). For a packet, use `.along` with the line's path.
- Travel on an arc, never in a straight diagonal: use `.along` with a curved `--path`. `.along.turns` rotates the object to face the way it goes (a ship, a plane).
- Morph (one icon becoming another): 0.6–1.0 s in-out; see `seek-drivers.md` (Flubber). Set `transform-box: fill-box; transform-origin: center` on SVG parts you rotate or scale, or they pivot on the SVG's corner.
- Settle: a logo or a stamped shape lands with scale 1.04 → 1 over 0.12–0.2 s.

## 3. Numbers and data

- Count while the number is said, with the props kit's `count` (eased out, formatted). Give a single number 0.8–1.2 s and ease out, with **no overshoot on quantities**. Set `font-variant-numeric: tabular-nums` so the width doesn't jitter.
- Hold the final value ≥ 0.5 s before anything else moves. The label fades in after the count, not during it.
- Never count two numbers at once; the eye can follow only one.
- Bars: animate `scale: 1 0` → `1 1` with `transform-origin: bottom`, 0.6 s `cubic-bezier(.22,1,.36,1)`, 60 ms apart. To highlight one bar, drop the others to 35 % opacity over 0.3 s.
- Line chart: draw the line (`.draw`, 0.8–1.2 s in-out) and fade in the area under it behind.
- Bring elements in by hierarchy (title → icon → number → label → connector), not top to bottom.
- Pictograms ("7 of 10 people"): the units appear on a stagger, and the partial unit is clipped, not shrunk.
- Climax stat: the biggest number gets the frame to itself (180–240 px), the longest hold, and the one big sound. Never open on it.

## 4. Diagrams, maps, isometric

- Diagram: bring in nodes → edges → labels. Nodes pop from scale .8 → 1 in 0.45 s back-out, 0.3 s apart; each edge draws in 0.5 s as its target appears; hold each step 0.5–1.5 s. A colour means one thing for the whole video.
- Map: fit the region, then make one camera move to the place (`data-cam` from k 1 to 3–4 over 1.2 s). Pins drop with a spring 0.2 s apart, and routes draw with `.draw`. Labels never rotate or scale with the map: keep them outside the camera element and place them in screen space.
- 12 fps overlay: pins, labels and hand-drawn marks on `steps()` (or `floor(t*12)/12`) feel hand-made. Keep the camera smooth.
- Isometric: use no perspective, and lift on Z instead of scaling. With one light, the top face is lightest, the left mid and the right darkest. Build bottom-up by position (0.12–0.15 s apart, back-out), and drift the camera a few degrees over 6–12 s.

## 5. Camera and depth

- Make one move per beat; never push + pan + rotate together. Moves ease in-out (`--e-move`) over 0.8–2 s.

| Move | Kit | Numbers |
|---|---|---|
| Push in (focus, tension) | `.push-in` or `data-cam` | scale 1 → 1.12 over 1.6 s, origin on the subject |
| Pull out (reveal the scale of it) | `.pull-out` or `data-cam` | 1.15 → 1 over 1.8 s |
| Pan to the next thing | `data-cam` | ≤ 1/3 of the frame per move, ease in-out |
| Punch in (a hit) | impact `.shake` + a 1 → 1.12 spring | on the beat, once |
| Slow drift (alive while talking) | `.drift` | 40–80 px across the whole scene, linear |

- Frame the subject on the rule-of-thirds points instead of centring it: y ≈ 640 and 1280 in a 1920 frame. Leave room in the direction it looks or moves.
- Parallax: inside a `data-cam` world, set `data-depth` 0.2 (sky, far) / 0.6 (middle) / 1 (the stage) / 1.3 (a foreground thing passing). When all layers move at 1.0×, the scene reads as a template.
- One world, many cameras: draw the place once, bigger than the frame (a street, a sea floor, a city), and make each beat a camera position on it. Continuity comes free, because the cuts are camera moves inside one world.
- **The 1/3 rule:** nothing travels more than a third of the frame in one unbroken move without a key or a scale change, and with three or more elements moving, at most a third of them move at once.

## 6. Cuts

- Use a hard cut by default (about 90 % of cuts); it needs no exit animation. Hard cuts make a video feel edited and keep it from reading as a slideshow.
- A match cut is the strongest: the same shape, place or direction on both sides of the cut (the round sun becomes the round coin; the cable at y 900 continues at y 900). With a persistent element (outside the sections) and `data-cam-<scene>`, the thing literally carries over.
- Cut on action: cut while something is moving, and continue the motion in the same direction and speed in the next scene.
- Push through (`.out-push` → `.in-push`) into a screen, a window or an eye, for "going inside".
- Whip (`.out-whip` → `.in-whip`, 0.28 s each, directional blur) for energy or "meanwhile".
- Dip (`.out-dip`/`.in-dip`) for time passing or a chapter. Save it for one or two cuts in a video.
- Use one transition family for the video plus one accent for the turn. A dissolve on every cut reads as amateur.
- Screen direction: progress moves left → right (or bottom → top), and going back reverses it. Keep the direction through the video.

## 7. Particles and backgrounds

- `canvas[data-particles]` offers `dust` (motes in light, a quiet room), `snow`, `embers` (fire, heat, the sun) and `confetti` (a win, at `data-at`). Use 40–120 particles, coloured from the palette (`data-color="#ffd166 #ff8fab"`).
- Smoke rises, grows and fades; sparks are short-lived and fast; snow sways. The impact kit's `.burst` is the pixel-art debris version.
- A background loop (mesh gradient, aurora, slow clouds) has a period of 8–30 s, low contrast, and a scrim under any text. Ambient motion shows the world is alive, and it must never compete with the beat.
- Glow and particles go where something is *on* (a lit cable, a fire), on one or two things a frame (`bloom-visual` anti-slop).

## 8. Pacing to the voice

- Give each phrase a beat. Get the times from `bloom-story/scripts/when.py`. Every result lands within 0.5 s of its words, with the trigger slightly before.
- Make a change every 2–4 s at uneven intervals (a metronome reads as boredom): a new prop state, a camera move, a cut, a number. With no event for more than about 3 s while the voice talks, the scene reads as a slide, and the seekcheck motion strip shows it as a run of blanks.
- Hook: put something moving on the first frame (no fade-up from black), and show the strongest visual first.
- Escalate: save the biggest move, sound and number for the climax, and keep it quieter before. Allow one "wow" moment a video.
- Endings hold still: the last line lands, motion settles, then ≥ 1.5 s of stillness follows (use `+1.5` on the scene in `script.md`).
- Exits are faster than entrances (about two thirds of the time) and ease in.

### Motion personalities

| Personality | Durations | Easing | Overshoot | Stagger | Fits |
|---|---|---|---|---|---|
| Calm / documentary | 0.5–0.8 s (unit .6) | out `(.16,1,.3,1)`, move `(.65,0,.35,1)` | 0 % | 100–120 ms | doc, science, serious news, money |
| Clean / informative | 0.3–0.5 s (unit .4) | `(.2,0,0,1)` | 0–3 % | 60–80 ms | explainers, how-to |
| Playful | 0.15–0.3 s (unit .25) | pop `(.34,1.56,.64,1)` | 10–20 % | 40–60 ms | kids, diary, comedy, pixel characters |
| Energetic / breaking | 0.1–0.25 s (unit .2) | expo out | 15–30 % on hits | 30–40 ms | hype, alerts, countdowns |

Never overshoot on serious or financial content, and never ship the browser's default `ease` (the undecided curve).
