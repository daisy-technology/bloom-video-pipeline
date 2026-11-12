---
status: approved
title: hello-spec
size: 1920x1080
look: iso-clean
motion: calm
voice: omnivoice:female, young adult
music: lofi
ending: question
cam: #block 1.5
---

# hello-spec

One paragraph: what this video is, who it's for, and the one thing they should leave knowing.

## cast

| id | kind | args |
|---|---|---|
| ground | tile | at="-2 -2" size="16 8" color=floor |
| file | card | at="7 -1 0.6" title=script.md text="## hello\nสวัสดี นี่คือบลูม" w=380 |
| block | box | at="1 0 0" size="3 2 2" color=c1 |
| question | ask | text="แล้วคุณจะเล่าเรื่องอะไร?" sub=github.com/daisy-technology/blooms |
| tagline | pin | at="2.5 1 2.3" text=บลูม |

## hello ~calm
> สวัสดี นี่คือบลูม เขียนบทภาษาไทยไฟล์เดียว ได้วิดีโอออกมา

| on | do | what | args |
|---|---|---|---|
| start | show | block | |
| เขียนบท | cam | file | zoom=1.3 |
| เขียนบท | show | file | |
| เขียนบท | type | file | |
| บลูม | show | tagline | |
| บลูม | sfx | pop | |

The block builds as the voice starts; on เขียนบท the camera moves to the script card, which types itself out.

## end +1.2
> แล้วคุณจะเล่าเรื่องอะไร

| on | do | what | args |
|---|---|---|---|
| start | cam | ground | zoom=0.95 |
| start | hide | tagline | |
| แล้ว | show | question | |
| -0.6 | end | cut | |

## music

| on | do |
|---|---|
| end@-0.6 | stop |
