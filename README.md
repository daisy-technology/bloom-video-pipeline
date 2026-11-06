# Bloom

Turn a Thai voiceover script into a finished, animated short video. Part of the Daisy Technology family.

You write two files: the narration (`script.md`) and the visuals as an animated web page (`scenes.html`). `bloom build` voices each scene, lays the clips on a timeline, writes subtitles, renders the page frame by frame in a headless browser and muxes it all into an MP4.

```
script.md ─► voice (OmniVoice / ElevenLabs / say) ─► mix (timeline, ducking, loudnorm) ─► subtitles (.srt)
scenes.html ─────────────────────────────────────────────────────────► render (Playwright → ffmpeg) ─► output/<name>.mp4
```

Each scene lasts exactly as long as its voice clip plus a short pause, so picture and narration stay in sync without timing anything by hand.

## Install

You need Python 3.10+, [uv](https://docs.astral.sh/uv/) and ffmpeg.

```sh
brew install ffmpeg uv
uv sync                            # includes PyTorch for OmniVoice, about 1 GB
uv run playwright install chromium
uv run python tests/test_bloom.py
```

The first OmniVoice run downloads the model (about 2.4 GB) into the Hugging Face cache.

## Make a video

```sh
uv run bloom build scripts/hello
open output/hello.mp4
```

Options: `--voice <provider>[:<variant>]` (see Voices), `--bed music.mp3` (ducked under the voice), `--size 1920x1080` (default is 1080x1920, vertical), `--fps 30`, `--out <folder>`.

A project is any folder with these two files, so it can live outside this repo.

**`script.md`**: one `## <scene-id>` heading per scene, narration below it. A space in Thai is a phrase break; subtitles split there and never inside a phrase. Write `{shown|spoken}` when the caption and the voice need different text. TTS misreads Thai abbreviations ("น." comes out as "นาฬิกา") and spells out English.

```markdown
## intro
สวัสดีครับ นี่คือบลูม

## flow +1.5
ดู {ภ.ง.ด.90|ภองอดอเก้าสิบ} บรรทัดที่ {18|สิบแปด}
```

`+1.5` after a scene id holds that scene 1.5 seconds past the end of its voice, which is useful for a closing frame. Thai spelling puts spaces around ๆ and numbers; captions treat those as glue, never as line breaks. To glue anything else, use a no-break space.

**`scenes.html`**: an ordinary page.

- One `<section data-scene="<id>">` per scene. Only the current scene is shown.
- Animate with CSS animations or the Web Animations API. Delays count from the start of the scene.
- The shown section gets a `--scene-dur` CSS variable (for example `8.4s`). Time things as a fraction of it, `animation-delay: calc(var(--scene-dur) * .4)`, and the motion follows the narration whichever voice reads it.
- An element with `id="caption"` gets the current subtitle line written into it. Leave it out if you don't want burned-in captions.
- For canvas or JS-driven motion, define `window.bloomSeek(sceneId, seconds)`. It is called before every frame.

The renderer pauses every animation and seeks it to each frame's time before taking the screenshot, so a render always comes out the same no matter how fast the machine is.

## Voices

Pick one with `--voice <provider>[:<variant>]` or `BLOOM_VOICE`. Without either, Bloom uses OmniVoice, then ElevenLabs if a key is set, then macOS `say`.

| `--voice` | What it is | Settings |
|---|---|---|
| `omnivoice[:<instruct>]` (default) | [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice), runs on your machine (Apple Silicon, CUDA or CPU), free | `BLOOM_OV_INSTRUCT` (default `female`), `BLOOM_OV_REF` + `BLOOM_OV_REF_TEXT`, `BLOOM_OV_STEPS` (32; 16 is twice as fast), `BLOOM_OV_SPEED`, `BLOOM_OV_SEED` |
| `elevenlabs[:<model_id>]` | ElevenLabs API, needs `ELEVENLABS_API_KEY` | `ELEVENLABS_VOICE_ID`, model defaults to `eleven_v3`, the one that lists Thai |
| `say[:<voice>]` | macOS built-in, offline | voice defaults to `Kanya`, `BLOOM_SAY_RATE` (175) |

**OmniVoice's model weights are CC-BY-NC: non-commercial use only.** Use ElevenLabs (on a plan that allows it) for commercial videos.

OmniVoice's design-a-voice mode (`instruct`) picks a new voice on every call, and Bloom voices each scene separately. So Bloom designs one reference clip per instruct (cached) and clones it for every scene. The voice then stays the same from scene to scene, and cloning is OmniVoice's most stable mode. For the best Thai, record 5–10 seconds of your own voice and point `BLOOM_OV_REF` at it, with the exact words in `BLOOM_OV_REF_TEXT`. OmniVoice doesn't read digits by default, so spell numbers out with `{18|สิบแปด}`.

ElevenLabs free plan: sign in, create a key under Settings → API Keys, and put `export ELEVENLABS_API_KEY=…` in `~/.zshenv`. The free plan includes API access and a monthly credit allowance, and requires attribution.

Clips are cached in `<project>/.bloom/voice/`, keyed by provider, settings and text. Re-rendering after changing only the animation doesn't synthesize or bill anything again. The cache folder ignores itself in git.

### Benchmark

```sh
uv run python bench/tts_bench.py             # every voice available here
uv run python bench/tts_bench.py --only elevenlabs
```

The same six Thai sentences (everyday, formal, numbers, English words, a question, consonant clusters) go through every voice. Each voice is scored on speed (RTF), intelligibility (character error rate of a whisper.cpp round trip; needs `brew install whisper-cpp`) and ElevenLabs credits. Results land in `output/bench/`: `report.md`, `results.json`, and `listen.html` for hearing the clips side by side. CER can't hear warmth or rhythm, so listen before you pick.

## Music and stock media

`--bed` takes any audio file and ducks it under the narration. Bloom doesn't search or download stock media itself. If your AI client is connected to a stock library's MCP server (Artlist, for example), ask it to put a track in `assets/`, then pass that file to `--bed`. Sign-in and licensing stay with you and your client, and the CLI still runs without them. `assets/` is gitignored because stock media is licensed to you, not to everyone who clones the repo.

## Layout

```
bloom/       the pipeline: script.py · voice.py · mix.py · subs.py · render.py · __main__.py
scripts/     projects: <name>/script.md + <name>/scenes.html
assets/      source videos, music, screenshots
output/      rendered videos (gitignored)
bench/       tts_bench.py, the Thai voice benchmark
tests/       python tests/test_bloom.py
```

## Not yet

- iApp Kaitom Voice. Add it to `bloom/voice.py` next to ElevenLabs when someone needs it.
- HyperFrames / onetake scenes. Today the renderer draws `scenes.html` itself. A pre-rendered clip can go in `assets/` and be played with a `<video>` tag once the renderer seeks video elements too.

## License

MIT
