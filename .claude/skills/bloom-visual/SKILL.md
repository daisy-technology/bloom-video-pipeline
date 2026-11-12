---
name: bloom-visual
description: Make a Bloom video's picture look designed, not generated — staging and composition for a 1080×1920 frame, the 12 principles of animation turned into seek-safe CSS, motion timing and easing by role, icons as files (Twemoji SVG, or PNG through web-asset-generator) instead of typed emoji, and the anti-slop tells to remove (stock grids, glow everywhere, neon gradients, text slides, idle wobble). Use it when building or reviewing any scenes.html, when someone says the video "looks AI-made", "ดูไม่โปร", "ภาพไม่สวย", "ทำให้ภาพดีขึ้น", "ใส่ไอคอน", "animation ดูแข็ง", or with bloom-story and bloom-character on every new video.
---

# Bloom visual

The picture of a Bloom video is a web page seeked frame by frame, so two crafts apply at once: graphic design (what one frame looks like) and animation (how frames change). This skill sets the baseline for both. It applies the design-core principles (composition, hierarchy, tokens), the 12 principles of animation (Thomas and Johnston, *The Illusion of Life*, 1981, as Adobe summarizes them), motion timing from UI animation practice, and the antislop filter, translated to video. What a scene *shows* comes first (the "Show it happening" section of `bloom-story`); this skill covers how it looks while it shows it. How the video *moves* across a scene and between scenes (camera, cuts, kinetic type, draw-ons, particles, and keeping it seek-safe) is covered in `bloom-motion`.

When rules conflict, follow this order: the person's request, then the project's own style (its palette, font, character), then platform rules (safe zones below), then these defaults.

## 1. The frame

A vertical short is watched on a phone, under the platform's own buttons and captions.

| Zone (1080×1920) | Use |
|---|---|
| 0–180 px | keep clear: platform header, status bar |
| 180–330 | headline band: one line, 64–96 px |
| 330–1100 | the stage: the prop or the event, the focal point |
| 1050–1500 | the character, reacting (smaller when a prop is the event; full size for the hook and the end) |
| 1550–1780 | captions (Bloom draws them), never covered |
| right 120 px, bottom 300 | keep clear of important content: the platform's like/share column and description |

- **One focal point per moment.** At any instant the eye has one thing to follow: the prop changing state. Everything else is quieter (smaller, lower contrast, still).
- Build hierarchy with size and contrast. When the result (✕, the number, the break) lands, it is the biggest and highest-contrast thing on the frame. A headline that competes with it is a finding.
- Use proximity: a label sits closer to its object than to anything else, and a source line sits with the headline, small.
- Type scale for video (Thai, read at phone size): headline 64–120 px, numbers 90–220 px, labels 36–48 px, source 28–32 px. Nothing goes under 28 px. Line height is 1.1–1.25 for headlines and 1.35–1.45 for captions.
- Define tokens once instead of one-off values: one palette per project as CSS variables (2–3 core colours, 1 accent, a bad/good pair for results), 2–3 radii, and a spacing scale on 8 px. Repeating the same values makes a video feel made by one hand.
- Keep text at a contrast of 4.5:1 against what is behind it, in every frame (a moving prop can slide under a label).

## 2. The 12 principles, in Bloom

The renderer seeks every animation to the frame's time, so all of these are CSS keyframes (or `window.bloomSeek`), never timers. The impact kit (`bloom-character/assets/impact.css`) and the props (`bloom-story/assets/props.*`) already implement most of them; use those before writing new keyframes.

| Principle | In a Bloom scene | Where it is built |
|---|---|---|
| 1. Squash and stretch | landing flat and wide, leaping tall and thin; keep the volume: `scale(1.2, .8)`, not `scale(1.2, 1)` | `.slam`, `.jump`, `.charge` |
| 2. Anticipation | a crouch before the jump, a scan line and a spinner before the result, a riser before the hit | `.jump` 0–18 %, `qr` scan + spinner, `riser` |
| 3. Staging | one event at a time, in the stage zone, with the character watching it; dim or remove what doesn't serve this beat | layout (section 1) |
| 4. Straight ahead / pose to pose | pose to pose: write the key poses as keyframes at the moments that matter, and let the easing fill between | every `@keyframes` |
| 5. Follow through, overlapping action | parts keep moving after the body stops (the tail wags on, the antenna wobbles after a landing); secondary parts start 1–3 frames after the lead | `squash-settle`, staggered `animation-delay` |
| 6. Slow in, slow out | nothing moves linearly except a constant drift (a ticker, clouds); arrivals ease out, departures ease in | easing table below |
| 7. Arcs | thrown and falling things travel on curves: animate x and y on separate easings, or through a mid keyframe off the straight line | `sun-miss`, debris `burst` |
| 8. Secondary action | the character reacts while the prop acts (a face, a shake, a tear), never instead of it | faces in `impact.css` |
| 9. Timing | the result lands on its word (`when.py`); big things take longer, small things snap | `--at`, `data-at` |
| 10. Exaggeration | push the key pose past real (a 30 % squash, a 26 px camera shake) only on the beat that matters, once a scene | `.shake`, `.slam` |
| 11. Solid drawing | pixel sprites keep their grid (`steps()`, one sprite pixel per CSS px in the SVG); vector props keep a consistent stroke and radius | `bloom-character` |
| 12. Appeal | a clear silhouette, one signature accessory, a readable face; props with a recognisable shape (a phone, a ship) over abstract boxes | sprite + icons |

## 3. Motion timing and easing

| Role | Duration | Easing |
|---|---|---|
| micro: a blip, a tick, a toggle | 0.1–0.3 s | `ease-out` or `steps()` for pixel art |
| a prop arriving, a result card | 0.3–0.5 s | `cubic-bezier(.2,.8,.3,1)` (out), or a spring keyframe set with one overshoot |
| a sequence: scan → spinner → result | 0.5–1.5 s across its steps | each step its own easing |
| a travel: a ship, a solar blast | as long as the narration about it | `ease-out` for arriving, `cubic-bezier(.4,0,.9,.6)` for something accelerating at you |
| ambient: clouds, ticker, light in a cable | 2–24 s loops | `linear`, and only where it shows the world working |

- Write springs as keyframes. An overshoot of about 5 % and back (`0% scale(.4) · 70% scale(1.08) · 100% none`) reads as a settle; 30 % reads as a bounce, so keep that for comic beats.
- Stagger the items in a list 40–120 ms apart, with the whole stagger under 0.4 s.
- Draw growing lines (a cable, a route, a graph) by animating `stroke-dashoffset` on an SVG path, eased out.
- Make exits faster than entrances. A hard cut needs no exit at all.
- **Only `transform` and `opacity` move** (and `filter` sparingly). They are cheap for the renderer and never shift the layout under other elements.
- **No more than three flashes a second** (photosensitivity). A `.flash` is one hit; don't repeat it into a strobe.

An 8-bit video steps smooth gradients (a navy sky, a radial glow, a soft wide shadow) into visible bands, and compression makes the banding worse. Bloom handles it at render time. Before encoding, every frame is debanded in 16 bits and dithered back to 8 with error diffusion (on by default; `--no-deband` skips it). On a navy radial gradient this shrinks the flat runs that read as bands from 19 px to 2.7 px, with no visible noise. The encoder also runs with `aq-mode=3`. Keep gradients and shadows in the page as designed: don't add noise yourself, and don't avoid gradients for fear of banding.

## 4. Icons: files, not typed emoji

A typed emoji is drawn by whatever font the rendering computer has: Apple on a Mac, Segoe on the Windows laptop, nothing on a bare server. The same project then renders differently on each machine, or with empty boxes. Draw icons once into the project:

```sh
uv run python .claude/skills/bloom-visual/scripts/icons.py scripts/<project> volcano=🌋 ship=🚢 rice=🍚
```

That writes `icons/<name>.svg`, Twemoji vector artwork that stays sharp at any size (CC-BY 4.0: credit "Twemoji" in the description). For a bitmap, `--png` renders through the web-asset-generator skill's emoji renderer (set `BLOOM_WEB_ASSETS` to that skill's folder if it isn't in `~/.claude/skills`). It upsamples 72 px artwork, so keep PNGs under about 120 px on screen. Use one icon family per video. Mixing Twemoji with hand-drawn pixel art is fine when the icons sit *in* the world (a bowl on the stall counter) rather than floating as decoration. An `<img class="icon" src="icons/volcano.svg" style="--at: 6.4s">` pops in at `--at`.

## 5. Anti-slop for video

These tells make a video look generated. Check every frame strip against them.

| Tell | Fix |
|---|---|
| A text slide: the narration repeated as bullets beside a mascot | act it out with a prop (`bloom-story`); text is a headline and a source |
| A stock "tech" background: grid lines, dot grids, circuit traces, binary rain | a real place (a room, a studio, a sea floor) or a flat colour from the palette |
| Glow on everything: text shadows, neon borders, glowing icons at once | glow only on the one thing that is "on" (a lit cable, a screen), 1–2 elements a frame |
| Blue-purple or cyan-magenta neon as the palette by default | take the palette from the story's mood and the character; 2–3 colours + 1 accent |
| Every element pops in the same way at the same scale | vary by role: the result slams, labels fade-rise, numbers count |
| Constant idle motion (bobbing, pulsing, floating) with no event | ambient motion only where it says something (the cable's light means data is flowing); the character's idle is small and stops mattering when a prop acts |
| The same transition at every cut | one primary cut style for the video, one accent for the turn |
| Emoji typed in the page; mixed icon sets | `icons.py` files, one family |
| Numbers shown static | count them up while they are said |
| A frame where two things fight for attention | stage one event; time the second after the first lands |

## 6. Review

Start with the measurable part: run the `bloom-visual-audit` skill (`scripts/audit.py`). It steps through every frame the way the renderer does and reports text out of the frame, text spilling out of its box, overlapping text, text too small, things under the platform's buttons, and anything that jumps at a cut. **Reach zero errors before every render.** The rest of this section covers what a script can't judge.

After `peek.py` passes, grab frames at each scene's key moments (before the trigger, the landing, one second after), on the real scene lengths:

```sh
uv run python .claude/skills/bloom-visual/scripts/frames.py scripts/<project> --voice "<voice>" day:1.5,2.6 month:7.2,14.5
```

It writes `.bloom/frames/sheet.png` and lists each scene's sounds with their times. Look at the sheet and score each row 0–10:

| Dimension | 10 looks like |
|---|---|
| Staging and focal point | every key frame has one obvious thing to look at, in the stage zone |
| Hierarchy and type | the result is the biggest, highest-contrast thing when it lands; nothing under 28 px |
| Motion craft (12 principles) | squash keeps volume, anticipation before every big move, eased arrivals, follow-through on landings |
| Timing to the voice | every result lands within half a second of its words (`when.py`) |
| Consistency (tokens, icons) | one palette, one icon family, repeated sizes and radii |
| Anti-slop | none of the tells in section 5 |

Report findings as `scene @time — issue → fix`, most severe first. A pass is 8+ on every row; otherwise fix and re-render (the voice is cached).
