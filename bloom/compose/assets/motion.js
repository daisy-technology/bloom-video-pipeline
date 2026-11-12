// ---- Bloom motion kit: paste into the page after props.js (if any), in a <script> at the end of <body>.
// Everything here is a pure function of (scene, t): no timers, no Math.random, no state between frames,
// so the render is the same whichever frame a worker starts on (check with bloom-motion/scripts/seekcheck.py).
//
//   data-split="word"            Thai-safe word spans (Intl.Segmenter), each with --i for a CSS stagger
//   data-split="char"            grapheme spans (a consonant keeps its vowels and tone marks), short strings only
//   data-stagger                 sets --i on each child (lines of a .rise headline, items of a list)
//   data-cam="t k cx cy, …"      camera: at scene time t, put point (cx, cy) of this element in the middle of
//                                its frame (the section or page it sits in) at zoom k.
//                                t is seconds, "-1.5" (from the end) or "60%". Eased in-out between keys.
//   data-cam-<scene>="…"         the same for one scene: for a world layer outside the sections that
//                                stays across cuts (match the last key of one scene to the first of the next)
//   data-depth="0.3"             a layer inside a camera element: 1 moves with it, 0.3 is far away (parallax)
//   <canvas data-particles="snow|dust|embers|confetti" data-n data-seed data-color data-at>
//                                closed-form particles: confetti bursts at data-at, the others drift all scene
//   data-cam keys may name an element instead of a point: "t k #station" frames that element's centre
//   data-after="scene@t"         world state: sets --p from 0 to 1 over data-len (default .6 s, expo out) from that
//                                moment, and keeps it 1 in every later scene (0 in earlier ones). For a long take,
//                                where one world stays on screen through the cuts and what happened stays happened.
//                                t is seconds, "-1.5" or "60%" of that scene. data-until="scene@t" does the same for --q.
//                                data-ease="linear" (typing, counting) or any BM.ease name; default expo out.
//                                (Not data-from: the props kit uses that for a counter's start value.)
//   SVG <animate>                any SMIL in the shown scene is paused and set to t (it runs on the wall clock otherwise)
//
// window.bloomSeek(scene, t, now) gets now, the video's clock, too: motion that runs on across cuts
// (a clip playing in a world that never cuts, a counter) reads it instead of a table of scene lengths.
// window.BM has the helpers for a page's own bloomSeek code: clamp, prog, ease, spring, hash, rand, secs.
(() => {
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const prog = (t, a, b) => clamp((t - a) / (b - a));
  const ease = {
    out: p => 1 - Math.pow(1 - p, 3), in: p => p * p * p,
    inOut: p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    expo: p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    back: p => 1 + 2.70158 * Math.pow(p - 1, 3) + 1.70158 * Math.pow(p - 1, 2),
  };
  // a damped spring from 0 to 1 at seconds s: closed form, so any frame can be drawn first.
  // bounce 0 settles without overshoot; .3 overshoots about 10 %; .5 is a comic boing
  const spring = (s, bounce = .25, settle = .5) => {
    if (s <= 0) return 0;
    const w = 2 * Math.PI / settle, z = 1 - bounce;
    if (z >= 1) return 1 - (1 + w * s) * Math.exp(-w * s);
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * s) * (Math.cos(wd * s) + (z * w / wd) * Math.sin(wd * s));
  };
  const hash = (a, b = 0) => {  // two integers -> [0, 1), the same every time
    let h = Math.imul(a | 0, 374761393) + Math.imul(b | 0, 668265263) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  };
  const rand = (seed, i, k = 0) => hash(seed * 7919 + i, k);
  const secs = (v, dur, fallback = 0) => {
    if (v == null || v === "") return fallback;
    v = String(v).trim();
    if (v.endsWith("%")) return parseFloat(v) / 100 * dur;
    return v.startsWith("-") ? dur + +v : +v;  // "-0" is the scene's end, not its start
  };
  window.BM = { clamp, prog, ease, spring, hash, rand, secs };

  // ---- text: split once at load, animate with CSS (motion.css .words / .chars) on --i
  document.querySelectorAll("[data-split]").forEach(el => {
    const by = el.dataset.split === "char" ? "grapheme" : "word";
    const seg = new Intl.Segmenter(el.lang || document.documentElement.lang || "th", { granularity: by });
    let i = 0;
    el.setAttribute("aria-label", el.textContent);
    el.innerHTML = [...seg.segment(el.textContent)].map(({ segment, isWordLike }) =>
      /^\s+$/.test(segment) ? segment
        : `<span class="${by === "word" ? "w" : "c"}" style="--i:${(by === "grapheme" || isWordLike) ? i++ : Math.max(0, i - 1)}" aria-hidden="true">${segment.replace(/[&<]/g, c => c === "&" ? "&amp;" : "&lt;")}</span>`
    ).join("");
  });
  document.querySelectorAll("[data-stagger]").forEach(el => [...el.children].forEach((c, k) => c.style.setProperty("--i", k)));

  // ---- camera keys: "t k cx cy", or "t k #id" for the centre of an element inside the camera element
  const centre = (cam, id) => {
    let el = document.getElementById(id), x = 0, y = 0;
    if (!el) throw new Error(`data-cam: no element #${id}`);
    const w = el.offsetWidth, h = el.offsetHeight, pin = el.hasAttribute("data-pin");
    while (el && el !== cam) { x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; }
    return pin ? [x, y - h / 2] : [x + w / 2, y + h / 2];  // a pin (iso.js) hangs above its point by its own size
  };
  const keys = (spec, dur, cam) => spec.split(",").map(s => s.trim().split(/\s+/))
    .map(p => p.length === 3 && p[2].startsWith("#") ? [p[0], p[1], ...centre(cam, p[2].slice(1))] : p)
    .filter(p => p.length >= 4).map(([t, k, x, y]) => [secs(t, dur), +k, +x, +y]).sort((a, b) => a[0] - b[0]);
  const camAt = (ks, t) => {
    if (t <= ks[0][0]) return ks[0].slice(1);
    for (let j = 1; j < ks.length; j++) if (t < ks[j][0]) {
      const [t0, ...a] = ks[j - 1], [t1, ...b] = ks[j], p = ease.inOut(prog(t, t0, t1));
      return a.map((v, n) => v + (b[n] - v) * p);
    }
    return ks[ks.length - 1].slice(1);
  };

  // ---- particles: every particle's position is a formula of its age, never a step from the last frame
  const PARTICLES = {
    snow: (c, W, H, t, i, r) => [(r(0) * W + Math.sin(t * (.6 + r(1)) + r(2) * 6) * 18) , (r(3) * H + t * (40 + r(4) * 60)) % (H + 20) - 10, 2 + r(5) * 4, 1],
    dust: (c, W, H, t, i, r) => [(r(0) * W + t * (r(1) - .5) * 30 + W) % W, (r(2) * H + Math.sin(t * .5 + r(3) * 6) * 24), 1 + r(4) * 2.5, .25 + .35 * (.5 + .5 * Math.sin(t * (1 + r(5)) + r(6) * 6))],
    embers: (c, W, H, t, i, r) => { const life = 2 + r(0) * 2, age = (t + r(1) * life) % life;
      return [r(2) * W + Math.sin(age * 2 + r(3) * 6) * 12, H - age / life * H * (.6 + r(4) * .4), 1.5 + r(5) * 2.5, 1 - age / life]; },
    confetti: (c, W, H, t, i, r) => { if (t < 0) return null;  // a burst from the middle at data-at: gravity, drag, spin
      // linear drag k, gravity g: x = v(1-e^-kt)/k, y adds g(t - (1-e^-kt)/k)/k; mostly upward, then it rains down
      const k = 1.3, g = 1600, a = -Math.PI / 2 + (r(0) - .5) * 2.2, v = 400 + r(1) * 1300;
      const vx = Math.cos(a) * v, vy = Math.sin(a) * v, d = (1 - Math.exp(-k * t)) / k;
      return [W / 2 + vx * d, H * .55 + vy * d + g * (t - d) / k, 0, 1 - prog(t, 2.2, 3.2), t * (r(2) - .5) * 14]; },
  };
  const drawParticles = (cv, t, dur) => {
    const kind = PARTICLES[cv.dataset.particles];
    if (!kind) return;
    const W = cv.width = cv.clientWidth || cv.width, H = cv.height = cv.clientHeight || cv.height;
    const g = cv.getContext("2d"), n = +cv.dataset.n || 60, seed = +cv.dataset.seed || 1;
    const colors = (cv.dataset.color || "#fff").split(/\s+/), local = t - secs(cv.dataset.at, dur, 0);
    g.clearRect(0, 0, W, H);
    for (let i = 0; i < n; i++) {
      const p = kind(cv, W, H, kind === PARTICLES.confetti ? local : t, i, k => rand(seed, i, k));
      if (!p || p[3] <= 0) continue;
      g.globalAlpha = clamp(p[3]);
      g.fillStyle = colors[i % colors.length];
      if (kind === PARTICLES.confetti) {  // flat rectangles that spin and flip read as confetti; dots don't
        g.save(); g.translate(p[0], p[1]); g.rotate(p[4]); g.scale(1, Math.cos(p[4] * 1.7)); g.fillRect(-11, -6, 22, 12); g.restore();
      } else { g.beginPath(); g.arc(p[0], p[1], p[2], 0, Math.PI * 2); g.fill(); }
    }
    g.globalAlpha = 1;
  };

  // ---- world state: where each scene sits in the video, so "scene@t" is before, now or after
  const order = [...document.querySelectorAll("[data-scene]")].map(s => s.dataset.scene);
  const staged = [...document.querySelectorAll("[data-after], [data-until]")];
  const stateAt = (spec, id, t, dur, len, curve = ease.expo) => {
    const [sc, at] = spec.split("@"), i = order.indexOf(sc), j = order.indexOf(id);
    if (i < 0) throw new Error(`data-after/until: no scene ${sc}`);
    if (i !== j) return i < j ? 1 : 0;
    const a = secs(at, dur, 0);
    return curve(prog(t, a, a + len));
  };
  window.BM.state = (spec, id, t, len = .6, curve = ease.expo) => stateAt(spec, id, t, 0, len, curve);  // for compose.js

  const cams = [...document.querySelectorAll("*")].filter(el => [...el.attributes].some(a => a.name.startsWith("data-cam")));
  const before = window.bloomSeek;
  window.bloomSeek = (id, t, now) => {  // now: seconds on the video's clock
    if (before) before(id, t, now);
    const scene = document.querySelector(`[data-scene="${CSS.escape(id)}"]`);
    if (!scene) return;
    const dur = parseFloat(scene.style.getPropertyValue("--scene-dur")) || 6;
    const mine = el => { const s = el.closest("[data-scene]"); return !s || s === scene; };

    cams.forEach(el => {
      if (!mine(el)) return;
      const spec = el.getAttribute(`data-cam-${id}`) || el.dataset.cam;
      if (!spec) return;
      const ks = keys(spec, dur, el);
      if (!ks.length) return;
      // the point lands in the middle of the frame the element sits in (its positioned parent: the
      // section or the page), whatever the element's own size: a world can be far bigger than the frame
      const frame = el.offsetParent || document.body, w = frame.clientWidth, h = frame.clientHeight;
      const [k, cx, cy] = camAt(ks, t), tx = w / 2 - cx * k, ty = h / 2 - cy * k;
      el.style.transformOrigin = "0 0";
      el.style.transform = `translate(${tx}px, ${ty}px) scale(${k})`;
      el.querySelectorAll(":scope [data-depth]").forEach(layer => {  // far layers give back part of the move
        const d = +layer.dataset.depth;
        layer.style.transform = `translate(${-(1 - d) * (tx - (w / 2 - w / 2 * k)) / k}px, ${-(1 - d) * (ty - (h / 2 - h / 2 * k)) / k}px)`;
      });
    });
    staged.forEach(el => {
      const len = +el.dataset.len || .6, curve = ease[el.dataset.ease] || (el.dataset.ease === "linear" ? p => p : ease.expo);
      if (el.dataset.after) el.style.setProperty("--p", stateAt(el.dataset.after, id, t, dur, len, curve).toFixed(4));
      if (el.dataset.until) el.style.setProperty("--q", stateAt(el.dataset.until, id, t, dur, len).toFixed(4));
    });
    scene.querySelectorAll("canvas[data-particles]").forEach(cv => drawParticles(cv, t, dur));
    scene.querySelectorAll("svg").forEach(svg => {
      if (svg.querySelector("animate, animateTransform, animateMotion, set")) { svg.pauseAnimations(); svg.setCurrentTime(t); }
    });
  };
})();
