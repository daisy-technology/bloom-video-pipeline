---
name: bloom-story-structure
description: Shape a Bloom video story into script.md — pick a beat structure (countdown ladder, problem→turn→payoff, before/after, myth vs fact, diary), size each scene to the voice, write narration Thai TTS reads well, and mark where the sources, the big moves and the sounds land. Use it when turning story.md and research.md into scenes, when someone asks "เรียงเรื่องให้หน่อย", "เขียนสคริปต์", "ทำให้ลุ้น/ตกใจ/น่าติดตาม", "the video drags", or as step 3 of bloom-story.
---

# Story structure

Adapted from story-skills' `plot-structure` and `scene-craft` for a voice-led video, where each scene lasts its voice line plus 0.9 s.

## Pick one structure

| Structure | Beats | Fits |
|---|---|---|
| Countdown ladder | hook → cause → step 1 → step 2 → step 3 (each worse) → turn → payoff | "what happens after 1 day / 1 month / 1 year", disasters, growth |
| Problem → turn → payoff | hook → the problem in one person's life → why → the turn (the fact that changes it) → payoff | explainers, product, how-to |
| Before / after | the normal → the break → the new normal → what we keep | change, history |
| Myth vs fact | the belief → the evidence → the surprise → what to do | debunking |
| Diary | day 1 → day 7 → day 30… in one character's words | making a big scenario personal |

Once the video announces its structure, it must keep to it: a video that says "1 day, 1 month, 1 year" delivers all three, in that order, each worse than the last.

## Size the scenes

- Put one idea in each scene, in 1–3 short phrases. A scene is one `## id` in script.md, and each new scene gets a new picture, so cut where the picture should change.
- Aim for a pace of 11–15 Thai characters a second. The build prints the pace and flags `(rushed)` over 19. A 60 s video has about 700–850 characters of narration in 6–9 scenes.
- Keep the hook scene ≤ 5 s, and give the last scene a hold (`+1.5`) for the final card.
- Escalate: make each ladder step shorter and harder-hitting than the one before. Hold back the worst thing until its step (Indeed's "timing" skill).

## Write for the ear (Thai TTS)

- A space is a phrase break and a breath, so write in phrases a speaker would breathe between.
- Plain amounts read well (OmniVoice spells them). Put years, codes and abbreviations in `{shown|spoken}`: `{1859|หนึ่งพันแปดร้อยห้าสิบเก้า}`, `{DNS|ดีเอ็นเอส}`, `{BGP|บีจีพี}`.
- Write English names as they are said in Thai: `{Facebook|เฟซบุ๊ก}`, `{NASA|นาซา}`.
- Use delivery tags only where the delivery changes: `[sigh]`, `[surprise-ah]` for OmniVoice (see `bloom-sound`).
- Match the particles to the narrator: ครับ for a man, ค่ะ for a woman, none for a newsreader.
- Cut every word that doesn't carry the story (Indeed's "directness" and "editing"), then read it aloud once at speaking pace.

## Run the hook loop

A video keeps a viewer the way a habit-forming product keeps a user. Nir Eyal's Hook model ([How to manufacture desire](https://www.nirandfar.com/how-to-manufacture-desire/)) has four phases. Each one has a job in a Bloom script:

| Phase | In a product | In the video | Write it as |
|---|---|---|---|
| Trigger | external: a notification; internal: a feeling the user already has ("the first-to-mind solution wins") | external: the first frame and its headline, read with the sound off. Internal: an itch the viewer already feels, named in their words in the first line ("คลิปหนึ่งนาที ทำไมต้องตัดต่อทั้งวัน") | `itch:` in `story.md`, said in the hook scene before anything about the subject |
| Action | the easiest behavior done in anticipation of a reward (motivation × ability) | staying for the next 3 seconds. Make it cheap: no logo, intro or setup before the itch, one idea per scene, the first reward inside 5 s | the hook scene ≤ 5 s, and scene 2 already pays something off |
| Variable reward | a reward that's sometimes different; "predictable feedback loops don't create desire" | every scene pays off, but not the same way twice: a number counting up, a before/after flip, a reveal ("this video came from that file"), a laugh, the picture landing on the exact word. Open a small question in one scene and answer it in the next | each scene's `act:` comment names its reward, and no two scenes in a row share the same kind |
| Investment | the user puts something in (data, effort, a follow) that loads the next trigger | the ending asks the viewer to put something in: answer the question in a comment, try one step, choose the next part. That effort is what brings them back (a reply notification, part 2) | the closing question (see End on a hook) is one the viewer can actually answer or do, in one line |

Use the loop the way the article ends: to give the viewer something worth their time. The truth rules still win. An itch is a feeling the viewer really has, and every reward is something true.

## End on a hook

End every Bloom video on something the viewer wants answered, then stop the picture and the music together. Do not close on a summary that wraps everything up. Decide which ending this story has before writing the last scene, and record it in `story.md` as `next:`.

- If there is a next part (a series, or the story has more to tell): after the payoff, spoil the next part with one concrete image or fact that raises a question ("แต่ก่อนเน็ตจะกลับมา มีอีกอย่างที่พังก่อน…"). Show it half-hidden, as a silhouette or through a slit, and **cut off on the reveal**: before the answer, mid-motion or mid-sentence, hard-cut to black and silence. A small "ตอนต่อไป" label may sit on the tease, but the answer never does. Promise only what the next part will deliver, and source that promise too when it rests on research.
- If there is no next part: end on a question that turns the story to the viewer ("คุณจะติดต่อคนที่คุณรักยังไง?"). Let it hang 0.5–1 s, then cut (sharp, unsettling) or fade (quiet, reflective) to black.
- Plant a surprise in the last third: one fact or image the viewer didn't see coming, so the ending lands on something new instead of a recap. Keep it separate from the turn. The turn changes the story, and the surprise sharpens its end.

In `script.md`, the hook is the last spoken line. Keep it short, ending in a question or broken off ("แล้วสิ่งที่ตามมาคือ…"). Give the last scene a hold for the black (`## end +1.2`). `bloom-motion` covers the picture side: `.tease`, `.end-cut` and `.end-fade`, with the music stopping on `cut`/`fade`.

## Mark the action while you write

Under each heading, write in an HTML comment what the viewer *sees happen*: the prop, its before → trigger → result, the word the result lands on, the character's reaction, and the source. A scene whose comment only lists text to show is not finished. Act out every consequence the narration states (see "Show it happening" in `bloom-story`):

```markdown
## day
<!-- act: phone at a food stall pays by QR (prop qr) → scan, spinner → ✕ "ทำรายการไม่สำเร็จ" + buzz, lands on "เงินหยุดเดิน" ·
     react: the kid's face falls, phone shakes · then 20,400 ล้าน counts up on "สองหมื่นล้านครั้ง" · src: ACI 2024 -->
ภายในวันแรก เงินหยุดเดิน คนไทยโอนเงินแบบทันที กว่าสองหมื่นล้านครั้งในปีเดียว
```

Put each scene's big move in a gap of the voice: before the first word, on a phrase break, or after the last word (see Impact in `bloom-character`).

## Checklist

- every scene's comment names an action (before → trigger → result), not only text
- the hook makes the promise in the first scene and reads with the sound off
- the hook loop holds: the itch comes first, the first reward lands inside 5 s, rewards vary scene to scene, and the ending asks the viewer to invest something
- every promised ladder step is delivered, each worse than the last
- each factual scene has its source in `research.md` and on screen
- the turn is one concrete fact or image
- the video ends on a hook instead of a summary (a teaser for the next part cut off on the reveal, or a question to the viewer), then cuts or fades to black, and `story.md` says which (`next:`)
- one surprise lands in the last third
- no line is `(rushed)` in the build's pace report
