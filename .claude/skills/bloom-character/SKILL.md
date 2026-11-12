---
name: bloom-character
description: Design an original animated pixel-art character (mascot, narrator, host animal, sidekick) for a Bloom video, then give it a Thai-capable font and a matching voice. Covers drawing the sprite as layered pixel maps in scenes.html, sprite-style motion (bob, blink, talking mouth, tail wag, swaying accessories), impact moves with squash and stretch (slam, jump, charge, camera shake, pixel debris, stamped titles) timed to their sounds, faces (joy, wow) and a mouth that follows the real voice, bundling a Google Font such as Mali, Kanit or Sriracha for captions, picking an OmniVoice voice (girl, boy, woman, old man), previewing frames in seconds with peek.py, and building on a remote GPU. Use it whenever someone wants a character, mascot or animated animal in a Bloom video, asks for pixel or 8-bit art in scenes.html, wants to change a Bloom video's caption font or narrator voice to fit a character, or says things like "ทำตัวละคร", "มาสคอต", "แมวพิกเซล", "pixel cat in a hat", even if they never say "skill" or "sprite".
---

# Bloom character

A Bloom picture is an ordinary web page (`scenes.html`) that the renderer seeks frame by frame, so a character is an inline SVG built from pixel maps, animated with CSS `steps()`. This skill turns a one-line idea ("a pixel cat in a flower hat, girl's voice, Mali font") into a project that renders cleanly the first time.

The worked example is `scripts/flower-cat/` in this repo. Read its `scenes.html` once before starting, because it uses every pattern below. Start from the blank `assets/character-template.html` (next to this file), which already carries the impact kit (`assets/impact.css`). The `bloom-sound` skill covers which sound lands on which move and how the voice delivers its lines. `bloom-visual` covers how the whole frame should look and move (composition, the 12 principles, icons, anti-slop).

## Workflow

1. Write a short brief (in your head or in a comment at the top of script.md): species or object, one signature accessory, a 6–10 colour palette, personality shown through motion, voice, font. See "Making it original" below.
2. Start the project. Create `scripts/<name>/` with `script.md` and a `scenes.html` copied from `assets/character-template.html`. Each `## id` in script.md needs a `<section data-scene="id">`.
3. Draw the sprite as character maps (one letter per pixel, `.` transparent) and split it into layers: what sits behind the body (tail, back wing), the body, overlays (closed eyes, open mouth), and what the character wears (hat, bow). The `px()` helper in the template turns maps into merged `<rect>`s.
4. Animate the layers (see "Motion"). Then give each scene one big move from the impact kit, timed into a gap of the voice, with its sound on the same element (see "Impact").
5. Bundle the font (see "Fonts") and point `@font-face` at `fonts/`.
6. Pick the voice (see "Voices") and write the full render command in a comment at the top of script.md, so anyone can rebuild with the same voice.
7. Preview without voicing:
   ```sh
   uv run python .claude/skills/bloom-character/scripts/peek.py scripts/<name>
   ```
   It takes a few seconds and writes `scripts/<name>/.bloom/peek/sheet.png` (one frame per scene). It fails on the mistakes that would otherwise render silently: a dropped `animation` declaration, a missing `@keyframes`, a font that didn't load, a character outside the frame, a script scene with no section. Look at the sheet as well as the report, since only an eye can judge proportions, gaps between layers, and whether the character reads at a glance. Fix and re-run until it's clean. A full build spends minutes on voice, so don't use it to check the picture.
8. Build. `uv run bloom remote list` names the computers you've added, and `uv run bloom remote check <name>` says whether one is reachable and has a GPU with OmniVoice. If it does, run the voice there:
   ```sh
   uv run bloom build scripts/<name> --voice "omnivoice:female, child, high pitch" --voice-on <remote>
   ```
   Otherwise drop `--voice-on`. If Whisper flagged any lines, open `output/<name>.review.html`.

## Making it original

Design a new character. Don't redraw an existing one (Hello Kitty, Pusheen, Pikachu, a brand mascot), even under a new name. An original design comes from a few deliberate choices:

- Give it one clear silhouette: a big head, a small body, and one shape that sticks out (ears, a tail curl, a hat brim). At 1080 px wide the sprite is scaled about 20–30×, so a 24–40 px grid is plenty. Bigger grids stop reading as pixel art and look like blurry photos.
- Give it one signature accessory that the story can use (the flower hat that grandma knitted), on its own layer so it can sway.
- Keep the palette small: a dark outline colour, one main colour, one belly or muzzle colour, a cheek or accent colour, and the accessory colours. Skip pure black; a dark plum or brown outline looks softer.
- Show personality through motion. A shy character blinks often and bobs slowly; an excited one bobs fast and wags. Two-frame loops are enough.
- Get symmetry by counting. For a face on a `W`-wide grid, a feature at columns `a..b` mirrors to `W-1-b..W-1-a`. Count each row's length, because a row one character short shifts everything after it.

## Motion

The renderer pauses every animation and sets its time each frame, so CSS animations, including `infinite` ones, render the same on every machine. Follow these rules:

- Inside the sprite's SVG, `1px` in a transform is one sprite pixel (the viewBox is in grid units), so `translateY(-1px)` bobs by exactly one pixel.
- Use `steps(1)` toggles between keyframes for sprite-like snapping: bob `50% { transform: translateY(-1px) }`, blink `0% {opacity:0} 94% {opacity:1}` on a closed-eyes overlay, talk `0% {opacity:1} 50% {opacity:0}` on an open-mouth overlay.
- Swap two poses (tail, wand, wing) with two mirror-image keyframes on the same duration: `poseA { 0% {opacity:1} 50% {opacity:0} }` and `poseB { 0% {opacity:0} 50% {opacity:1} }`. **Don't reuse one animation with `reverse`.** With `steps()`, a reversed animation switches one frame boundary off from the forward one, so any frame that lands exactly on the halfway point shows neither pose. Whether that happens depends on the period: 0.6 s at 30 fps hits it, 0.7 s doesn't. peek.py flags `steps()` with `reverse`.
- **Give an `animation` shorthand only one timing function.** `steps(30) infinite linear` is invalid, so the browser drops the whole declaration and the element never moves. Nothing in the console reports it; peek.py catches it.
- Keep worn things inside the bob group. A hat that bobs on its own timing lifts a pixel off the head and leaves a visible gap. Sway the decoration (the flower) inside the group instead.
- Put the entry animation on a wrapper (`.stage`) carrying `data-sfx`. Bloom times an element's sounds from its *first* animation (`pop` as it starts, `hit@end` as it ends, `zip@.2` 0.2 s in), so the looping parts must live on children.
- Time things against narration with `calc(var(--scene-dur) * .5)` when something should happen mid-line.
- Let the mouth follow the voice. Bloom sets `html[data-mouth]` (0 shut, 1 half, 2 open) on every frame from the real audio. Draw an open mouth (`.talk`) and a half-open one (`.talk-half`) as overlays; the kit's rules show the right one, so the mouth rests in pauses and after the line instead of flapping on a loop. In peek.py and a plain browser, `.talk` still loops. `.voice-pulse` on the sprite's `<svg>` swells it a few percent on loud syllables.
- Fit the frame. The default video is 1080×1920 (vertical). Size the `.stage` so the whole sprite, tail and hat included, stays inside the frame, and mark the sprite `data-character` so peek.py checks it. For a close-up scene, put the same sprite in a bigger stage; don't draw a new one.

## Impact

Paste `assets/impact.css` into the page's `<style>` after the `.stage` rule (the template has it). Every move lands at `--at`, set inline in seconds from the scene start, so the motion and its sound share one number:

| Class | On | What it does | Sound on the same element |
|---|---|---|---|
| `slam` | `.stage` | falls in stretched, squashes flat on contact, springs back | `hit@end` |
| `jump` | `.stage` | crouch (anticipation), stretch up, hang, stretch down, squash on landing; lands at `--at` | `zip@.18 thud@.86` |
| `charge` | `.stage` | shivers and gathers for `--len`, releases big at `--at` | `riser sparkle@end` |
| `stamp` | a headline | comes down big and lands with a small overshoot | `hit@end`, `sting@end` on the final card, or none when the voice says the word |
| `shake` | the `<section>` | the camera takes the hit, decaying in 0.4 s; captions stay still | (the hit) |
| `flash` | `<i class="flash">` | two or three white frames | (the hit) |
| `burst` | `<div class="burst" data-n data-r data-up>` | pixel debris from `--x`/`--y` in `--c`; `data-up` sprays only upward (dust off the ground). Filled by `fillBursts()` | (the hit) |

- **One big move a scene, in a gap of the voice.** The voice starts 0.35 s into each scene: a slam at `--at: .3s` lands before the first word, a reveal goes on a phrase break, and a jump and the closing sting go after the last word (`--at: calc(var(--scene-dur) - 1.1s)`). A move that lands on a word the voice is saying competes with it.
- Squash and stretch keep the volume: stretched tall means narrower (`scale(.84, 1.22)`), and squashed flat means wider. `transform-origin: 50% 100%` keeps the feet on the ground.
- Shake only on impacts. A shake on every scene stops meaning anything.
- Draw each face as overlay layers with class `face face-joy` (or `face-wow`, `face-sad`), painted after the eyes and mouth, and list the ones a scene uses on the stage: `data-face="wow joy" style="--wow-at: .3s; --wow-end: 1.05s; --joy-at: 1.05s"`. Surprise before a reveal and joy after it read as a reaction, and that makes a character feel alive.
- Check the move at several times around a landing (`peek.py --at .2`, `--at .35`, `--at .6`), and compare the `sounds` lines peek prints with where the words fall.

## Fonts

Captions and titles use the project's own font files, never a system font. Chromium in the renderer may not see fonts that macOS downloads on demand (Mali, for example), and without the file the video silently falls back to another face.

1. Find the family folder: `https://api.github.com/repos/google/fonts/contents/ofl/<lowercasename>` lists the files. Static families have `Family-Medium.ttf` / `Family-Bold.ttf`. Some are variable fonts (`Family[wght].ttf`); for those, use one `@font-face` with `font-weight: 100 900`.
2. Download the weights you use, plus `OFL.txt`, into `scripts/<name>/fonts/` from `https://raw.githubusercontent.com/google/fonts/main/ofl/<name>/<file>`. The OFL lets you redistribute them with the project as long as the licence file comes along.
3. Keep `document.fonts.forEach(f => f.load())` in the page script (the template has it). A face that no visible text uses at load time stays unloaded, Bloom's `fonts.ready` doesn't wait for it, and the first captions come out in a fallback font.

Thai-capable families that suit characters: Mali (round, handwritten, cute), Itim (casual marker), Sriracha (brush handwriting), Kodchasan and Mitr (friendly rounded), Kanit and Prompt (clean, bold titles), and Chonburi (display headline). Google Fonts has no Thai pixel font, so the pixel feel comes from the sprite and the caption box (thick square border, hard offset shadow). Keep the text smooth.

## Voices

Pass `--voice "omnivoice:<instruct>"`. The instruct is a comma-and-space list from OmniVoice's fixed vocabulary, and anything else is rejected.

- gender: `male`, `female`
- age: `child`, `teenager`, `young adult`, `middle-aged`, `elderly`
- pitch: `very low pitch`, `low pitch`, `moderate pitch`, `high pitch`, `very high pitch`
- style: `whisper`

| Character asks for | instruct |
|---|---|
| little girl, cute girl | `female, child, high pitch` |
| little boy | `male, child, high pitch` |
| teen girl / teen boy | `female, teenager` / `male, teenager` |
| young woman, office worker | `female, young adult` |
| grandpa | `male, elderly, low pitch` |
| a secret or bedtime voice | add `whisper` |

Bloom designs one reference clip per instruct and clones it for every line, so the voice stays the same across scenes. Match the script to the voice: a girl says ค่ะ/นะคะ, a boy ครับ. Write `{shown|spoken}` for anything the voice would misread. OmniVoice's weights are non-commercial (CC-BY-NC). For client or paid work, say so and use `--voice elevenlabs` on a plan that allows it.

For a voice that sounds like a real person (the user), run `uv run bloom voice record <name>`, then build with `--voice omnivoice:@<name>`.

## Keep private work private

Bloom is public and videos get shared, so a video about private work is anonymized by default. Leave out product, repo, org and customer names, file paths, class, table and column names, ticket and alert numbers, and private URLs. Say "a server of ours" or "our audit log" instead. Public facts can stay: package and framework names, versions, CVE/GHSA IDs, scores. Put such a project outside this repo (for example `~/…/bloom-videos/<name>/`) and build it with `--out` there. Before building, grep the project for every private name you met while researching, and grep the `.srt` for them afterwards. Include a name only when the user asks for it.

## Checklist before handing over

- peek.py says `ok`, and you've looked at sheet.png
- the font files and `OFL.txt` are in `fonts/`
- script.md's top comment has the exact build command with the voice
- the character is your own design, and you can say in one line what makes it recognisable
- each scene has at most one big move, landing in a gap of the voice, with its sound on the same element (peek.py's `sounds` lines)
- the mouth has `.talk` and `.talk-half` layers, so it follows the voice
