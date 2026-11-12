# Bench: ถ้าอินเทอร์เน็ตทั้งโลกหายไป — three versions

## Prompt (verbatim)

> สร้างเรื่องเกี่ยวกับว่าถ้า internet บนโลกหายไปจะเกิดอะไรขึ้นบ้างใน 1 วัน, 1 เดือน, 1 ปี และเหตุผลที่ทำให้ internet หายไปได้ ทำให้ดูน่าตกใจ และอ้างอิงตามงานวิจัยจริงที่มี ถ้าไม่มีให้ถามก่อนว่าจะเปลี่ยนเรื่องมั้ย

**Research gate: passed.** The premise rests on a peer-reviewed paper (Abdu Jyothi, ACM SIGCOMM 2021: solar superstorms could cause global, months-long Internet outages, 1.6–12% chance per decade), a US National Research Council report (2008), and real events (Tonga 2022, Red Sea 2024, Visa Europe 2018). Twelve claims were checked against primary sources; every claim the videos make is in [research.md](research.md), and the ones dropped or reworded are listed under "Not used". No need to ask about changing the topic.

Pipeline: `bloom-story` (idea → research → structure → cast → act it out → review), voices on the laptop GPU (`--on laptop`, RTX 3050; about 1 min of voicing and 1.3 min of rendering per video), props timed with `when.py`, icons from `bloom-visual/scripts/icons.py`.

## The versions

| | news | doc | diary |
|---|---|---|---|
| project | `scripts/no-internet-news` | `scripts/no-internet-doc` | `scripts/no-internet-diary` |
| style | emergency broadcast: red/black, BREAKING bar, ticker | documentary on deep navy, sea cables | pixel bedroom, day note, window |
| character | TV-headed anchor (screen face turns to static) | home router narrating (LED eyes → red X) | a boy with a phone (no signal) |
| voice | OmniVoice male, middle-aged, low pitch | OmniVoice female, young adult | OmniVoice male, child, high pitch |
| music | `tense` | `lofi` | `chip` |
| font | Kanit | Mitr | Mali |
| ending | "เตรียมพร้อม ไม่ตื่นตระหนก" | a message to Mum that never sends: "คุณจะติดต่อคนที่คุณรักยังไง?" | he writes Mum's number in his notebook |

Every beat is acted out: the globe's signal turns to ✕, a solar blast sets Earth on fire (1859) and then misses it (2012), a sea cable breaks (a repeater fails first in *doc*), a QR payment at a rice stall fails with a buzz, a card is DECLINED (*doc*), a volcano erupts and cuts Tonga's cable while a calendar counts 38 days offline and a repair ship sails in, a calendar runs to day 365 while the damage counts up, the 1.6–12% band fills on a bar.

## Measured

| | news | doc | diary |
|---|---|---|---|
| length | 90.0 s | 78.2 s | 72.5 s |
| pace flags | 2 lines `(drags)` (sun 9.9, odds 9.7 ch/s) | none | none |
| Whisper check | 0 of 8 flagged | 0 of 8 | 0 of 8 |
| loudness | −14.0 LUFS, −1.4 dBTP | −14.0 LUFS, −1.3 dBTP | −14.0 LUFS, −1.5 dBTP |
| sources on screen | 7 of 7 factual scenes | 7 of 7 | 7 of 7 |
| claims used verified | 100 % | 100 % | 100 % |
| effects | 26 | 22 | 28 |
| visual audit before | 83 errors, 38 warnings | 60 errors, 28 warnings | 36 errors, 11 warnings |
| visual audit after | 0 errors, 0 warnings | 0 · 0 | 0 · 0 |
| ticker across cuts | 7 px/frame at all 7 cuts (its normal speed) | — | — |

The audit (`bloom-visual-audit`) found the faults visible in the first renders: headlines stamping in at 2.8× ran off the frame for a few frames in every scene, the diary's day notes grew over their source line, counters' labels collided with their numbers, a page rule hid the sea's captions, the repair ship sailed over the Tonga caption, and the news ticker restarted at every cut (the renderer now runs anything outside the sections on the video's clock). The doc was re-laid on one grid (title 190 · source 275 · prop 340–1080 · narrator 1110 · captions 1600).

## Scored (simulated panel: scroller, sceptic, target viewer; 1–5)

Simulated reads, written by the agent, not audience feedback.

| Criterion | news | doc | diary |
|---|---|---|---|
| Hook | 4: "อินเทอร์เน็ตดับทั้งโลก" stamps in at 0.3 s with a hit; the globe goes ✕ at 3.4 s | 4: big question at 0.3 s, but the world only goes dark at 6.2 s | 4: diary note at 0.3 s, globe ✕ at 3.6 s, a child's voice is an unusual hook |
| Directness | 4 | 4 | 4 |
| Detail | 4: rice stall QR, volcano, ship | 5: plus a failing repeater and a declined card | 4 |
| Empathy | 2: institutional; nobody we care about loses anything | 4: "คุณ" throughout; the unsent message to Mum | 5: Mum can't pay for lunch; he writes her number down |
| Escalation & timing | 4: each step bigger; results land on their words | 4 | 4 |
| Truth | 5: every number sourced, the scenario labelled | 5 | 5: facts in a diary voice ("ผมอ่านเจอว่า"), still sourced |
| Shown, not told | 4: props carry each beat; the anchor is a small witness | 5 | 4: sun scene crowded (two blasts and the boy) |
| Craft fit | 5: newsroom, anchor, low voice, tense music agree | 4: router reads as narrator, but small on screen | 5: room, kid, chiptune agree |
| Editing | 3: 90 s, two slow lines | 4 | 5: tightest at 72 s |

Contact sheets (key moments from the rendered MP4s): [news](no-internet-news.moments.png) · [doc](no-internet-doc.moments.png) · [diary](no-internet-diary.moments.png)

## Verdict

- **For a general Thai short-video audience: *diary*.** The most personal, the shortest, and the one a viewer would share; the facts land through what happens to one family.
- **For an explainer or a school/organisation channel: *doc*.** The most detail shown on screen (repeater, declined card), and the strongest ending question.
- **For urgency: *news*, after an edit.** It has the most impact but the least empathy and runs 90 s.

One change each:
- news: cut "จนกระดาษลุกไหม้" and shorten the odds line (both flagged slow), and end on one person (a viewer's phone) instead of the anchor.
- doc: make the router bigger in the hook and end, so the narrator is seen while it speaks.
- diary: split the sun scene: 1859 first, then 2012 alone, so only one event is on screen at a time.

## Motion rework (bloom-motion)

The same three stories, rebuilt as animation with the `bloom-motion` skill. Each version is a copy (`scripts/no-internet-<version>-motion`) with the same facts, sources, palette, font, character and voice; only the picture changed, plus one new rule: every video ends on a hook (a question, then a cut or fade to black, and the music stops with the picture). News and diary got a new closing question, voiced with the same reference voice; doc already ended on one.

| | news | doc | diary |
|---|---|---|---|
| video | `output/story/no-internet-news-motion.mp4` | `output/story/no-internet-doc-motion.mp4` | `output/story/no-internet-diary-motion.mp4` |
| length | 90.6 s | 78.2 s | 74.3 s |
| motion language | energetic, unit .2 s | calm documentary, unit .6 s | playful, unit .25 s, 12 fps hand-drawn marks |
| ending | "คุณพร้อมแล้วหรือยังครับ", the signal bursts to static, hard cut | "คุณจะติดต่อคนที่คุณรักยังไงคะ", the last LED dying is the cut | "แล้วคุณล่ะ จำเบอร์ใครได้บ้าง", the notebook closes, fade |
| effects | 39 | 38 | 31 |
| loudness | −14.1 LUFS, −1.4 dBTP | −14.0 LUFS, −1.5 dBTP | −14.0 LUFS, −1.5 dBTP |
| Whisper check | 0 of 8 flagged | 0 of 8 | 0 of 8 |
| seek check (frames drawn in and out of order) | 375 match | 325 match | 310 match |
| longest quiet stretch in a scene | 0.5 s | 2.0 s | 1.5 s |
| visual audit | 46 → 0 errors, 5 warnings accepted | 66 → 0 errors, 0 warnings | 0 errors, 3 warnings accepted |

What changed is the staging. Before, every scene was the same layout: a headline, a card in the middle, the character at the bottom, and only pop-ins. After, each scene is a place the camera moves through (the sea floor, Tonga, a stall, a city at night), things draw on and count on the words that name them, and cuts carry something across (one Earth through hook → sun → cable in doc; the globe match cut in news). Last section's "one change each" are done too: diary's sun scene is split into three shots, doc's router acts inside every world, and news ends on a question to the viewer.

Before/after sheets, one frame per scene at 70 % of it: [news](no-internet-news.compare.png) · [doc](no-internet-doc.compare.png) · [diary](no-internet-diary.compare.png)

Checked on the real render: after the cut the frame is black (luma 0.0) and the audio falls from about −16 dB to −59 dB once the hit's tail has decayed.
