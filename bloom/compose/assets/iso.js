// ---- Bloom iso kit: a clean isometric world from a few attributes. Paste BEFORE motion.js (the camera
// measures what this builds). It runs once at load and draws nothing per frame, so it is seek-safe.
//
//   <div class="iso" data-unit="48" data-origin="1600 500">   the world layer; one unit = data-unit px,
//                                                              the grid's (0,0,0) sits at data-origin
//     <div data-box="x y z w d h" style="--c:#5b8def"></div>   a block: top lightest, left the colour,
//                                                              right darkest (one light, always)
//     <div data-tile="x y w d" style="--c:#e9eef5"></div>      a flat floor plate (z = 0), a road, a pad
//     <div data-face="right x y z" style="width:220px;height:140px">…HTML…</div>
//                                                              HTML laid on a plane: left (facing +y),
//                                                              right (facing +x) or top. A screen on a block,
//                                                              a sign, a card lying on the floor.
//     <div data-pin="x y z" class="tag">ข้อความ</div>         a flat label pinned above a world point: it
//                                                              travels with the camera and stays readable.
//                                                              Text people read goes here, not on a face.
//   </div>
//
// 2:1 dimetric (the pixel/arcade iso): +x runs down-right, +y down-left, +z straight up. No perspective:
// height is lift, never scale. Elements are layered back to front by x + y + z automatically.
// Each placed element keeps its own id and classes, so the motion kit works on it (data-after + .build
// raises a block from its base; data-cam="t k #id" frames it).
(() => {
  document.querySelectorAll(".iso").forEach(world => {
    const u = +world.dataset.unit || 48;
    const [ox, oy] = (world.dataset.origin || "0 0").split(/\s+/).map(Number);
    const P = (x, y, z) => [ox + (x - y) * u, oy + (x + y) * u / 2 - z * u];
    const place = (el, pts, depth) => {  // size the element to its points' bounding box, return local coordinates
      const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
      const l = Math.min(...xs), t = Math.min(...ys);
      Object.assign(el.style, { position: "absolute", left: l + "px", top: t + "px",
        width: Math.max(...xs) - l + "px", height: Math.max(...ys) - t + "px", zIndex: Math.round(depth * 10) + 1000 });
      return pts.map(([x, y]) => `${(x - l).toFixed(1)},${(y - t).toFixed(1)}`);
    };
    const svg = (el, faces) => {
      const w = parseFloat(el.style.width), h = parseFloat(el.style.height);
      el.innerHTML = `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block;overflow:visible">` +
        faces.map(([pts, fill]) => `<polygon points="${pts.join(" ")}" style="fill:${fill};stroke:${fill};stroke-width:.6;stroke-linejoin:round"/>`).join("") +
        "</svg>" + el.innerHTML;
    };
    const TOP = "color-mix(in oklch, var(--c) 72%, white)", LEFT = "var(--c)", RIGHT = "color-mix(in oklch, var(--c) 70%, black)";

    world.querySelectorAll("[data-box]").forEach(el => {
      const [x, y, z, w, d, h] = el.dataset.box.split(/\s+/).map(Number);
      const c = [P(x, y, z + h), P(x + w, y, z + h), P(x + w, y + d, z + h), P(x, y + d, z + h),
                 P(x, y + d, z), P(x + w, y + d, z), P(x + w, y, z)];
      const loc = place(el, c, x + y + z + (w + d) / 2);
      const top = [0, 1, 2, 3].map(i => loc[i]);
      const left = [loc[3], loc[2], loc[5], loc[4]];   // the +y face, towards the viewer's left
      const right = [loc[2], loc[1], loc[6], loc[5]];  // the +x face, towards the viewer's right
      svg(el, [[left, LEFT], [right, RIGHT], [top, TOP]]);
    });
    world.querySelectorAll("[data-tile]").forEach(el => {
      const [x, y, w, d] = el.dataset.tile.split(/\s+/).map(Number);
      const loc = place(el, [P(x, y, 0), P(x + w, y, 0), P(x + w, y + d, 0), P(x, y + d, 0)], x + y - 1);
      svg(el, [[loc, "var(--c)"]]);
    });
    world.querySelectorAll("[data-pin]").forEach(el => {  // bottom-centre on the point, drawn over the blocks
      const [x, y, z] = el.dataset.pin.split(/\s+/).map(Number), [px, py] = P(x, y, z);
      Object.assign(el.style, { position: "absolute", left: px + "px", top: py + "px", translate: "-50% -100%",
        zIndex: 100000 });
    });
    const M = { top: "matrix(1, .5, -1, .5, 0, 0)", left: "matrix(1, .5, 0, 1, 0, 0)", right: "matrix(1, -.5, 0, 1, 0, 0)" };
    world.querySelectorAll("[data-face]").forEach(el => {
      const [face, x, y, z] = el.dataset.face.split(/\s+/);
      if (!M[face]) throw new Error(`data-face: ${face}? expected left, right or top`);
      const [px, py] = P(+x, +y, +z);
      Object.assign(el.style, { position: "absolute", left: px + "px", top: py + "px", transformOrigin: "0 0",
        transform: M[face], zIndex: Math.round((+x + +y + +z + 1) * 10) + 1000 });
    });
  });
})();
