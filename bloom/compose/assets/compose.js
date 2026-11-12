// ---- Bloom compose runtime: the drivers a generated page needs beyond motion.js (typing, counting,
// clips, lines). Generated pages only; every value comes from (scene, t, now), never a timer.
(() => {
  const { ease, state } = window.BM;
  const seg = new Intl.Segmenter("th", { granularity: "grapheme" });
  const esc = s => s.replace(/[&<]/g, c => (c === "&" ? "&amp;" : "&lt;"));
  const all = sel => [...document.querySelectorAll(sel)];

  // lines in the world: x y z projected with the iso world's unit and origin, once, at load
  all("svg[data-line]").forEach(svg => {
    const world = svg.closest(".iso"), u = +world.dataset.unit || 48;
    const [ox, oy] = (world.dataset.origin || "0 0").split(/\s+/).map(Number);
    const P = (x, y, z) => [ox + (x - y) * u, oy + (x + y) * u / 2 - z * u];
    const [a, b] = svg.dataset.line.split(";").map(s => P(...s.trim().split(/\s+/).map(Number)));
    const pad = 12, l = Math.min(a[0], b[0]) - pad, t = Math.min(a[1], b[1]) - pad;
    Object.assign(svg.style, { position: "absolute", left: l + "px", top: t + "px", overflow: "visible", zIndex: 999 });
    svg.setAttribute("width", Math.abs(a[0] - b[0]) + 2 * pad);
    svg.setAttribute("height", Math.abs(a[1] - b[1]) + 2 * pad);
    svg.innerHTML = `<path pathLength="1" d="M${a[0] - l} ${a[1] - t} L${b[0] - l} ${b[1] - t}"/>`;
  });

  const typed = all("[data-type]").map(el => {
    const ls = [...el.querySelectorAll("[data-type-line]")];
    const text = ls.map(x => [...seg.segment(x.textContent)].map(s => s.segment));
    return { el, ls, text, total: text.reduce((n, g) => n + g.length, 0) };
  });
  const counts = all("[data-count-at]").map(el => ({ el, b: el.querySelector("[data-count]") }));
  const clips = all("[data-play-at]").map(el => ({ el, s: el.querySelector("[data-sheet]") }));
  const lines = all("svg[data-draw]");

  const before = window.bloomSeek;
  window.bloomSeek = (id, t, now) => {
    if (before) before(id, t, now);
    typed.forEach(({ el, ls, text, total }) => {  // the rest stays in place, invisible, so nothing reflows
      let n = Math.round(state(el.dataset.type, id, t, +el.dataset.typeLen || 1, p => p) * total);
      ls.forEach((x, k) => {
        const g = text[k], take = Math.min(n, g.length);
        x.innerHTML = esc(g.slice(0, take).join("")) + `<span class="ghost">${esc(g.slice(take).join(""))}</span>`;
        n -= take;
      });
    });
    counts.forEach(({ el, b }) => {
      const p = ease.out(state(el.dataset.countAt, id, t, +el.dataset.countLen || 1, q => q));
      const from = +b.dataset.from, to = +b.dataset.to, dec = +b.dataset.dec || 0;
      b.textContent = (b.dataset.pre || "") + (from + (to - from) * p).toLocaleString("en-US",
        { minimumFractionDigits: dec, maximumFractionDigits: dec }) + (b.dataset.suf || "");
    });
    clips.forEach(({ el, s }) => {  // 8 x 5 frames at 10 fps, on the video's clock: it plays on through cuts
      const at = +el.dataset.playAt, f = now == null || now < at ? 0 : Math.floor((now - at) * 10) % 40;
      const w = s.offsetWidth, h = s.offsetHeight;
      s.style.backgroundPosition = `${-(f % 8) * w}px ${-Math.floor(f / 8) * h}px`;
    });
    lines.forEach(svg => {
      const p = state(svg.dataset.draw, id, t, +svg.dataset.drawLen || .8, ease.inOut);
      const path = svg.querySelector("path");
      if (path) path.style.strokeDashoffset = (1 - p).toFixed(4);
    });
  };
})();
