/*
 * props.js : the shared doodle props and primitives for photo-doodle films, drawn once here so
 * every shot draws them identically. Loaded after lib.js and before the scenes.
 *
 * Everything is a pure function of its arguments (no state between frames) and every stroke goes
 * through FILM.lib.inkPath, so the boil and the draw-on behave like the rest of the film.
 *
 *   props:       bubble, sparkle, speedLines, starburst, cloud, sun, moon, heart, note, flag,
 *                trail, zzz, dust, drop (see each function's comment)
 *   primitives:  step (stroke i of n from a figure's draw fraction), place (translate/scale/flip),
 *                ink, wash, eye, blush, blob — what src/cast.js builds its characters from
 *
 * The film's own characters live in src/cast.js and call these. Keep them out of scene files: a
 * character redrawn per scene drifts, and sixteen agents will each drift differently.
 *
 * Draw-on: every function takes draw 0..1 and reveals its strokes in order, each stroke taking
 * 1/n of the range with a small overlap, so a figure assembles the way a hand would draw it.
 * Night shots pass night: true, which swaps ink for chalk and drops the pigment.
 */
(function () {
  'use strict';

  const FILM = window.FILM;
  const L = FILM.lib;
  const P = L.pal;
  const TAU = Math.PI * 2;
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);

  /** progress of stroke i of n, given the whole-figure draw fraction */
  const step = (d, i, n) => clamp((d * n - i) * 1.35);

  /** rotate + scale helper: maps local coords (x right, y down, origin at the figure's base) */
  function place(ctx, o, fn) {
    ctx.save();
    ctx.translate(o.x, o.y);
    if (o.tilt) ctx.rotate(o.tilt);
    const s = o.s != null ? o.s : 1;
    ctx.scale(o.flip ? -s : s, s);
    fn();
    ctx.restore();
  }

  const inkOf = (o) => (o.night ? P.chalk : P.doodleInk);

  function ink(ctx, pts, o, extra) {
    // o.alpha applies to the whole figure; extra.alpha (per stroke) multiplies it.
    const base = { color: inkOf(o), width: 3.4, wobble: 1.6, tremble: 0.4 };
    const q = Object.assign(base, extra);
    if (o.alpha != null) q.alpha = (q.alpha != null ? q.alpha : 1) * o.alpha;
    L.inkPath(ctx, pts, q);
  }

  function wash(ctx, pts, o, color, extra) {
    if (o.night) return; // night shots are chalk line only, no pigment
    L.wash(ctx, pts, Object.assign({ color, alpha: 0.5, seed: (extra && extra.seed) || 7 }, extra));
  }

  /** a closed blob path: centre, radius, per-angle radius function */
  function blob(cx, cy, n, rf) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / n) * TAU;
      const r = rf(a, i);
      pts.push([cx + Math.cos(a) * r[0], cy + Math.sin(a) * r[1]]);
    }
    return pts;
  }

  const eye = (ctx, x, y, r, o, blink) => {
    if (blink > 0.5) ink(ctx, [[x - r * 1.3, y], [x + r * 1.3, y]], o, { width: 2.6, smooth: false, taper: 3 });
    else {
      ctx.save();
      ctx.fillStyle = inkOf(o);
      ctx.beginPath();
      ctx.ellipse(x, y, r, r * 1.08, 0, 0, TAU);
      ctx.fill();
      ctx.restore();
    }
  };

  const blush = (ctx, x, y, r, o) => {
    if (o.night) return;
    ctx.save();
    ctx.globalAlpha *= 0.55;
    ctx.fillStyle = P.blush;
    ctx.beginPath();
    ctx.ellipse(x, y, r, r * 0.68, 0, 0, TAU);
    ctx.fill();
    ctx.restore();
  };

  // ---------------------------------------------------------------------------
  // Props
  // ---------------------------------------------------------------------------

  /** bubble(ctx, o) : speech bubble with a tail. x, y is the bubble centre; tail points at tx, ty. */
  function bubble(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const w = o.w || 200, h = o.h || 110;
    const pts = blob(o.x, o.y, 34, (a) => [w / 2 + Math.cos(a * 3) * 5, h / 2 + Math.sin(a * 2) * 4]);
    if (!o.night) {
      L.wash(ctx, pts, { color: o.fill || P.washCream, alpha: o.fillAlpha != null ? o.fillAlpha : 0.75, p: d, seed: (o.seed || 5) + 1, offset: [2, 2], edge: 0 });
    }
    ink(ctx, pts, o, { closed: true, draw: d, width: 3, seed: o.seed || 5 });
    if (o.tx != null) {
      const dx = o.tx - o.x, dy = o.ty - o.y;
      const l = Math.hypot(dx, dy) || 1;
      const bx = o.x + (dx / l) * (w / 2) * 0.8, by = o.y + (dy / l) * (h / 2) * 0.9;
      ink(ctx, [[bx - 14, by - 2], [o.tx, o.ty], [bx + 12, by + 8]], o, { draw: d, width: 2.8, seed: (o.seed || 5) + 2 });
    }
    if (o.label && d > 0.85) {
      L.hand(ctx, o.label, o.x, o.y + (o.size || 42) * 0.34, {
        size: o.size || 42,
        align: 'center',
        color: inkOf(o),
        p: clamp((d - 0.85) / 0.15),
      });
    }
  }

  /** sparkle(ctx, x, y, r, o) : a four-point twinkle. */
  function sparkle(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    if (d <= 0) return;
    const k = r * d;
    ink(ctx, [[x - k, y], [x + k, y]], o, { width: o.width || 2.4, seed: (o.seed || 3) });
    ink(ctx, [[x, y - k], [x, y + k]], o, { width: o.width || 2.4, seed: (o.seed || 3) + 1 });
    ink(ctx, [[x - k * 0.45, y - k * 0.45], [x + k * 0.45, y + k * 0.45]], o, { width: (o.width || 2.4) * 0.7, seed: (o.seed || 3) + 2 });
    ink(ctx, [[x + k * 0.45, y - k * 0.45], [x - k * 0.45, y + k * 0.45]], o, { width: (o.width || 2.4) * 0.7, seed: (o.seed || 3) + 3 });
  }

  /** speedLines(ctx, o) : n trailing lines behind something moving. x, y is the trailing edge. */
  function speedLines(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const n = o.n || 3, len = o.len || 90, gap = o.gap || 22, dir = o.dir != null ? o.dir : -1;
    for (let i = 0; i < n; i++) {
      const y = o.y + (i - (n - 1) / 2) * gap;
      const l = len * (i === Math.floor(n / 2) ? 1 : 0.7);
      ink(ctx, [[o.x, y], [o.x + dir * l, y + (i - (n - 1) / 2) * 4]], o, {
        draw: clamp(d * 1.4 - i * 0.12),
        width: o.width || 3,
        seed: (o.seed || 40) + i,
        smooth: false,
      });
    }
  }

  /** starburst(ctx, x, y, r, o) : the impact star behind a loud moment. */
  function starburst(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    if (d <= 0) return;
    const n = o.n || 10;
    const pts = [];
    for (let i = 0; i < n * 2; i++) {
      const a = (i / (n * 2)) * TAU - Math.PI / 2;
      const rr = (i % 2 ? r * 0.52 : r) * (0.9 + 0.2 * Math.sin(i * 2.7 + (o.seed || 1)));
      pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]);
    }
    if (!o.night && o.fill !== false) L.wash(ctx, pts, { color: o.fill || P.washYellow, alpha: 0.45, p: d, seed: (o.seed || 9) + 4, offset: [3, 2] });
    ink(ctx, pts, o, { closed: true, draw: d, width: o.width || 3.4, seed: o.seed || 9 });
  }

  /** cloud(ctx, x, y, w, o) : a bumpy cloud. o.face: 'angry' | 'happy' draws a face on it. */
  function cloud(ctx, x, y, w, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const h = o.h || w * 0.46;
    const pts = [];
    const bumps = o.bumps || 5;
    for (let i = 0; i <= 44; i++) {
      const u = i / 44, a = u * TAU;
      const r = 1 + 0.16 * Math.cos(a * bumps + (o.seed || 2));
      pts.push([x + Math.cos(a) * (w / 2) * r, y + Math.sin(a) * (h / 2) * (a > Math.PI ? r : r * 0.82)]);
    }
    if (!o.night) L.wash(ctx, pts, { color: o.fill || P.washBlue, alpha: o.fillAlpha != null ? o.fillAlpha : 0.35, p: d, seed: (o.seed || 2) + 1 });
    ink(ctx, pts, o, { closed: true, draw: d, width: o.width || 3.2, seed: o.seed || 2 });
    if (o.face && d > 0.9) {
      const ey = y - h * 0.05;
      eye(ctx, x - w * 0.12, ey, 4.6, o, o.blink || 0);
      eye(ctx, x + w * 0.12, ey, 4.6, o, o.blink || 0);
      const m = o.face === 'angry'
        ? [[x - w * 0.1, y + h * 0.2], [x, y + h * 0.12], [x + w * 0.1, y + h * 0.2]]
        : [[x - w * 0.1, y + h * 0.12], [x, y + h * 0.24], [x + w * 0.1, y + h * 0.12]];
      ink(ctx, m, o, { width: 2.4, seed: (o.seed || 2) + 6 });
      if (o.face === 'angry') {
        ink(ctx, [[x - w * 0.2, ey - 16], [x - w * 0.06, ey - 8]], o, { width: 2.4, seed: (o.seed || 2) + 7 });
        ink(ctx, [[x + w * 0.2, ey - 16], [x + w * 0.06, ey - 8]], o, { width: 2.4, seed: (o.seed || 2) + 8 });
      }
    }
  }

  /** sun(ctx, x, y, r, o) / moon(ctx, x, y, r, o) : with rays / with a sleepy face. */
  function sun(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const disc = blob(x, y, 30, () => [r, r]);
    if (!o.night) L.wash(ctx, disc, { color: o.fill || P.washYellow, alpha: 0.5, p: d, seed: (o.seed || 11) + 1 });
    ink(ctx, disc, o, { closed: true, draw: d, width: 3.2, seed: o.seed || 11 });
    const n = o.rays == null ? 8 : o.rays;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * TAU + (o.rot || 0);
      ink(ctx, [[x + Math.cos(a) * r * 1.25, y + Math.sin(a) * r * 1.25], [x + Math.cos(a) * r * 1.6, y + Math.sin(a) * r * 1.6]], o, {
        draw: clamp(d * 1.3 - i * 0.05),
        width: 2.6,
        seed: (o.seed || 11) + 3 + i,
        smooth: false,
      });
    }
    if (o.face && d > 0.9) {
      eye(ctx, x - r * 0.3, y - r * 0.1, 4.4, o, o.blink || (o.face === 'sleep' ? 1 : 0));
      eye(ctx, x + r * 0.3, y - r * 0.1, 4.4, o, o.blink || (o.face === 'sleep' ? 1 : 0));
      ink(ctx, [[x - r * 0.18, y + r * 0.26], [x, y + r * 0.38], [x + r * 0.18, y + r * 0.26]], o, { width: 2.4, seed: (o.seed || 11) + 20 });
    }
  }

  function moon(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const pts = [];
    for (let i = 0; i <= 40; i++) {
      const a = -Math.PI * 0.62 + (i / 40) * Math.PI * 1.24;
      pts.push([x + Math.cos(a) * r, y + Math.sin(a) * r]);
    }
    for (let i = 40; i >= 0; i--) {
      const a = -Math.PI * 0.62 + (i / 40) * Math.PI * 1.24;
      pts.push([x + Math.cos(a) * r * 0.42 + r * 0.42, y + Math.sin(a) * r * 0.92]);
    }
    if (!o.night) L.wash(ctx, pts, { color: o.fill || P.washCream, alpha: 0.5, p: d, seed: (o.seed || 13) + 1 });
    ink(ctx, pts, o, { closed: true, draw: d, width: 3.2, seed: o.seed || 13 });
    if (o.face && d > 0.9) {
      eye(ctx, x - r * 0.28, y - r * 0.08, 4.2, o, 1);
      ink(ctx, [[x - r * 0.34, y + r * 0.3], [x - r * 0.18, y + r * 0.4], [x - r * 0.02, y + r * 0.3]], o, { width: 2.2, seed: (o.seed || 13) + 6 });
    }
  }

  /** heart(ctx, x, y, r, o) and note(ctx, x, y, s, o) : the two little feeling glyphs. */
  function heart(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const pts = [];
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * TAU;
      const sx = 16 * Math.pow(Math.sin(a), 3);
      const sy = 13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a);
      pts.push([x + (sx / 16) * r, y - (sy / 16) * r]);
    }
    if (!o.night) L.wash(ctx, pts, { color: o.fill || P.washPink, alpha: 0.55, p: d, seed: (o.seed || 17) + 1 });
    ink(ctx, pts, o, { closed: true, draw: d, width: o.width || 2.8, seed: o.seed || 17 });
  }

  function note(ctx, x, y, s = 1, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const head = blob(x, y, 20, () => [11 * s, 8.5 * s]);
    if (!o.night) L.wash(ctx, head, { color: o.fill || P.washLilac, alpha: 0.55, p: d, seed: (o.seed || 19) + 1 });
    ink(ctx, head, o, { closed: true, draw: d, width: 2.6, seed: o.seed || 19 });
    ink(ctx, [[x + 10 * s, y - 2 * s], [x + 11 * s, y - 40 * s]], o, { draw: d, width: 2.6, seed: (o.seed || 19) + 2 });
    if (o.flag !== false) ink(ctx, [[x + 11 * s, y - 40 * s], [x + 26 * s, y - 30 * s], [x + 22 * s, y - 18 * s]], o, { draw: d, width: 2.4, seed: (o.seed || 19) + 3 });
  }

  /** flag(ctx, x, y, o) : a little pennant on a pole, y is the pole's foot. */
  function flag(ctx, x, y, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const h = o.h || 90;
    ink(ctx, [[x, y], [x - 2, y - h]], o, { draw: step(d, 0, 2), width: 3, seed: o.seed || 23 });
    const w = o.w || 62, wave = o.wave || 0;
    const pts = [
      [x - 2, y - h], [x + w * 0.5, y - h + 6 + wave], [x + w, y - h + 2 - wave],
      [x + w * 0.6, y - h + 30 + wave], [x - 2, y - h + 34],
    ];
    if (!o.night) L.wash(ctx, pts, { color: o.fill || P.washRed, alpha: 0.5, p: step(d, 1, 2), seed: (o.seed || 23) + 1 });
    ink(ctx, pts, o, { closed: true, draw: step(d, 1, 2), width: 2.8, seed: (o.seed || 23) + 2 });
  }

  /** trail(ctx, pts, o) : a travelling character's trail — a double line with sparkles along it. */
  function trail(ctx, pts, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    if (d <= 0 || !pts || pts.length < 2) return;
    ink(ctx, pts, o, { draw: d, width: o.width || 2.6, seed: o.seed || 29, alpha: o.alpha != null ? o.alpha : 0.75 });
    const off = pts.map(([x, y]) => [x, y + (o.gap || 9)]);
    ink(ctx, off, o, { draw: clamp(d * 1.1 - 0.08), width: (o.width || 2.6) * 0.8, seed: (o.seed || 29) + 1, alpha: (o.alpha != null ? o.alpha : 0.75) * 0.8 });
    const n = o.sparkles == null ? 3 : o.sparkles;
    for (let i = 0; i < n; i++) {
      const u = (i + 0.5) / n;
      if (d < u) continue;
      const k = Math.min(pts.length - 1, Math.floor(u * (pts.length - 1)));
      sparkle(ctx, pts[k][0], pts[k][1] - 14, 9, { seed: (o.seed || 29) + 5 + i, night: o.night, width: 1.8 });
    }
  }

  /** zzz(ctx, o) : three sleeping z's rising. */
  function zzz(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const s = o.s || 1;
    for (let i = 0; i < 3; i++) {
      const p = clamp(d * 3 - i);
      if (p <= 0) continue;
      const k = (26 - i * 6) * s;
      const x = o.x + i * 26 * s, y = o.y - i * 34 * s;
      ink(ctx, [[x, y], [x + k, y], [x, y + k], [x + k, y + k]], o, { draw: p, width: 2.6, smooth: false, seed: (o.seed || 31) + i });
    }
  }

  /** dust(ctx, x, y, o) : a puff of motion dust at the ground. */
  function dust(ctx, x, y, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const n = o.n || 3;
    for (let i = 0; i < n; i++) {
      const a = Math.PI + (i / (n - 1 || 1)) * Math.PI;
      const r = (o.r || 18) * (0.7 + 0.3 * Math.cos(i * 2.1));
      cloud(ctx, x + Math.cos(a) * (o.spread || 34), y + Math.sin(a) * 10, r * 2, {
        draw: clamp(d * 1.3 - i * 0.1),
        night: o.night,
        seed: (o.seed || 37) + i,
        fill: o.fill || P.washCream,
        fillAlpha: 0.3,
        width: 2.4,
      });
    }
  }

  /** drop(ctx, x, y, r, o) : a raindrop / teardrop, point up. */
  function drop(ctx, x, y, r, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const pts = [];
    for (let i = 0; i <= 30; i++) {
      const a = (i / 30) * TAU - Math.PI / 2;
      const rr = r * (1 - 0.45 * Math.cos(a)) * (a > Math.PI * 0.5 && a < Math.PI * 1.5 ? 1 : 1);
      pts.push([x + Math.cos(a) * rr * 0.72, y + Math.sin(a) * rr]);
    }
    if (!o.night) L.wash(ctx, pts, { color: o.fill || P.washBlue, alpha: 0.5, p: d, seed: (o.seed || 41) + 1 });
    ink(ctx, pts, o, { closed: true, draw: d, width: o.width || 2.4, seed: o.seed || 41 });
  }

  FILM.props = {
    bubble,
    sparkle,
    speedLines,
    starburst,
    cloud,
    sun,
    moon,
    heart,
    note,
    flag,
    trail,
    zzz,
    dust,
    drop,
    // primitives, for src/cast.js
    step,
    place,
    ink,
    wash,
    eye,
    blush,
    blob,
    inkOf,
  };
})();
