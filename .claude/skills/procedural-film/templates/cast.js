/*
 * cast.js : THIS FILM'S recurring characters — copy this file into src/ and rewrite the bodies for
 * your own cast. Loaded after src/props.js and before the scenes.
 *
 * The example below is the cast of "The slowest race": a snail, a beetle and a bird. What to keep
 * when you replace them:
 *   - one function per character, taking { x, y, s, flip, pose, draw, seed, night, blink, tilt }
 *   - every stroke through P.ink / P.wash, so the boil, the draw-on and the night plate all work
 *   - P.step(draw, i, n) to reveal the strokes in drawing order
 *   - a returned anchor object ({ head, eye, ... }) so scenes hang props off the character instead
 *     of guessing pixels
 *   - poses as a small named set, not free parameters: scene agents pick from a list
 */
(function () {
  'use strict';

  const FILM = window.FILM;
  const L = FILM.lib;
  const P = FILM.props;
  const TAU = Math.PI * 2;
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const { step, place, ink, wash, eye, blush, blob } = P;
  const inkOf = P.inkOf;

  // This cast's own colours. The mode's house colours (inks, washes, paper tints, blush) already live
  // in lib.pal; a character's colours are per-film, so write them into the subject palette block of
  // src/lib.js and read them here as L.pal.<name>. The literals are the fallback, so the template
  // still draws before you have done that.
  const SHELL = L.pal.shellA || '#E0A15C';
  const BODY = L.pal.snailBody || '#F2E3CE';
  const BEETLE = L.pal.beetleRed || '#CF5B48';
  const BIRD = L.pal.birdBlue || '#8FB8D8';

  // ---------------------------------------------------------------------------
  // Pim, the snail
  // ---------------------------------------------------------------------------

  /**
   * snail(ctx, o) : the hero. Local frame is 180 px nose to tail at s = 1, standing on y = o.y.
   *   pose   crawl (default) | reach | cheer | tired | sleep | look
   *   number true to letter a small 7 on the shell (his race number)
   * Returns { head: [x, y], shellTop: [x, y], tail: [x, y], eye: [x, y] } in world coordinates.
   */
  function snail(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const pose = o.pose || 'crawl';
    const sd = o.seed == null ? 31 : o.seed;
    const sleep = pose === 'sleep';
    const tired = pose === 'tired';
    const cheer = pose === 'cheer';
    const reach = pose === 'reach';
    const headUp = cheer ? -26 : reach ? -18 : tired ? 6 : sleep ? 10 : 0;
    const stalkA = cheer ? -0.5 : tired ? 0.45 : sleep ? 0.9 : reach ? -0.25 : 0;
    const anchors = {};
    place(ctx, o, () => {
      // 1 foot: a long flat sole with a curled tail
      const foot = [
        [-86, 0], [-72, -13], [-40, -19], [0, -20], [38, -18], [62, -14], [76, -8], [82, 0],
      ];
      const sole = foot.concat([[40, 2], [-40, 2]]);
      if (d > 0) wash(ctx, sole, o, BODY, { p: step(d, 0, 6), seed: sd + 1, offset: [3, 2] });
      ink(ctx, foot, o, { draw: step(d, 0, 6), width: 3.6, seed: sd });
      ink(ctx, [[-86, 0], [0, 3], [82, 0]], o, { draw: step(d, 1, 6), width: 2.6, seed: sd + 2 });
      // 2 shell: a spiral shell sitting on the back
      const scx = -14, scy = -64, R = 52;
      const shellPts = blob(scx, scy, 40, (a) => [R * (1 + 0.05 * Math.cos(a * 2)), R * 0.94]);
      if (d > 0) wash(ctx, shellPts, o, SHELL, { p: step(d, 2, 6), seed: sd + 3, alpha: 0.55 });
      ink(ctx, shellPts, o, { closed: true, draw: step(d, 2, 6), width: 3.8, seed: sd + 4 });
      const spiral = [];
      for (let i = 0; i <= 64; i++) {
        const u = i / 64;
        const a = u * TAU * 2.1 + 0.6;
        const r = R * 0.9 * (1 - u * 0.86);
        spiral.push([scx + Math.cos(a) * r, scy + Math.sin(a) * r * 0.94]);
      }
      ink(ctx, spiral, o, { draw: step(d, 3, 6), width: 2.8, seed: sd + 5 });
      // 3 neck and head
      const hx = 84, hy = -34 + headUp;
      const neck = [[52, -16], [70, -24], [80, -30 + headUp * 0.6], [hx, hy]];
      ink(ctx, neck, o, { draw: step(d, 4, 6), width: 3.2, seed: sd + 6 });
      const headPts = blob(hx, hy, 26, () => [21, 19]);
      if (d > 0) wash(ctx, headPts, o, BODY, { p: step(d, 4, 6), seed: sd + 7, offset: [2, 2] });
      ink(ctx, headPts, o, { closed: true, draw: step(d, 4, 6), width: 3.2, seed: sd + 8 });
      // 4 eye stalks, face
      const s5 = step(d, 5, 6);
      const stalk = (dx, la) => {
        const bx = hx + dx, by = hy - 14;
        const tipx = bx + dx * 0.9 + Math.sin(la) * 14;
        const tipy = by - 34 + Math.abs(la) * 10;
        ink(ctx, [[bx, by], [bx + dx * 0.4 + Math.sin(la) * 6, by - 20], [tipx, tipy]], o, {
          draw: s5,
          width: 2.8,
          seed: sd + 9 + dx,
        });
        if (s5 > 0.7) eye(ctx, tipx, tipy - 3, 5.2, o, sleep ? 1 : o.blink || 0);
        return [tipx, tipy];
      };
      const e1 = stalk(6, stalkA);
      stalk(-9, stalkA * 0.7);
      if (s5 > 0.8) {
        blush(ctx, hx + 12, hy + 5, 8, o);
        const mouth = sleep
          ? [[hx + 8, hy + 6], [hx + 14, hy + 9], [hx + 18, hy + 6]]
          : cheer
            ? [[hx + 4, hy + 3], [hx + 12, hy + 12], [hx + 19, hy + 2]]
            : tired
              ? [[hx + 6, hy + 10], [hx + 14, hy + 6], [hx + 19, hy + 10]]
              : [[hx + 7, hy + 6], [hx + 15, hy + 10], [hx + 19, hy + 5]];
        ink(ctx, mouth, o, { draw: 1, width: 2.4, seed: sd + 12 });
      }
      if (o.number && s5 > 0.9) {
        ctx.save();
        ctx.scale(o.flip ? -1 : 1, 1);
        L.hand(ctx, '7', (o.flip ? -1 : 1) * (scx - 2), scy + 12, { size: 34, color: inkOf(o), align: 'center', alpha: 0.9 });
        ctx.restore();
      }
      if (sleep && s5 > 0.9) {
        P.zzz(ctx, { x: scx + 10, y: scy - 62, s: 0.8, night: o.night, draw: 1, seed: sd });
      }
      anchors.localHead = [hx, hy];
      anchors.localEye = e1;
      anchors.localShell = [scx, scy - R];
    });
    const s = o.s != null ? o.s : 1;
    const f = o.flip ? -1 : 1;
    const toWorld = (p) => [o.x + p[0] * s * f, o.y + p[1] * s];
    return {
      head: toWorld(anchors.localHead || [84, -34]),
      eye: toWorld(anchors.localEye || [90, -68]),
      shellTop: toWorld(anchors.localShell || [-14, -116]),
      tail: toWorld([-86, 0]),
    };
  }

  // ---------------------------------------------------------------------------
  // Zip, the beetle (the fast one)
  // ---------------------------------------------------------------------------

  /** beetle(ctx, o) : 120 px long at s = 1, standing on y = o.y. pose: stand | run | smug. */
  function beetle(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const sd = o.seed == null ? 77 : o.seed;
    const run = o.pose === 'run';
    const ph = o.phase || 0;
    const anchors = {};
    place(ctx, o, () => {
      // legs first (they sit behind the body)
      const s0 = step(d, 0, 5);
      for (let i = 0; i < 3; i++) {
        const bx = -24 + i * 24;
        const sw = run ? Math.sin(ph * TAU + i * 1.6) * 12 : (i - 1) * 4;
        // near legs: hip, knee out, foot on the ground
        ink(ctx, [[bx, -34], [bx - 16 + sw, -20], [bx - 22 + sw * 1.5, 0]], o, { draw: s0, width: 2.8, seed: sd + i });
        // far legs, lighter
        ink(ctx, [[bx, -34], [bx + 12 + sw, -22], [bx + 16 + sw, -6]], o, { draw: s0, width: 2.2, seed: sd + 10 + i, alpha: 0.75 });
      }
      // body: a rounded carapace
      const body = blob(0, -52, 34, () => [46, 28]);
      if (d > 0) wash(ctx, body, o, BEETLE, { p: step(d, 1, 5), seed: sd + 20, alpha: 0.5 });
      ink(ctx, body, o, { closed: true, draw: step(d, 1, 5), width: 3.6, seed: sd + 21 });
      ink(ctx, [[0, -79], [0, -25]], o, { draw: step(d, 2, 5), width: 2.6, seed: sd + 22, smooth: false });
      // head
      const head = blob(48, -58, 24, () => [20, 18]);
      if (d > 0) wash(ctx, head, o, BEETLE, { p: step(d, 3, 5), seed: sd + 23, alpha: 0.4 });
      ink(ctx, head, o, { closed: true, draw: step(d, 3, 5), width: 3.2, seed: sd + 24 });
      const s4 = step(d, 4, 5);
      ink(ctx, [[54, -72], [72, -100]], o, { draw: s4, width: 2.4, seed: sd + 25 });
      ink(ctx, [[44, -74], [52, -104]], o, { draw: s4, width: 2.4, seed: sd + 26 });
      if (s4 > 0.7) {
        eye(ctx, 54, -60, 4.4, o, o.blink || 0);
        blush(ctx, 60, -52, 6, o);
        ink(ctx, o.pose === 'smug' ? [[46, -50], [56, -46], [62, -52]] : [[48, -50], [56, -44], [62, -50]], o, {
          draw: 1,
          width: 2.2,
          seed: sd + 27,
        });
      }
      anchors.localHead = [48, -58];
    });
    const s = o.s != null ? o.s : 1;
    const f = o.flip ? -1 : 1;
    const lh = anchors.localHead || [48, -58];
    return { head: [o.x + lh[0] * s * f, o.y + lh[1] * s] };
  }

  // ---------------------------------------------------------------------------
  // Bo, the bird (the crowd, the commentator)
  // ---------------------------------------------------------------------------

  /** bird(ctx, o) : 110 px tall at s = 1, feet on y = o.y. pose: stand | fly | cheer | peek. */
  function bird(ctx, o = {}) {
    const d = o.draw == null ? 1 : clamp(o.draw);
    const sd = o.seed == null ? 53 : o.seed;
    const fly = o.pose === 'fly';
    const cheer = o.pose === 'cheer';
    const ph = o.phase || 0;
    place(ctx, o, () => {
      if (!fly) {
        const s0 = step(d, 0, 5);
        ink(ctx, [[-10, -22], [-12, -4], [-20, 0]], o, { draw: s0, width: 2.4, seed: sd });
        ink(ctx, [[-12, -4], [-4, 0]], o, { draw: s0, width: 2.2, seed: sd + 1 });
        ink(ctx, [[10, -22], [12, -4], [4, 0]], o, { draw: s0, width: 2.4, seed: sd + 2 });
        ink(ctx, [[12, -4], [20, 0]], o, { draw: s0, width: 2.2, seed: sd + 3 });
      }
      const body = blob(0, -52, 34, (a) => [36, 40]);
      if (d > 0) wash(ctx, body, o, BIRD, { p: step(d, 1, 5), seed: sd + 4, alpha: 0.5 });
      ink(ctx, body, o, { closed: true, draw: step(d, 1, 5), width: 3.4, seed: sd + 5 });
      // wing(s)
      const flap = fly ? Math.sin(ph * TAU) * 26 : cheer ? -20 : 0;
      ink(ctx, [[-6, -62], [-30, -70 + flap], [-40, -52 + flap * 0.6], [-16, -44]], o, {
        draw: step(d, 2, 5),
        width: 3,
        seed: sd + 6,
        closed: true,
      });
      if (fly || cheer) {
        ink(ctx, [[6, -62], [30, -70 + flap], [40, -52 + flap * 0.6], [16, -44]], o, {
          draw: step(d, 2, 5),
          width: 3,
          seed: sd + 7,
          closed: true,
        });
      }
      const s3 = step(d, 3, 5);
      ink(ctx, [[30, -60], [50, -56], [30, -50]], o, { draw: s3, width: 2.8, seed: sd + 8, closed: true, fill: o.night ? null : L.pal.washYellow });
      const s4 = step(d, 4, 5);
      if (s4 > 0.6) {
        eye(ctx, 18, -64, 4.6, o, o.blink || 0);
        blush(ctx, 24, -54, 7, o);
        ink(ctx, [[-4, -88], [2, -100]], o, { draw: s4, width: 2.2, seed: sd + 9 });
        ink(ctx, [[2, -88], [10, -99]], o, { draw: s4, width: 2.2, seed: sd + 10 });
      }
    });
    const s = o.s != null ? o.s : 1;
    return { head: [o.x, o.y - 64 * s] };
  }

  FILM.cast = { snail, beetle, bird };
})();
