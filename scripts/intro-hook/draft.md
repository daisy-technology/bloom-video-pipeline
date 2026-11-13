---
status: approved
title: intro-hook
size: 1920x1080
look: iso-clean
motion: calm
voice: omnivoice:female, young adult
music: lofi
ending: question
cam: #clock 1.2
---

# intro-hook

The Bloom intro for the README and site hero, v2. It covers everything the first intro (`scripts/intro-longtake`) covered: the script, the voice, the picture, the sound, the MP4, the skills, the before/after and the three styles. It's run as a Hook-model loop (trigger → action → variable reward → investment), so it opens on the viewer's itch instead of on what Bloom is, and every station pays off in a different way. For Thai creators and developers; they should leave knowing what Bloom does from script to MP4, and wanting to write their first script.

Hook loop:

- itch (internal trigger): "คลิปแค่นาทีเดียว ทำไมต้องตัดต่อทั้งวัน", said before Bloom is named
- action: stay 3 more seconds; the first reward (the reveal) lands in scene 2
- rewards, never the same kind twice in a row: reveal (this clip is a file) → the beats table, word to action → number (15 s of your voice) → the picture landing on the exact word "ตอนนี้" → a meter settling at −14 LUFS → the finished file → "แบบคลิปนี้" (the skill that made what you're watching) → before/after flip → surprise (one story, three styles)
- investment: write your first scene and say in a comment what it's about

The before/after scene plays the bench's news clips (8×5 sprite sheets copied from `scripts/intro-longtake/media/`) on two `phone`s.

## cast

| id | kind | args |
|---|---|---|
| ground | tile | at="-2 -3" size="84 9" color=floor |
| desk | box | at="0 -1 0" size="3 2 1" color=c4 |
| clock | count | at="1 0 1.6" from=0 to=8 suf=" ชม." label="ตัดต่อคลิป 1 นาที?" |
| itch | headline | text="คลิป 1 นาที\nทำไมต้องตัดต่อทั้งวัน?" |
| file | card | at="7 -1 0.6" title=intro-hook/draft.md text="## hook\nคลิปแค่นาทีเดียว…\n## file\nคลิปนี้ไม่ได้ตัดต่อเลย…" w=400 |
| filetag | pin | at="6 1 0.3" text="ไฟล์เดียว" |
| beats | card | at="14 -1 0.6" title="## voice" text="on · do · what\nแค่ · count · 15 วินาที\nวินาที · sfx · chime" w=420 |
| beatstag | pin | at="11 3 0" text="คำไหน ภาพทำอะไร" |
| mic | box | at="21 0 0" size="2 2 2" color=c1 |
| secs | count | at="22 1 2.8" from=0 to=15 suf=" วินาที" label="เสียงคุณ" |
| stage | box | at="28 0 0" size="3 2 1" color=c2 |
| pop | box | at="29 0.5 1" size="1 1 1" color=c3 |
| poptag | pin | at="29.5 1 2.4" text="ตอนนี้" |
| speaker | box | at="35 0 0" size="2 2 3" color=c4 |
| lufs | count | at="36 1 3.8" from=-30 to=-14 suf=" LUFS" label="ความดังมาตรฐาน" |
| mp4 | card | at="42 -1 0.6" title=intro-hook.mp4 text="▶ เล่นได้เลย\nซับไทยในตัว\nปิดเสียงก็ดูรู้เรื่อง" w=340 |
| story | box | at="46 0 0" size="2 2 1" color=c1 |
| motion | box | at="51 0 0" size="2 2 2" color=c2 |
| longtake | box | at="56 0 0" size="2 2 3" color=c3 |
| storytag | pin | at="47 1 1.4" text="bloom-story" |
| motiontag | pin | at="52 1 2.4" text="bloom-motion" |
| longtaketag | pin | at="57 1 3.4" text="bloom-longtake" |
| before | phone | at="60 0 0.4" sheet=media/news-before.jpg w=200 label="ก่อน: เหมือนสไลด์" |
| after | phone | at="63 -3 0.4" sheet=media/news-after.jpg w=200 label="หลัง: แอนิเมชัน" |
| news | card | at="72 3 0.6" title=ข่าว text="เน็ตดับทั้งโลก" w=240 |
| doc | card | at="72 -1 0.6" title=สารคดี text="เน็ตดับทั้งโลก" w=240 |
| diary | card | at="72 -5 0.6" title=ไดอารี่ text="เน็ตดับทั้งโลก" w=240 |
| question | ask | text="บทแรกของคุณ จะเล่าเรื่องอะไร?" sub=github.com/daisy-technology/blooms |

## hook ~calm
> คลิปแค่นาทีเดียว ทำไมต้องตัดต่อทั้งวัน

| on | do | what | args |
|---|---|---|---|
| start | show | desk | |
| start | show | clock | |
| start | count | clock | len=2.4 |
| 0.3 | show | itch | |
| ทั้งวัน | sfx | buzz | |

The internal trigger. The first frame already moves (the clock counts up) and the headline reads with the sound off. Bloom isn't named yet.

## file
> คลิปนี้ไม่ได้ตัดต่อเลย มันมาจากไฟล์นี้ ไฟล์เดียว

| on | do | what | args |
|---|---|---|---|
| start | hide | itch | |
| start | hide | clock | |
| start | cam | file | zoom=1.3 |
| คลิปนี้ | show | file | |
| ไม่ได้ | type | file | len=2.2 |
| ไฟล์เดียว | show | filetag | |
| ไฟล์เดียว | sfx | pop | |

Reward 1, a reveal: the card types out the opening lines of this very draft, so the viewer learns that what they're watching is the output.

## script
> นี่คือบลูม คุณเขียนบทภาษาไทยเป็นฉาก ๆ แล้วบอกว่าคำไหน ให้ภาพทำอะไร

| on | do | what | args |
|---|---|---|---|
| start | hide | file | |
| start | hide | filetag | |
| start | cam | beats | zoom=1.3 |
| บลูม | show | beats | |
| เขียนบท | type | beats | len=2 |
| คำไหน | show | beatstag | |
| คำไหน | sfx | pop | |

Reward 2, the mechanism: a beats table shows a word mapped to an action. These are the real lines that drive the next scene.

## voice
> บลูมพากย์ให้ทุกฉาก ด้วยเสียงที่รันบนเครื่องคุณเอง หรือเสียงคุณ จากคลิปอัดแค่ 15 วินาที

| on | do | what | args |
|---|---|---|---|
| start | hide | beats | |
| start | hide | beatstag | |
| start | cam | mic | zoom=1.2 |
| บลูม | show | mic | |
| เสียงคุณ | show | secs | |
| แค่ | count | secs | len=1.2 |
| วินาที | sfx | chime | |

Reward 3, a number: 15 counts up on the words that say it, which is exactly the beat the previous card showed.

## scenes
> ภาพสร้างจากบททีละเฟรม ทุกอย่างขยับตรงคำที่พูด อย่างคำว่า ตอนนี้

| on | do | what | args |
|---|---|---|---|
| start | hide | secs | |
| start | cam | stage | zoom=1.3 |
| ภาพ | show | stage | |
| ตอนนี้ | show | pop | len=.3 |
| ตอนนี้ | show | poptag | |
| ตอนนี้ | sfx | hit | |

Reward 4, the promise kept on screen: a block drops exactly on "ตอนนี้".

## sound ~bright
> เพลงเปลี่ยนตามอารมณ์ของฉาก เสียงประกอบลงตามจังหวะ แล้วปรับความดังให้ได้มาตรฐาน

| on | do | what | args |
|---|---|---|---|
| start | hide | poptag | |
| start | cam | speaker | zoom=1.2 |
| เพลง | show | speaker | |
| เสียงประกอบ | sfx | pop | |
| ปรับ | show | lufs | |
| ปรับ | count | lufs | len=1.4 |

Reward 5, a meter: loudness counts from −30 and settles at −14 LUFS on "มาตรฐาน". The music turns brighter at this scene (`~bright`), so the viewer hears the change being described.

## mp4
> ได้ไฟล์ {MP4|เอ็มพีโฟร์} พร้อมซับในตัว ปิดเสียงดูก็ยังรู้เรื่อง

| on | do | what | args |
|---|---|---|---|
| start | hide | lufs | |
| start | cam | mp4 | zoom=1.2 |
| ไฟล์ | show | mp4 | |
| ซับ | type | mp4 | |
| รู้เรื่อง | sfx | chime | |

Reward 6, the payoff: the finished file.

## skills
> แล้วยังมีสกิลให้เอเจนต์ช่วย {bloom-story|บลูมสตอรี่} หาเรื่องและตรวจข้อมูล {bloom-motion|บลูมโมชัน} ทำให้ภาพขยับ {bloom-longtake|บลูมลองเทค} ถ่ายยาวไม่ตัด แบบคลิปนี้

| on | do | what | args |
|---|---|---|---|
| start | hide | mp4 | |
| start | cam | motion | zoom=0.9 |
| bloom-story | show | story | |
| bloom-story | show | storytag | |
| bloom-motion | show | motion | |
| bloom-motion | show | motiontag | |
| bloom-longtake | show | longtake | |
| bloom-longtake | show | longtaketag | |
| แบบคลิปนี้ | sfx | chime | |

Reward 7, a callback: three blocks rise one per skill, and "แบบคลิปนี้" points back at the long take the viewer is inside.

## before
> จากวิดีโอที่ดูเหมือนสไลด์ กลายเป็นแอนิเมชัน เรื่องเดียวกัน

| on | do | what | args |
|---|---|---|---|
| start | hide | storytag | |
| start | hide | motiontag | |
| start | hide | longtaketag | |
| start | cam | before | zoom=1 |
| จาก | show | before | |
| จาก | play | before | |
| กลายเป็น | show | after | |
| กลายเป็น | play | after | |
| กลายเป็น | sfx | whoosh | |

Reward 8, the turn: the same news story from the bench, playing on two phones: before (slide-like) appears on "จาก", and after (animated) joins it on "กลายเป็น".

## styles
> เรื่องเน็ตดับทั้งโลก เล่าได้ทั้งแบบข่าว สารคดี และไดอารี่

| on | do | what | args |
|---|---|---|---|
| start | hide | before | |
| start | hide | after | |
| start | cam | doc | zoom=1.25 |
| ข่าว | show | news | |
| สารคดี | show | doc | |
| ไดอารี่ | show | diary | |
| ไดอารี่ | sfx | pop | |

Reward 9, the surprise in the last third: one story, three styles, one card per word.

## end +1.2
> ลองเขียนบทแรกของคุณดู บลูมเป็นโอเพนซอร์ส แล้วบอกเราหน่อย คุณจะเล่าเรื่องอะไร

| on | do | what | args |
|---|---|---|---|
| start | hide | news | |
| start | hide | doc | |
| start | hide | diary | |
| start | cam | speaker | zoom=0.4 |
| ลองเขียน | show | question | |
| -0.6 | end | cut | |

The investment: the cards step aside, the camera pulls out over every station, and the viewer is asked to write one scene and answer in a comment. The line now opens on "ลองเขียน" instead of "บลูม", whose first sound the voice dropped in v1. Cut to black, and the music stops with it.

## music

| on | do |
|---|---|
| end@-0.6 | stop |
