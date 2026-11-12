# Driving motion under Bloom's seek

Bloom draws each frame by calling `SEEK(scene, t)`. It pauses every animation in `document.getAnimations()`, sets its `currentTime` (scene time for elements inside a section, video time for elements outside every section), writes the caption, then calls `window.bloomSeek(sceneId, t)`. The scenes are split across several worker browsers. Each worker starts at the first frame of some scene, and frames within a scene go forward. So a frame must be **a pure function of (scene, t)**.

Everything here was tested on Bloom's real SHOW/SEEK (Chromium headless, Nov 2026) unless marked otherwise.

## Contents
1. Driver table
2. Pitfalls the renderer won't catch
3. Closed-form recipes (spring, seeded random, particles, bounce, damped follow)
4. Libraries (GSAP, Lottie, three.js, shaders, Flubber)

## 1. Driver table

| Driver | Seeked by Bloom? | How |
|---|---|---|
| CSS `@keyframes` (any property, incl. `offset-distance`, `clip-path`, `stroke-dashoffset`, `filter`) | yes, automatically | delays count from the scene start; use `--at`, `--scene-dur` |
| Registered custom property (`@property --n { syntax: '<integer>' … }`) animated in keyframes | yes (tested: 0 → 856 → 1250) | a CSS-only counter: `counter-reset: n var(--n)` + `::after { content: counter(n) }`. It has no thousands separators; for formatted numbers use the props kit's `count` |
| Web Animations API (`el.animate(...)`) created at load | yes | create it once at load, never inside `bloomSeek` (an animation made during a frame misses that frame's seek) |
| CSS transitions | no | they start on a style change at wall-clock time. Use keyframes |
| SVG SMIL (`<animate>`, `<animateMotion>`, `<set>`) | no: it runs on the wall clock (tested: the same t gave 18, 21, 26, 29 px) | `motion.js` pauses it and calls `svg.setCurrentTime(t)` for every SVG in the shown scene. Without the kit, call `svg.pauseAnimations(); svg.setCurrentTime(t)` in `bloomSeek` |
| Canvas 2D | via `bloomSeek` | clear and redraw the whole canvas from t on every call |
| WebGL / three.js | via `bloomSeek` (tested: the canvas shows in the screenshot, with or without `preserveDrawingBuffer`) | `renderer.render()` inside `bloomSeek`; pass `preserveDrawingBuffer: true` anyway, since it costs nothing here |
| GSAP | via `bloomSeek` (tested: `tl.seek(1)` gave 263 px of 300 with `power2.out`) | `const tl = gsap.timeline({ paused: true })`, then `tl.seek(t)` in `bloomSeek`. Use one timeline per scene |
| Lottie (lottie-web) | via `bloomSeek` (not tested here) | `autoplay: false`, renderer `svg`; `anim.goToAndStop(t * 1000, false)` |
| `<video>` | no, and seeking is async | render the clip to an image sequence and show frame `floor(t * fps)`, or accept that `currentTime` may show a stale frame |
| `<html data-mouth>` / `--voice` (lip sync) | set by Bloom each frame | drive plain properties from them, not animations they start |

Run `scripts/seekcheck.py` after adding any driver. It draws every frame in order and out of order and fails on any difference.

## 2. Pitfalls the renderer won't catch

- `Math.random()`, `Date.now()`, `performance.now()` and `new Date()` in anything drawn give a new value every frame and on every worker. Use `BM.rand(seed, i, k)` (a hash of integers).
- State between calls: `x += v`, a particle array updated in place, a "last frame" variable, `mixer.update(dt)`, a damped `lerp(current, goal, .1)`. The first frame a worker draws has no history. Compute from t.
- `requestAnimationFrame`, `setTimeout` and `setInterval` keep running on the wall clock between screenshots. Build the DOM once at load, and draw only in `bloomSeek`.
- Class toggles from `bloomSeek` that start a CSS animation or transition: the new animation starts at wall-clock time. Toggle plain properties instead (opacity, a visible class with no animation), or keep every animation in the stylesheet from the start.
- Text measured before the font loads: split and measure after `document.fonts.ready`. Bloom waits for it before the first frame, but your load-time script may not. `data-split` only splits and doesn't measure, so it's safe.
- Persistent elements: anything outside every `<section>` runs its CSS on the video's clock, so a ticker never restarts at a cut. For `bloomSeek`-driven motion that should run on across cuts (a clip, typing, a counter), use the third argument, `now` (the video's clock). Or key it per scene (`data-cam-<scene>`) and make the last key of one scene equal the first key of the next.

## 3. Closed-form recipes

All of these are in `bloom/compose/assets/motion.js` as `window.BM`.

```js
// a damped spring 0 -> 1, s seconds after it starts. bounce 0 = no overshoot, .25 ≈ 8 %, .5 = comic
BM.spring(s, bounce = .25, settle = .5)
// usage: el.style.scale = .6 + .4 * BM.spring(t - 1.2)

BM.rand(seed, i, k)          // [0,1) for particle i, attribute k: no sequence, so order never matters
BM.prog(t, a, b)             // 0..1 between times a and b, clamped
BM.ease.out / in / inOut / expo / back
```

Particles as formulas of age (this is what `data-particles` does):

- Burst with drag k and gravity g, launched at speed (vx, vy): `d = (1 - e^(-k·age)) / k`, `x = x0 + vx·d`, `y = y0 + vy·d + g·(age - d) / k`. Spin with `rot = age · w`, and fade with `1 - prog(age, life-1, life)`. Confetti reads as confetti because of flat rectangles that spin and flip (`scaleY = cos(rot)`) under gravity and drag. Round dots don't.
- Continuous emitter: particle i is born at `i / rate`, and its age is `t - birth` (skip it while negative). Looping: `age = (t + offset_i) mod life`.
- Snow: `y = (y0 + speed·t) mod (H + margin)`, `x = x0 + A·sin(ω·t + φ)`.
- Wall bounce without a simulation: `x = W - |((x0 + v·t) mod 2W) - W|` (a triangle wave).
- Damped follow (a camera catching up after a jump to `goal` at time t0): `x = goal + (x0 - goal)·(1 + λτ)·e^(-λτ)` with `τ = t - t0`, λ 3..8.
- A simulation you can't write in closed form: re-run it from the scene start up to t with a fixed step (`for (s = 0; s < t; s += 1/60) step(1/60)`) from a fixed seed. That costs O(t) per frame, which is fine for a few hundred particles over a 15 s scene.

Loops that must meet themselves: use `phase = (t % P) / P · 2π` and only `sin`/`cos` of whole multiples of it. CSS loops need identical 0 % and 100 % keyframes.

Stutter on purpose (a hand-made, 12 fps look on one layer): use `tq = Math.floor(t * 12) / 12` for that layer only, or `steps()` in CSS. Keep the camera smooth; stuttering everything looks like dropped frames.

Hand-drawn boil: change the wobble seed every 4 frames, `seed = Math.floor(t * 30 / 4)`. Changing it every frame reads as noise. `.boil` in motion.css does this.

## 4. Libraries

Vendor the file into the project (`scripts/<project>/lib/gsap.min.js`) instead of linking a CDN. The render may run on a remote machine without network, and a pinned file renders the same next year.

GSAP:
```js
const tl = { hook: gsap.timeline({ paused: true }), sun: gsap.timeline({ paused: true }) };
tl.hook.from(".title .w", { yPercent: 110, duration: .6, ease: "expo.out", stagger: .05 }, .3);
const before = window.bloomSeek;
window.bloomSeek = (id, t) => { if (before) before(id, t); tl[id]?.seek(t, false); };
```
`seek(t, false)` doesn't fire callbacks, so never rely on `onComplete` to change the page. ScrollTrigger, Lenis and `quickTo` are interactive and don't apply. Plugins (MorphSVG, MotionPath, SplitText) work the same way inside a paused timeline. For Thai, split with `data-split` rather than SplitText's character mode.

Lottie: call `lottie.loadAnimation({ container, renderer: "svg", autoplay: false, loop: false, path })`; it is ready on `DOMLoaded`. In `bloomSeek`, call `anim.goToAndStop(Math.min(t, anim.getDuration()) * 1000, false)`. Load the JSON inline (`animationData`) so file:// loading can't fail.

three.js: don't use `setAnimationLoop` or `Clock`. In `bloomSeek`, set uniforms and object transforms from t, call `mixer.setTime(t)` for GLTF clips (absolute, never `update(dt)`), move the camera along `curve.getPointAt(BM.ease.inOut(p))`, then call `renderer.render(scene, camera)`. A black canvas means an init error or NaN positions; check the console.

Fragment shaders: everything is a function of `u_time` and `u_progress`, so set them from t and draw. Transitions run on progress: a noise dissolve is `smoothstep(p - .05, p, noise(uv * 20.))`, and a displacement is `uv ± disp * p * .3`. Loops need an integer number of noise cells scrolled per period.

Shape morph: Flubber's `interpolate(a, b, { maxSegmentLength: 2 })` returns `f(p)`, a pure function, so call `path.setAttribute("d", f(BM.ease.inOut(BM.prog(t, 2, 2.8))))` in `bloomSeek`. Two paths with the same command list can morph with plain CSS `d: path(...)` keyframes.
