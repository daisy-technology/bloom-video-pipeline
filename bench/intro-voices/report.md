# Bench: the 16:9 intro, three voices and soundtracks

Same picture (`scripts/intro-longtake`, one long take), same script, re-timed to each voice with
`bloom-sound/scripts/revoice.py`; only the voice and the music change. The current version is the reference.

| | current | A · warm | B · calm | C · upbeat |
|---|---|---|---|---|
| voice | OmniVoice `male` | OmniVoice female, young adult | OmniVoice male, low pitch, middle-aged | your voice (`@me-v4`) |
| music | Bloom built-in, calm → bright | Bloom built-in lofi | Artlist, Lyria 3 Pro: slow cinematic ambient | Artlist, Lyria 3 Pro: upbeat electronic pop |
| video | `output/intro-longtake.mp4` | `output/intro-voices/intro-longtake-a-warm.mp4` | `…-b-calm.mp4` | `…-c-upbeat.mp4` |
| length | 52.3 s | 51.0 s | 61.1 s | 62.9 s |
| pace (Thai ch/s, natural ≈ 15) | 13.6–16.9, avg 15.6 | 14.3–17.2, avg 15.9 | 11.5–13.8, avg 12.8 | 11.2–13.4, avg 12.4 |
| lines flagged rushed / dragging | 0 | 0 | 0 | 0 |
| Whisper lines flagged | 5 of 10 | 3 of 10 | 5 of 10 | 3 of 10 |
| loudness | −14.1 LUFS, −1.2 dBTP | −14.0, −1.4 | −14.1, −1.4 | −14.2, −1.2 |
| seek check · audit | pass · 0 errors | pass · 0 errors | pass · 0 errors | pass · 0 errors |

Most Whisper flags are the same in every version: English loanwords written in English ("Bloom", "Render",
"Animation", "Open Source") and ไฟล์ heard as ไฟ. The current and B versions also drop the start of the last line
("ลูมเป็น"), which A and C don't.

Music balance is the same by construction: Bloom normalizes every bed to −26 LUFS, ducks it under the voice and
stops it on the end cut. What differs is character, which only listening can judge.

## Scores (simulated: from the numbers and the brief, not from listening)

1–5 each. I can't hear the takes; the person's ear decides.

| Criterion | current | A warm | B calm | C upbeat |
|---|---|---|---|---|
| Clarity (Whisper, pace) | 3 | 4 | 3 | 4 |
| Fits the clean isometric look | 3 | 4 | 4 | 4 |
| Energy for a montage | 3 | 3 | 2 | 4 |
| Finish (loudness, ending) | 4 | 4 | 4 | 4 |
| Length for a README hero (≤ 60 s) | 5 | 5 | 3 | 3 |
| **Total** | 18 | **20** | 16 | **19** |

- **A** is the safest README hero: the clearest delivery at a natural pace, and the shortest.
- **C** has the most energy and the most personal voice (yours), but runs 63 s; trimming two lines would bring it under 60.
- **B** is the most "premium" in mood but the slowest; better for a calm YouTube explainer than a hero clip.

Licence: B and C's music are Artlist generations made on a free trial. Check Artlist's terms for free-trial
generations before publishing either one on the README or site.
