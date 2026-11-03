// Mini-motor de animación 2D para Reels (canvas 1080x1920).
// Cada escena es el CUERPO de una función: (ctx, t, A) => { ... } que dibuja el fotograma en el tiempo t.
// Debe ser determinista: el mismo t siempre produce la misma imagen (usa A.rand(semilla), nunca Math.random).
(function () {
  const W = 1080, H = 1920;
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  const ease = {
    linear: p => p,
    inCubic: p => p * p * p,
    outCubic: p => 1 - Math.pow(1 - p, 3),
    inOutCubic: p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    inOutSine: p => -(Math.cos(Math.PI * p) - 1) / 2,
    outBack: p => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
    outElastic: p => (p === 0 || p === 1 ? p : Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
  };
  const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const FONT = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

  function make(ctx, t, scene) {
    const A = {
      W, H, t, dur: scene.dur, accent: scene.accent, ctx, clamp, lerp, ease, FONT,
      // Momento (s) en que la voz dice una palabra. A.k('rompe') -> 2.31. n = enésima aparición.
      k(word, def = 0, n = 1) {
        const w = norm(word); let c = 0;
        for (const [ini, , txt] of scene.words) if (norm(txt).startsWith(w) && ++c === n) return ini;
        return def;
      },
      // Progreso 0..1 con curva entre start y start+len.
      p(start, len = 0.6, e = 'outCubic') { return ease[e](clamp((t - start) / Math.max(len, 1e-3))); },
      // Escala de "pop" (aparece rebotando) a partir de start.
      pop(start, len = 0.45) { return t < start ? 0 : ease.outBack(clamp((t - start) / len)); },
      // Generador aleatorio determinista.
      rand(seed = 1) { let s = seed * 9301 + 49297; return () => ((s = (s * 9301 + 49297) % 233280) / 233280); },
      counter(from, to, p, dec = 0) { return (from + (to - from) * clamp(p)).toLocaleString('es-MX', { minimumFractionDigits: dec, maximumFractionDigits: dec }); },

      // Fondo estándar del canal: degradado + rejilla técnica que se desplaza + viñeta.
      bg(top = '#0d1b2a', bottom = '#05070a', grid = true) {
        const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, top); g.addColorStop(1, bottom);
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
        if (grid) {
          ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 2;
          const off = (t * 20) % 90;
          for (let x = -90 + off; x < W + 90; x += 90) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
          for (let y = -90 + off; y < H + 90; y += 90) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
          ctx.restore();
        }
        const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.25, W / 2, H / 2, H * 0.75);
        v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.55)');
        ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
      },
      // Transformación temporal: A.with(() => {...}, {x, y, scale, rot, alpha, shake})
      with(fn, o = {}) {
        ctx.save();
        if (o.alpha !== undefined) ctx.globalAlpha *= clamp(o.alpha);
        if (o.shake) { const r = A.rand(Math.floor(t * 30) + 7); ctx.translate((r() - 0.5) * 2 * o.shake, (r() - 0.5) * 2 * o.shake); }
        const x = o.x || 0, y = o.y || 0; ctx.translate(x, y);
        if (o.rot) ctx.rotate(o.rot);
        if (o.scale !== undefined) ctx.scale(o.scale, o.scale);
        ctx.translate(-x, -y);
        fn(); ctx.restore();
      },
      _style(o) {
        ctx.globalAlpha *= o.alpha === undefined ? 1 : clamp(o.alpha);
        if (o.glow) { ctx.shadowColor = o.glowColor || o.fill || o.stroke || A.accent; ctx.shadowBlur = o.glow; }
        if (o.dash) ctx.setLineDash(o.dash);
        ctx.lineWidth = o.lw || 6; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      },
      circle(x, y, r, o = {}) {
        if (r <= 0) return; ctx.save(); A._style(o); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
        if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(); } if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.stroke(); } ctx.restore();
      },
      rect(x, y, w, h, o = {}) {
        ctx.save(); A._style(o); ctx.beginPath(); ctx.roundRect(x, y, w, h, o.r || 0);
        if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(); } if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.stroke(); } ctx.restore();
      },
      // Polilínea [[x,y],...] dibujada parcialmente según o.progress (0..1).
      line(pts, o = {}) {
        if (pts.length < 2) return; const prog = o.progress === undefined ? 1 : clamp(o.progress); if (prog <= 0) return;
        let total = 0; const seg = [];
        for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); total += d; }
        let rest = total * prog; ctx.save(); A._style(o); ctx.strokeStyle = o.stroke || A.accent; ctx.beginPath(); ctx.moveTo(...pts[0]);
        for (let i = 1; i < pts.length && rest > 0; i++) {
          const f = Math.min(1, rest / seg[i - 1]); ctx.lineTo(lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)); rest -= seg[i - 1];
        }
        ctx.stroke(); ctx.restore();
      },
      arrow(x1, y1, x2, y2, o = {}) {
        const p = o.progress === undefined ? 1 : clamp(o.progress); if (p <= 0) return;
        const ex = lerp(x1, x2, p), ey = lerp(y1, y2, p), c = o.color || A.accent, lw = o.lw || 10, hd = o.head || lw * 3;
        A.line([[x1, y1], [ex, ey]], { stroke: c, lw, alpha: o.alpha, glow: o.glow });
        const a = Math.atan2(y2 - y1, x2 - x1); ctx.save(); A._style(o); ctx.fillStyle = c; ctx.beginPath();
        ctx.moveTo(ex + Math.cos(a) * hd * 0.6, ey + Math.sin(a) * hd * 0.6);
        ctx.lineTo(ex + Math.cos(a + 2.5) * hd, ey + Math.sin(a + 2.5) * hd);
        ctx.lineTo(ex + Math.cos(a - 2.5) * hd, ey + Math.sin(a - 2.5) * hd); ctx.closePath(); ctx.fill(); ctx.restore();
      },
      text(str, x, y, o = {}) {
        ctx.save(); A._style(o); ctx.font = `${o.weight || 800} ${o.size || 60}px ${FONT}`;
        ctx.textAlign = o.align || 'center'; ctx.textBaseline = 'middle';
        if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.strokeWidth || 10; ctx.strokeText(str, x, y); }
        ctx.fillStyle = o.color || '#fff'; ctx.fillText(str, x, y); ctx.restore();
      },
      // Etiqueta tipo "píldora" con fondo de color.
      label(str, x, y, o = {}) {
        const size = o.size || 44; ctx.save(); ctx.font = `800 ${size}px ${FONT}`; const w = ctx.measureText(str).width + size * 1.2; ctx.restore();
        const s = o.scale === undefined ? 1 : o.scale; if (s <= 0) return;
        A.with(() => {
          A.rect(x - w / 2, y - size * 0.85, w, size * 1.7, { r: size * 0.85, fill: o.bg || A.accent, alpha: o.alpha, glow: o.glow });
          A.text(str, x, y + 2, { size, color: o.color || '#111', alpha: o.alpha });
        }, { x, y, scale: s });
      },
      // Ondas concéntricas que se expanden desde (x,y) a partir de start.
      rings(x, y, start, o = {}) {
        if (t < start) return; const n = o.count || 4, speed = o.speed || 500, gap = o.gap || 0.35, max = o.maxR || 900;
        for (let i = 0; i < n; i++) {
          const r = (t - start - i * gap) * speed; if (r <= 0 || r > max) continue;
          A.circle(x, y, r, { stroke: o.color || A.accent, lw: o.lw || 8, alpha: (1 - r / max) * (o.alpha || 1), glow: o.glow });
        }
      },
      // Partículas deterministas: fn(i, rnd) se llama para cada una.
      particles(n, seed, fn) { const r = A.rand(seed); for (let i = 0; i < n; i++) fn(i, r); },
      // Destello blanco breve (corte de impacto) en start.
      flash(start, len = 0.25, alpha = 0.8) {
        if (t < start || t > start + len) return; ctx.save(); ctx.globalAlpha = alpha * (1 - (t - start) / len);
        ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); ctx.restore();
      },
    };
    return A;
  }

  window.__escena = null;
  window.cargarEscena = function (codigo, scene) {
    window.__escena = { fn: new Function('ctx', 't', 'A', codigo), scene };
  };
  // Dibuja el fotograma t. Zoom lento automático para que nunca haya un plano estático.
  window.dibujar = function (t) {
    const cv = document.getElementById('c'), ctx = cv.getContext('2d'), e = window.__escena;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.shadowBlur = 0; ctx.setLineDash([]);
    ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    const z = 1 + 0.035 * clamp(t / Math.max(e.scene.dur, 0.1));
    ctx.translate(W / 2, H * 0.42); ctx.scale(z, z); ctx.translate(-W / 2, -H * 0.42);
    e.fn(ctx, t, make(ctx, t, e.scene));
  };
  window.lote = function (t0, n, fps, calidad) {
    const out = [], cv = document.getElementById('c');
    for (let i = 0; i < n; i++) { window.dibujar(t0 + i / fps); out.push(cv.toDataURL('image/jpeg', calidad).slice(23)); }
    return out;
  };
})();
