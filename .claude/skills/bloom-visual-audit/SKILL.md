---
name: bloom-visual-audit
description: Audit a Bloom video's layout and motion before (and after) it is rendered — text or characters out of the frame, text spilling out of its box, overlapping text, text too small to read on a phone, things in the platform overlay zones, elements that jump at a scene cut (a ticker restarting), and things that teleport between frames — then report findings as `scene @time — issue → fix`, fix them, and re-audit until clean. Use it whenever a scenes.html is built or changed, before every `bloom build`, and whenever someone says a Bloom video "looks bad", "layout เละ", "ตัวหนังสือล้นจอ", "ข้อความทับกัน", "ตัวอักษรหลุดเฟรม", "ตัววิ่งกระตุก", "ภาพกระโดดตอนตัดฉาก", "review the motion", "audit the video", or asks for a visual review of a Bloom project, even if they don't say "audit".
---

# Bloom visual audit

A wrong picture is usually wrong for only a few frames: a headline that overshoots the frame while it stamps in, a label that slides under a counter as the number grows, a news ticker that snaps back to its start at every cut. A single preview screenshot misses these, and every viewer of the video sees them. So this audit steps through the page the way the renderer does (Bloom's own SHOW and SEEK, on each scene's real length from its voice clip), samples every quarter second plus consecutive frames, and measures what is on screen. `bloom-visual` says how a frame should look; this skill checks that it does, and it must pass before a render.

## Run it

```sh
uv run python .claude/skills/bloom-visual-audit/scripts/audit.py scripts/<project> --voice "<the build's --voice>"
```

It needs the voice clips (from any earlier build, `--voice-only`, or a remote run that brought them back) for the real scene lengths; without them it assumes 5 s of speech per scene. It takes seconds, writes `.bloom/audit.json`, prints the findings grouped by check, and exits 1 while any error remains.

| Check | Level | What a viewer sees | Usual fix |
|---|---|---|---|
| `frame` | error | text or a character cut off by the edge, even for a few frames | smaller entrance scale (the impact kit's `stamp` starts at 1.12×), narrower box, `left/right` inside 60 px |
| `spill` | error | text running out of the note, card or bubble it belongs to | smaller type, a wider box, or `white-space: nowrap` plus a shorter line |
| `collide` | error | two texts on top of each other (a counter's number and its label, a headline and its source, text under the caption) | more space between them (line-height 1.15 or more on big numbers), move one, or time one after the other |
| `hidden` | error | text you meant to show, covered (even partly) by an opaque prop or card | move it clear of the prop; if a card *replaces* what is under it (a result card over a screen), hide what it replaces at the same moment |
| `cut-jump` | error | something that stays across a cut (a ticker, a frame, a logo) jumping at the cut | put it outside every `<section>`: Bloom runs those on the video's clock, so it never restarts |
| `teleport` | warn | an element moving more than 250 px in one frame | an entrance that starts too far away, or a missing keyframe |
| `small` | warn | text under 28 px on the frame, scale included | raise the size, or don't scale its prop below about 0.8 |
| `safe` | warn | text under the platform's buttons (top 150 px, right 110 px) | move it into the frame's safe area (`bloom-visual`, section 1) |

Covered text is reported once, as `hidden`, and not again as a collision. A number that re-centres as it counts is not a teleport.

## The loop

1. Audit, and read the errors first. Each line names the scene, the time span, the element (tag, class and its first words) and what is wrong.
2. Look at the worst moments: `bloom-visual/scripts/frames.py scripts/<project> --voice "…" scene:t,…` at the times the audit printed. The numbers say *where*; the sheet says *how bad*.
3. Fix at the cause. A finding that repeats in every scene comes from shared CSS (the impact kit, the props kit, the page's own rules), so fix it there once. A one-off comes from the scene's own markup. Keep the fix in the project's style (`bloom-visual`); don't shrink everything to make the numbers pass.
4. Re-audit until there are no errors. Decide on each warning: fix it, or accept it with a reason (the broadcast bar is a frame; nothing in it must be read).
5. Render (`bloom build`, the voice is cached), then grab frames from the MP4 at the same moments to confirm.

When something breaks a rule on purpose, opt it out: mark the element (or a parent) with `data-audit="<checks>"` and a comment saying why. A ticker that runs off both edges is `data-audit="frame spill safe"`. **An opt-out without a reason is a finding in review.**

## Reporting

Report to the person as findings, most severe first, one line each:

```
day @2.25–12.3s — the ✕ overlaps "ทำรายการไม่สำเร็จ" in the QR result card → line-height 1.15 on the ✕ (props.css)
hook @0.25s — the headline overshoots the frame by 366 px while it stamps in → stamp entrance from 1.12×, not 2.8× (impact.css)
```

Then list what you changed and the audit's before/after counts (`errors 83 → 0, warnings 38 → 4`). Name each warning you accepted and why.

## Trust the frame over the number

The audit measures boxes, not ink. Before fixing a finding, look at its frames. If the sheet shows clear space where the audit says two texts collide (a tall Thai glyph box, an entrance passing through), say it is an artefact and leave the page alone. The audit can also miss what lasts less than a few frames. It samples every animation's own frames, but a frame sheet at the moments it printed is still the proof.

## What it cannot see (look for these by hand)

All of these were found by eye in the first test runs, and none of them is a geometry error:

- Something that should show but doesn't, such as a page rule hiding a prop's label (`.tag { display: none }` hid the sea's captions in every scene) or an element under an opaque layer for the whole scene. List what each scene is meant to show and find each item on the sheet.
- Contrast against the ground. A dark device on a dark page (`--p-ink` near the background) loses its outline. Text must stay at 4.5:1 against whatever passes behind it.
- Picture against voice. What is on screen while a line is spoken must be what the line is about: a 1859 card still up while the voice says "2012" is out of sync even though nothing overlaps. Check with `bloom-story/scripts/when.py`.
- Taste: composition, colour, hierarchy, and whether the motion has life. Use the rubric in `bloom-visual` (section 6). The sound belongs to `bloom-sound`.
