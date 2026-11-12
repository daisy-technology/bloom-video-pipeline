---
name: bloom-story-review
description: Review and compare Bloom story videos — score each version on the storytelling skills (hook, directness, detail, empathy, timing, creativity, editing, truth) with a simulated viewer panel plus measured numbers (length, pace, Whisper error, loudness, sources on screen), and write a bench report that says which version works best and why. Use it when someone asks "อันไหนดีกว่า", "เทียบ 3 แบบ", "review the story", "bench these videos", "would people keep watching", or as step 5 of bloom-story.
---

# Story review

Adapted from story-skills' `reader-panel`. Label simulated reads as simulated, and never present them as real audience feedback. The rubric's criteria come from Indeed's list of storytelling skills: directness, attention to detail, empathy, creativity, editing, timing, humour, copywriting, impression management, strategic thinking, branding. Each one is turned into something you can check in a video.

## Measured (from the build, no opinion)

| Measure | Where | Good |
|---|---|---|
| length | build output | inside the target (default 45–75 s) |
| pace per line | build output `ch/s` | 10–19, no `(rushed)` |
| Whisper check | `<name>.review.html`, "N of M lines may be wrong" | 0 flagged |
| loudness | build output | −14 ±1 LUFS, true peak ≤ −1 dBTP |
| sources on screen | count `.src` in scenes.html against the factual scenes in research.md | every factual scene |
| claims verified | research.md | 100 % of the claims used are verified or reworded |

## Scored 1–5 by a simulated panel

Score with three personas. Each one reads the script and looks at the frame strip (the `peek.py` sheet, or frames from the MP4):

- Scroller (first-page reader): would they stop scrolling within 2 s? Do they stay to the end?
- Sceptic (fact-minded): is anything overstated? Is every number sourced and in its context?
- Target viewer (the audience in story.md): do they feel it personally? Is the language theirs?

| Criterion | From | Question |
|---|---|---|
| Hook | timing | does the first scene make the promise, with the sound off? |
| Directness | directness | one promise, no detours |
| Detail | attention to detail | concrete images (an ATM, a cable ship) instead of abstractions |
| Empathy | empathy | one person's loss the viewer can feel |
| Escalation & timing | timing | each step worse, the worst withheld until its step, the turn lands |
| Truth | impression management | nothing overstated, scenarios labelled, sources shown |
| Shown, not told | creativity, attention to detail | does every consequence happen on screen (a prop changes state on its words), or is it only said and written? |
| Craft fit | creativity, branding | style, character, voice and music agree |
| Editing | editing | no wasted line, clean captions, no misread words |
| Hook out | timing, creativity | instead of a summary, does the end leave them wanting more (a next part spoiled and cut off on the reveal, or a question they keep thinking about), with a surprise before it and a cut or fade to black? |

Back each score with one line of evidence instead of adjectives.

## Bench report

For a comparison of versions, write `bench/story/<topic>/report.md`:

1. The prompt, verbatim, and the outcome of the research gate (premise supported: yes/no, by what).
2. A table of version × measured numbers.
3. A table of version × the ten scores, with the evidence lines.
4. A linked contact sheet (key frames) for each version.
5. Verdict: which version suits which audience, and the one change that would most improve each.

Keep the scoring honest. When a version wins on hook but loses on truth, the report says so.
