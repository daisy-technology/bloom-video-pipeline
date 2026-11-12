// ---- Bloom scenario props: builds each prop's inside from its data attributes, and drives the
// counting ones (a calendar, a number) through window.bloomSeek, which Bloom calls before every frame.
// No timers, no randomness: the same frame always draws the same thing.
(() => {
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const hash = (s, k) => { let h = 2166136261; for (const c of s + k) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };

  function qrCells(seed) {  // a QR-looking 21 x 21 grid: three finder squares, the rest from a fixed hash
    const finder = (x, y) => [[0, 0], [14, 0], [0, 14]].some(([fx, fy]) => {
      const dx = x - fx, dy = y - fy;
      if (dx < 0 || dy < 0 || dx > 6 || dy > 6) return false;
      return dx === 0 || dy === 0 || dx === 6 || dy === 6 || (dx > 1 && dx < 5 && dy > 1 && dy < 5);
    });
    const inFinder = (x, y) => [[0, 0], [14, 0], [0, 14]].some(([fx, fy]) => x >= fx - 1 && x <= fx + 7 && y >= fy - 1 && y <= fy + 7);
    let out = "";
    for (let y = 0; y < 21; y++) for (let x = 0; x < 21; x++) {
      const on = inFinder(x, y) ? finder(x, y) : hash(seed, x * 31 + y) % 100 < 47;
      out += on ? "<i></i>" : '<i class="o"></i>';
    }
    return out;
  }

  const build = {
    qr: el => `<div class="body"><div class="screen">
        <div class="head">${el.dataset.icon ? `<img src="${esc(el.dataset.icon)}">` : ""}${esc(el.dataset.head || "สแกนจ่าย")}</div>
        <div class="code">${qrCells(el.dataset.head || "qr")}</div><div class="scan"></div>
        <div class="amt">${esc(el.dataset.amount || "฿ 50.00")}</div><div class="spin"></div>
        <div class="res" data-sfx="${"ok" in el.dataset ? "chime" : "buzz"}"><b>${"ok" in el.dataset ? "✓" : "✕"}</b>
          <span>${esc(el.dataset.result || ("ok" in el.dataset ? "สำเร็จ" : "ทำรายการไม่สำเร็จ"))}</span>
          <small>${esc(el.dataset.sub || "")}</small></div></div></div>`,
    pos: el => `<div class="card"></div><div class="body"><div class="screen">
        <span class="wait">${esc(el.dataset.wait || "กำลังเชื่อมต่อ…")}</span>
        <div class="no" data-sfx="buzz"><b>${esc(el.dataset.result || "DECLINED")}</b><span>${esc(el.dataset.sub || "ปฏิเสธรายการ")}</span></div></div>
        <div class="keys">${"<i></i>".repeat(9)}</div></div>`,
    chat: el => `<div class="msg m1">${esc(el.dataset.first || "ถึงบ้านยัง?")}<i>✓✓</i></div>
        <div class="msg m2 fail">${esc(el.dataset.second || "โทรกลับด่วน")}<i class="clock">กำลังส่ง…</i><span class="bang" data-sfx="buzz" data-audit="spill">!</span></div>
        <div class="note">${esc(el.dataset.result || "ส่งไม่สำเร็จ")}</div>`,
    sea: el => `<div class="wave"></div><div class="floor"></div><div class="wire"></div>
        ${el.dataset.icon ? `<img class="volc" src="${esc(el.dataset.icon)}">` : ""}
        <div class="cut" data-sfx="hit"></div>${"ship" in el.dataset ? `<div class="ship" data-sfx="whoosh"></div>` : ""}
        <div class="sea-tag">${esc(el.dataset.tag || "")}</div>`,
    sun: el => `<div class="star"></div><div class="blast" data-sfx="${"miss" in el.dataset ? "riser whoosh@end" : "riser hit@end"}"></div><div class="earth"></div>
        ${el.dataset.icon ? `<img class="hiticon" src="${esc(el.dataset.icon)}">` : ""}
        <div class="lbl">${esc(el.dataset.label || "")}</div>`,
    cal: el => `<div class="pad"><div class="top">${esc(el.dataset.head || "วันที่")}</div><div class="num">${esc(el.dataset.from || 1)}</div></div>`,
    count: el => `<span class="v">${esc(el.dataset.pre || "")}${esc(el.dataset.from || 0)}${esc(el.dataset.suf || "")}</span><small>${esc(el.dataset.label || "")}</small>`,
    offline: el => `${el.dataset.icon ? `<img class="globe" src="${esc(el.dataset.icon)}">` : ""}<div class="land"></div><div class="wifi"><i></i><i></i><i></i></div><div class="x" data-sfx="buzz">✕</div>
        <div class="lbl">${esc(el.dataset.label || "")}</div>`,
    odds: el => {
      const max = +el.dataset.max || 20, lo = +el.dataset.lo || 0, hi = +el.dataset.hi || max;
      return `<div class="track"><div class="band" style="left:${lo / max * 100}%; width:${(hi - lo) / max * 100}%" data-sfx="hit"></div></div>
        <div class="tick" style="left:${lo / max * 100}%">${esc(el.dataset.lotext || lo + "%")}</div>
        <div class="tick" style="left:${hi / max * 100}%">${esc(el.dataset.hitext || hi + "%")}</div>
        <div class="lbl">${esc(el.dataset.label || "")}</div>`;
    },
  };

  document.querySelectorAll(".prop").forEach(el => {
    const kind = Object.keys(build).find(k => el.classList.contains(k));
    if (kind) el.innerHTML = build[kind](el);
  });

  // counting props: value at scene time t, eased out, formatted with thousands separators
  const ease = p => 1 - Math.pow(1 - p, 3);
  // a time is seconds from the scene start, "-1.5" for 1.5 s before its end, or "60%" of the scene
  const secs = (v, dur, fallback) => {
    if (v == null || v === "") return fallback;
    if (v.endsWith("%")) return parseFloat(v) / 100 * dur;
    return v.startsWith("-") ? dur + +v : +v;  // "-0" is the scene's end, not its start
  };
  const at = (el, t, dur) => {
    const t0 = secs(el.dataset.t0, dur, 0), t1 = secs(el.dataset.at, dur, t0 + 1);
    const from = +el.dataset.from || 0, to = +el.dataset.to || 0;
    return from + (to - from) * ease(Math.min(1, Math.max(0, (t - t0) / (t1 - t0))));
  };
  const fmt = (v, dec) => v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const before = window.bloomSeek;
  window.bloomSeek = (id, t, now) => {  // now: seconds on the video's clock
    if (before) before(id, t, now);
    const scene = document.querySelector(`[data-scene="${CSS.escape(id)}"]`);
    if (!scene) return;
    const dur = parseFloat(scene.style.getPropertyValue("--scene-dur")) || 6;
    scene.querySelectorAll(".prop.cal").forEach(el => { el.querySelector(".num").textContent = Math.round(at(el, t, dur)); });
    scene.querySelectorAll(".prop.count").forEach(el => {
      el.querySelector(".v").textContent = (el.dataset.pre || "") + fmt(at(el, t, dur), +el.dataset.dec || 0) + (el.dataset.suf || "");
    });
  };
})();
