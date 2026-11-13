---
name: bloom-story-idea
description: Find the story for a Bloom video when the person has only a topic, a question or nothing yet — capture the spark, generate what-ifs and angles, test a one-sentence promise, pick the hook and the turn, and write story.md. Use it when someone says "ไม่รู้จะทำคลิปเรื่องอะไร", "ช่วยคิดไอเดีย", "อยากทำเรื่อง X แต่ยังไม่รู้จะเล่ายังไง", "what if…", "brainstorm a video idea", "is this idea strong enough", or as step 1 of bloom-story.
---

# Story idea

Adapted from story-skills' `premise-workshop` for short narrated video. The person owns the idea, so offer options and tests and let them decide.

## 1. Capture the spark (ask, don't assume)

If any of these is missing and the person is present, ask for it in one short message, in their language:

- Topic or spark: a question ("ถ้าเน็ตหายไป?"), an image, a character, a fact, a feeling.
- Audience: who watches (students, office workers, kids, a client's customers) and where (TikTok/Reels/Shorts vertical, YouTube 16:9, a presentation).
- The feeling to leave: shocked, reassured, amused, curious, moved, ready to act.
- True or invented: real facts (`bloom-story-research` then gates it), fiction, or a labelled scenario built on facts.
- Length: default 45–75 s for a short. At about 13 Thai characters a second, that is 600–950 characters of narration.

When the request already answers these (a full prompt), restate your reading of it in two lines and continue. Don't ask again for what was given.

## 2. Generate angles

Write 6–10 one-line what-ifs or angles from the spark, each from a different direction:

| Move | Example for "ถ้าเน็ตหายไป" |
|---|---|
| Raise the stakes | not one app down, the whole Internet, for a year |
| Make it personal | one person's day: the alarm, the bank app, the hospital |
| Move it in time | it already happened once, in 1859, to the telegraph |
| Give it to the wrong person | a delivery rider / a grandma who never used it / a child |
| Invert it | what still works with no Internet |
| Count down | 1 hour → 1 day → 1 month → 1 year |
| Reveal the hidden machine | the cables under the sea, the address book of the Internet |

Say which angles already carry conflict. Let the person pick one to three, or combine them. In a non-interactive bench, pick the strongest yourself and record why in `story.md`.

## 3. The promise sentence

Write one sentence a stranger could repeat after one viewing: **who or what + what changes + why it matters**.

> ถ้าอินเทอร์เน็ตทั้งโลกดับ ภายในวันเดียวเงินจะหยุดเดิน ภายในเดือนเดียวของจะเริ่มหมดชั้น และนักวิจัยบอกว่ามันเกิดขึ้นได้จริง

Run the tests and mark each one pass, weak or fail:

| Test | Question |
|---|---|
| Concrete | Can each claim be shown on screen as an image (an empty ATM, a cable on the sea floor)? |
| Stakes for one person | Does a viewer feel *their own* loss, not just "the world's"? |
| Escalation | Does it get worse in at least three steps? |
| A turn | Is there one moment that flips understanding ("it already happened, in Tonga, for five weeks")? |
| True | Can every factual piece be sourced? (if unsure, `bloom-story-research` decides) |
| Distinct | Does it hold something a viewer hasn't seen in the last ten videos on this topic? |
| Fits the length | Can it be told in the chosen seconds without rushing (pace under 19 Thai ch/s)? |

## 4. Hook, turn, payoff

- Hook (first 2 seconds): a question, an image or a number that makes the promise. It must work with the sound off (on-screen text).
- Turn: the single fact or image the story pivots on.
- Payoff: short, calm and big. It lands the feeling and, if the format allows, gives one next step.
- Hook out: what the viewer is left wanting. If there is a next part, this is its spoiler, one image or fact that raises the question the next part answers. If not, it is a question turned back on the viewer. Either way the video then cuts or fades to black (see "End on a hook" in `bloom-story-structure`).
- Surprise: the one thing near the end the viewer won't see coming.

## 5. Write `story.md`

```markdown
# <title>
- promise: <one sentence>
- audience / platform / length: …
- feeling: …
- truth: real research | fiction | labelled scenario
- angle: <chosen angle> (others considered: …)
- itch: <the feeling the viewer already has that this video answers, in their words> (the internal trigger; see "Run the hook loop" in bloom-story-structure)
- hook: …
- turn: …
- payoff: …
- surprise: …
- next: <the next part and its spoiler> | none: <the closing question>
- stakes: external … · personal … (at least one personal and concrete)
```

When the truth line says real research, hand over to `bloom-story-research`. Otherwise go straight to `bloom-story-structure`.
