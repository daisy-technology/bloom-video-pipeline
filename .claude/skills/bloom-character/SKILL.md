---
name: bloom-character
description: Design an original animated pixel-art character (mascot, narrator, host animal, sidekick) for a Bloom video, then give it a Thai-capable font and a matching voice. Covers drawing the sprite as layered pixel maps in scenes.html, sprite-style motion (bob, blink, talking mouth, tail wag, swaying accessories), bundling a Google Font such as Mali, Kanit or Sriracha for captions, picking an OmniVoice voice (girl, boy, woman, old man), previewing frames in seconds with peek.py, and building on a remote GPU. Use it whenever someone wants a character, mascot or animated animal in a Bloom video, asks for pixel or 8-bit art in scenes.html, wants to change a Bloom video's caption font or narrator voice to fit a character, or says things like "ทำตัวละคร", "มาสคอต", "แมวพิกเซล", "pixel cat in a hat", even if they never say "skill" or "sprite".
---

# Bloom character

A Bloom picture is an ordinary web page (`scenes.html`) that the renderer seeks frame by frame, so a character is an inline SVG built from pixel maps, animated with CSS `steps()`. This skill turns a one-line idea ("a pixel cat in a flower hat, girl's voice, Mali font") into a project that renders cleanly the first time.

The worked example is `scripts/flower-cat/` in this repo. Read its `scenes.html` once before starting: it shows every pattern below in about 150 lines. The blank starting point is `assets/character-template.html` (next to this file).

## Workflow

1. **Write a short brief** (in your head or in a comment at the top of script.md): species or object, one signature accessory, a 6–10 colour palette, personality shown through motion, voice, font. See "Making it original" below.
2. **Start the project.** Create `scripts/<name>/` with `script.md` and `scenes.html` copied from `assets/character-template.html`. Each `## id` in script.md needs a `<section data-scene="id">`.
3. **Draw the sprite** as character maps (one letter per pixel, `.` transparent) and split it into layers: what sits behind the body (tail, back wing), the body, overlays (closed eyes, open mouth), and what's worn (hat, bow). The `px()` helper in the template turns maps into merged `<rect>`s.
4. **Animate the layers** (see "Motion").
5. **Bundle the font** (see "Fonts") and point `@font-face` at `fonts/`.
6. **Pick the voice** (see "Voices") and write the full render command in a comment at the top of script.md, so anyone can rebuild with the same voice.
7. **Preview without voicing**:
   ```sh
   uv run python .claude/skills/bloom-character/scripts/peek.py scripts/<name>
   ```
   It takes a few seconds, writes `scripts/<name>/.bloom/peek/sheet.png` (one frame per scene), and fails on the mistakes that otherwise render silently: a dropped `animation` declaration, a missing `@keyframes`, a font that didn't load, a character outside the frame, a script scene with no section. Look at the sheet, not just the report: proportions, gaps between layers, and whether the character reads at a glance can only be judged by eye. Fix and re-run until it's clean. A full build spends minutes on voice, so don't use it to check the picture.
8. **Build.** `uv run bloom remote list` names the computers you've added, and `uv run bloom remote check <name>` says whether one is reachable and has a GPU with OmniVoice. If it does, run the voice there:
   ```sh
   uv run bloom build scripts/<name> --voice "omnivoice:female, child, high pitch" --voice-on <remote>
   ```
   Otherwise drop `--voice-on`. Then open `output/<name>.review.html` if Whisper flagged any lines.

## Making it original

Design a new character; don't redraw an existing one (Hello Kitty, Pusheen, Pikachu, a brand mascot), even with a new name. Originality comes from a few deliberate choices:

- **One clear silhouette.** Big head, small body, and one shape that sticks out (ears, a tail curl, a hat brim). At 1080 px wide the sprite is scaled about 20–30×, so a 24–40 px grid is plenty. Bigger grids look like blurry photos, not pixel art.
- **One signature accessory** that the story can use (the flower hat that grandma knitted). Give it its own layer so it can sway.
- **A small palette** with a dark outline colour, one main colour, one belly or muzzle colour, a cheek or accent colour, and the accessory colours. Skip pure black. A dark plum or brown outline looks softer.
- **Personality through motion:** a shy character blinks often and bobs slowly, an excited one bobs fast and wags. Two-frame loops are enough.
- **Symmetry by counting:** for a face on a `W`-wide grid, a feature at columns `a..b` mirrors to `W-1-b..W-1-a`. Count each row's length. A row one character short shifts everything after it.

## Motion

The renderer pauses every animation and sets its time each frame, so CSS animations, including `infinite` ones, render the same on every machine. Rules that matter:

- **Inside the sprite's SVG, `1px` in a transform is one sprite pixel** (the viewBox is in grid units). `translateY(-1px)` bobs by exactly one pixel.
- **Use `steps(1)` toggles between keyframes** for sprite-like snapping: bob `50% { transform: translateY(-1px) }`, blink `0% {opacity:0} 94% {opacity:1}` on a closed-eyes overlay, talk `0% {opacity:1} 50% {opacity:0}` on an open-mouth overlay.
- **Swap two poses (tail, wand, wing) with two mirror-image keyframes**, `poseA { 0% {opacity:1} 50% {opacity:0} }` and `poseB { 0% {opacity:0} 50% {opacity:1} }`, on the same duration. Don't reuse one animation with `reverse`. With `steps()`, a reversed animation switches one frame boundary off from the forward one, so any frame that lands exactly on the halfway point shows neither pose. Whether that happens depends on the period: 0.6 s at 30 fps hits it, 0.7 s doesn't. peek.py flags `steps()` with `reverse`.
- **Give an `animation` shorthand only one timing function.** `steps(30) infinite linear` is invalid, so the browser drops the whole declaration and the element never moves. Nothing in the console says so. peek.py catches it.
- **Keep worn things inside the bob group.** If a hat bobs on its own timing it lifts a pixel off the head and leaves a visible gap. Sway the decoration (the flower) inside the group instead.
- **The entry animation goes on a wrapper** (`.stage`) carrying `data-sfx="pop"`: Bloom fires a sound effect when an element's *first* animation starts, so the looping parts must live on children.
- **Time against narration** with `calc(var(--scene-dur) * .5)` when something should happen mid-line. The talking mouth can simply loop: it reads as speech even across pauses.
- **Fit the frame.** The default video is 1080×1920 (vertical). Size the `.stage` so the whole sprite, tail and hat included, stays inside the frame, and mark the sprite `data-character` so peek.py checks it. A close-up scene is the same sprite in a bigger stage, not a new drawing.

## Fonts

Captions and titles use the project's own font files, never a system font. Chromium in the renderer may not see fonts that macOS downloads on demand (Mali, for example). Without the file, the video silently falls back to another face.

1. Find the family folder: `https://api.github.com/repos/google/fonts/contents/ofl/<lowercasename>` lists the files. Static families have `Family-Medium.ttf` / `Family-Bold.ttf`. Some are variable fonts (`Family[wght].ttf`): use one `@font-face` with `font-weight: 100 900`.
2. Download the weights you use and `OFL.txt` into `scripts/<name>/fonts/` from `https://raw.githubusercontent.com/google/fonts/main/ofl/<name>/<file>`. The OFL lets you redistribute them with the project, as long as the licence file comes along.
3. Keep `document.fonts.forEach(f => f.load())` in the page script (the template has it). A face that no visible text uses at load time stays unloaded, Bloom's `fonts.ready` doesn't wait for it, and the first captions come out in a fallback font.

Thai-capable families that suit characters: **Mali** (round, handwritten, cute), **Itim** (casual marker), **Sriracha** (brush handwriting), **Kodchasan** and **Mitr** (friendly rounded), **Kanit** and **Prompt** (clean, bold titles), **Chonburi** (display headline). Google Fonts has no Thai pixel font, so the pixel feel comes from the sprite and the caption box (thick square border, hard offset shadow). Keep the text smooth.

## Voices

`--voice "omnivoice:<instruct>"`. The instruct is a comma-and-space list from OmniVoice's fixed vocabulary. Anything else is rejected.

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

For a voice that sounds like a real person (the user), `uv run bloom voice record <name>` then `--voice omnivoice:@<name>`.

## Keep private work private

Bloom is public and videos get shared, so a video about private work is anonymized by default. Leave out product, repo, org and customer names, file paths, class, table and column names, ticket and alert numbers, and private URLs. Say "a server of ours", "our audit log". Public facts can stay: package and framework names, versions, CVE/GHSA IDs, scores. Put such a project outside this repo (for example `~/…/bloom-videos/<name>/`) and build it with `--out` there. Before building, grep the project, and afterwards the `.srt`, for every private name you met while researching. Only include a name when the user asks for it.

## Checklist before handing over

- peek.py says `ok`, and you've looked at sheet.png
- the font files and `OFL.txt` are in `fonts/`
- script.md's top comment has the exact build command with the voice
- the character is your own design, and you can say in one line what makes it recognisable
