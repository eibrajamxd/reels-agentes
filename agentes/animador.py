"""AGENTE 4 — Animador: diseña y programa una animación explicativa por escena.

Ciclo por escena (hasta 3 intentos):
  1. Claude (animador) escribe el código de la animación, sincronizada con las palabras de la voz.
  2. Se ejecuta en un navegador sin ventana: si hay errores de JavaScript, vuelven al animador.
  3. Claude (director) mira 4 fotogramas reales y aprueba o pide correcciones concretas.
El código aprobado se guarda dentro del guion, así que volver a renderizar no cuesta nada.
"""
import base64
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

from .claude import pedir_json
from .config import CANAL_NOMBRE, CHROMIUM_PATH, ESTILO_ANIMACION

W, H = 1080, 1920
LIB = (Path(__file__).parent / "anim_lib.js").read_text(encoding="utf-8")
# Biblioteca de dibujo del skill procedural-film (MIT): trazo a mano, blueprint, papel, sombreado.
_FILM_LIB = Path(__file__).resolve().parent.parent / ".claude/skills/procedural-film/foundation/src/lib.js"
FILM_LIB = _FILM_LIB.read_text(encoding="utf-8") if _FILM_LIB.exists() else ""
# GSAP (licencia estándar gratuita de GreenSock), copiado desde el runtime de motionmaxxing.
_GSAP = Path(__file__).resolve().parent / "vendor/gsap.min.js"
GSAP = _GSAP.read_text(encoding="utf-8") if _GSAP.exists() else ""
HTML = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800;900&display=swap" rel="stylesheet">
<style>html,body{{margin:0;background:#000}}</style></head>
<body><canvas id="c" width="{W}" height="{H}"></canvas><script>{GSAP}</script><script>{FILM_LIB}</script><script>{LIB}</script></body></html>"""

API_DOC = """Escribe SOLO el cuerpo de una función JavaScript `(ctx, t, A) => { ... }` que dibuja en un canvas
2D de 1080x1920 el fotograma del instante t (segundos desde el inicio de la escena).
Debe ser determinista (prohibido Math.random y Date; usa A.rand(semilla)). Sin imágenes externas ni emojis.

API disponible (objeto A):
- A.W, A.H, A.t, A.dur (duración de la escena), A.accent (color de la escena), A.FONT, A.ctx
- A.k('palabra', def, n=1) -> segundo en que la voz dice esa palabra (n-ésima vez). ¡Úsalo para sincronizar!
- A.p(inicio, duracion=0.6, curva='softLand') -> progreso 0..1. Usa de preferencia las 12 curvas medidas de motion
  design profesional: snapSettle (entrada de héroe), softLand (textos y paneles), whip (movimiento grande), glide
  (movimiento mediano), crashIn (impacto), popOver / bounceHard (rebote, con moderación), softInOut (fundidos),
  cruise (lineal), gentleIn, accelExit / crashOut (salidas). También acepta curvas de GSAP: 'expo.out', 'back.out(2)'...
  Evita outCubic genérico en todo: elige la curva según el papel del movimiento.
- A.tl((tl, s) => {...}) -> estado: línea de tiempo GSAP construida una vez y llevada al instante t (determinista).
  Usa siempre tl.fromTo(s, {desde}, {hasta, duration, ease}, inicio) sobre propiedades de s, y dibuja con s.x, s.alpha...
- A.pop(inicio, dur=0.45) -> escala 0..~1.1..1 para que algo aparezca rebotando
- A.lerp(a,b,p), A.clamp(v,a=0,b=1), A.rand(semilla) -> función que da números 0..1, A.counter(desde,hasta,p,decimales) -> texto
- A.bg(colorArriba, colorAbajo, rejilla=true)  fondo del canal (llámalo primero)
- A.with(() => {...}, {x, y, scale, rot, alpha, shake})  transforma lo que dibujes dentro (escala/rota alrededor de x,y; shake=px de temblor)
- A.circle(x,y,r,{fill,stroke,lw,alpha,glow})   A.rect(x,y,w,h,{r,fill,stroke,lw,alpha,glow})
- A.line([[x,y],...],{stroke,lw,alpha,dash,progress})  línea que se dibuja progresivamente
- A.arrow(x1,y1,x2,y2,{progress,color,lw,head,alpha})
- A.text(str,x,y,{size,color,weight,align,alpha,stroke,strokeWidth})   A.label(str,x,y,{size,bg,color,scale,alpha})
- A.rings(x,y,inicio,{count,speed,gap,maxR,color,lw,alpha})  ondas expansivas
- A.particles(n, semilla, (i, rnd) => {...})   A.flash(inicio, dur, alpha)  destello de impacto
- Piezas listas: A.person(x,yPies,{scale,color}), A.bulb(x,y,{scale,on:0..1}), A.rainbow(cx,cy,r,{width,progress,from,to,alpha}),
  A.drop(x,y,r,{fill,stroke}), A.sun(x,y,r), A.ant(x,y,escala), A.ray([[x,y],...],{color,lw,progress}),
  A.follow(x,y,inicio,toque) botón "Seguir" que se presiona, A.ARCOIRIS (7 colores de rojo a violeta)
- Estilo película (skill procedural-film): A.bg pinta un plano blueprint y A.line/A.circle/A.rect con trazo se
  dibujan como tinta a mano con "boil". Para acabado de ilustración usa también A.lib (FILM.lib), con
  ctx como primer argumento: A.lib.inkPath(ctx, pts, {width, color, closed, fill, draw}),
  A.lib.hatch(ctx, pts, {angle, spacing, width, color}) para sombrear dentro de una forma,
  A.lib.crossHatch(ctx, pts, {tone}), A.lib.stipple(ctx, pts, {...}), A.lib.glowDot(ctx, x, y, r, {...}),
  y la paleta A.pal (navy, lineWhite, paleBlue, glow, magenta, ink, paper...). Sombrea las formas grandes con hatch.
- También puedes usar ctx directamente (paths, gradientes, bezier...).

ZONAS DE LA PANTALLA (obligatorio respetarlas):
- y 200–380: titular de la escena (lo pone el sistema). No pongas texto ahí.
- y 1150–1310: subtítulos (los pone el sistema). Nada importante ahí.
- y 1780–1920: marca del canal.
- Zona principal para la animación: y 420–1120 (el centro de atención). Zona secundaria: y 1340–1740.

CRITERIO DE MOTION DESIGN (skill motionmaxxing):
- Un solo elemento protagonista por momento; lo grande necesita algo pequeño al lado. Gasta el énfasis, no lo reparte.
- Cada movimiento causa el siguiente: un objeto se convierte en el de la siguiente idea; evita fundidos entre todo.
- Sostén un instante antes de lo importante; nada de contadores "01/05", etiquetas en esquinas ni tarjetas genéricas.

PRINCIPIOS DE RETENCIÓN:
- Algo debe cambiar en pantalla al menos cada 1.5 s; nunca un plano quieto.
- Cada concepto que dice la voz aparece EXACTAMENTE cuando lo dice (usa A.k).
- Muestra el mecanismo (cómo funciona), no decoración: diagramas, cortes transversales, flechas de fuerza,
  contadores, comparaciones de tamaño, antes/después. Estilo motion graphics plano y moderno, alto contraste.
- Impacto en los momentos clave: pop, shake, flash, ondas. Etiquetas cortas (1–3 palabras) grandes y legibles.
- Paleta: fondo oscuro, acento de la escena, blanco, y un color de contraste como máximo."""

SYSTEM_ANIMADOR = f"""Eres el animador de motion graphics de "{CANAL_NOMBRE}", un canal de Reels que explica
cómo funcionan las cosas. Conviertes cada escena del guion en una animación explicativa que retiene
al espectador y le hace ENTENDER el fenómeno.\n\n{API_DOC}"""

SYSTEM_DIRECTOR = """Eres el director de animación. Recibes 4 fotogramas de una escena de un Reel (1080x1920,
mostrados reducidos con su tiempo) y la narración. Aprueba solo si: se entiende qué representa, ilustra lo
que dice la narración, nada importante cae en la zona de subtítulos (y 1150–1310, marcada en rojo) ni del
titular (y 200–380, marcada en azul), el texto es legible y hay cambio visible entre fotogramas.
Si no apruebas, da correcciones concretas y accionables (posiciones, tamaños, qué agregar o quitar)."""

SCHEMA_CODIGO = {
    "type": "object",
    "properties": {"idea": {"type": "string"}, "codigo": {"type": "string"}},
    "required": ["idea", "codigo"],
    "additionalProperties": False,
}
SCHEMA_REVISION = {
    "type": "object",
    "properties": {"aprobado": {"type": "boolean"}, "correcciones": {"type": "string"}},
    "required": ["aprobado", "correcciones"],
    "additionalProperties": False,
}


class Renderizador:
    """Navegador sin ventana que ejecuta y graba las animaciones."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        opciones = {"executable_path": CHROMIUM_PATH} if CHROMIUM_PATH else {}
        self._browser = self._pw.chromium.launch(**opciones)
        self.page = self._browser.new_page(viewport={"width": 540, "height": 960})
        self.errores: list[str] = []
        self.page.on("pageerror", lambda e: self.errores.append(str(e)))
        self.page.set_content(HTML, wait_until="load")
        self.page.evaluate("document.fonts.ready.then(() => true)")
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def _cargar(self, codigo: str, escena: dict):
        self.errores.clear()
        self.page.evaluate("([c, s]) => cargarEscena(c, s)", [codigo, escena])

    def probar(self, codigo: str, escena: dict) -> tuple[str | None, bytes | None]:
        """Devuelve (error, hoja_de_contacto_png)."""
        try:
            self._cargar(codigo, escena)
            tiempos = [round(escena["dur"] * f, 2) for f in (0.12, 0.4, 0.68, 0.95)]
            cuadros = []
            for t in tiempos:
                self.page.evaluate("t => dibujar(t)", t)
                b64 = self.page.evaluate("document.getElementById('c').toDataURL('image/jpeg', 0.8).slice(23)")
                cuadros.append(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"))
        except Exception as e:  # error de sintaxis o de ejecución en el código generado
            return str(e).split("Call log")[0][:1500], None
        if self.errores:
            return self.errores[0][:1500], None
        return None, _hoja(cuadros, tiempos)

    def grabar(self, codigo: str, escena: dict, salida: Path, fps: int = 30):
        self._cargar(codigo, escena)
        n_total = int(round(escena["dur"] * fps))
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg",
             "-framerate", str(fps), "-i", "-", "-frames:v", str(n_total), "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), str(salida)],
            stdin=subprocess.PIPE,
        )
        for i in range(0, n_total, 15):
            for b64 in self.page.evaluate("([t, n, f]) => lote(t, n, f, 0.9)", [i / fps, min(15, n_total - i), fps]):
                ff.stdin.write(base64.b64decode(b64))
        ff.stdin.close()
        if ff.wait() != 0 or self.errores:
            raise RuntimeError(f"Fallo al grabar la animación: {self.errores[:1]}")


def _hoja(cuadros, tiempos) -> bytes:
    ancho, alto = 270, 480
    hoja = Image.new("RGB", (ancho * 4 + 30, alto + 40), "white")
    d = ImageDraw.Draw(hoja)
    for i, (im, t) in enumerate(zip(cuadros, tiempos)):
        im = im.resize((ancho, alto))
        dd = ImageDraw.Draw(im)
        f = alto / H
        dd.rectangle([0, 200 * f, ancho, 380 * f], outline=(60, 120, 255), width=2)
        dd.rectangle([0, 1150 * f, ancho, 1310 * f], outline=(255, 40, 40), width=2)
        x = i * (ancho + 10)
        hoja.paste(im, (x, 40))
        d.text((x + 6, 10), f"t = {t:.2f}s", fill="black")
    buf = io.BytesIO()
    hoja.save(buf, "PNG")
    return buf.getvalue()


def _datos_escena(escena: dict, dur: float, palabras) -> dict:
    return {"dur": round(dur, 3), "accent": escena.get("color", "#FFD400"), "estilo": ESTILO_ANIMACION,
            "words": [[round(a, 3), round(b, 3), w] for a, b, w in palabras]}


def _pedir_codigo(guion, i, datos, previo=None, feedback=None) -> str:
    escena = guion["escenas"][i]
    contexto = [f"{j + 1}. {e['narracion']}" for j, e in enumerate(guion["escenas"])]
    prompt = (
        f"Reel: {guion['titulo']}\nGuion completo (contexto):\n" + "\n".join(contexto) +
        f"\n\nAnima la ESCENA {i + 1} de {len(guion['escenas'])}.\nNarración: \"{escena['narracion']}\"\n"
        f"Titular en pantalla: {escena['texto_pantalla']}\nColor de acento: {datos['accent']}\n"
        f"Duración: {datos['dur']} s\nTiempos de cada palabra [inicio, fin, palabra]: {json.dumps(datos['words'], ensure_ascii=False)}\n"
    )
    if previo:
        prompt += f"\nVersión anterior del código:\n```js\n{previo}\n```\nProblema a corregir:\n{feedback}\n"
    return pedir_json(SYSTEM_ANIMADOR, prompt, SCHEMA_CODIGO, effort="high", max_tokens=24000)["codigo"]


def _revisar(escena, png: bytes) -> dict:
    contenido = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.b64encode(png).decode()}},
        {"type": "text", "text": f"Narración de la escena: \"{escena['narracion']}\"\n"
                                 f"Titular: {escena['texto_pantalla']}\n¿Apruebas la animación?"},
    ]
    return pedir_json(SYSTEM_DIRECTOR, contenido, SCHEMA_REVISION, effort="medium", max_tokens=4000)


def animar_guion(guion: dict, voces, indices: list[int], rend: Renderizador, intentos: int = 3):
    """Genera (o reutiliza) la animación de las escenas indicadas. Modifica `guion` en sitio."""
    datos = {i: _datos_escena(guion["escenas"][i], voces[i][1], voces[i][2]) for i in indices}
    pendientes = [i for i in indices if not guion["escenas"][i].get("animacion")]
    codigo: dict[int, str] = {}
    feedback: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for intento in range(1, intentos + 1):
            if not pendientes:
                break
            print(f"   🖌️  Animador: intento {intento} para escenas {[i + 1 for i in pendientes]}")
            nuevos = pool.map(lambda i: (i, _pedir_codigo(guion, i, datos[i], codigo.get(i), feedback.get(i))), pendientes)
            hojas = {}
            for i, cod in nuevos:
                codigo[i] = cod
                err, png = rend.probar(cod, datos[i])
                if err:
                    feedback[i] = f"El código lanzó este error de JavaScript: {err}"
                    print(f"      ✗ escena {i + 1}: error JS")
                else:
                    hojas[i] = png
            revisiones = pool.map(lambda i: (i, _revisar(guion["escenas"][i], hojas[i])), list(hojas))
            for i, rev in revisiones:
                ultimo = intento == intentos
                if rev["aprobado"] or ultimo:
                    guion["escenas"][i]["animacion"] = codigo[i]
                    pendientes.remove(i)
                    print(f"      ✓ escena {i + 1}: {'aprobada' if rev['aprobado'] else 'aceptada (último intento)'}")
                else:
                    feedback[i] = f"El director pidió: {rev['correcciones']}"
                    print(f"      ↻ escena {i + 1}: {rev['correcciones'][:90]}")
            pendientes = [i for i in pendientes if i not in hojas or not guion["escenas"][i].get("animacion")]
    for i in pendientes:
        print(f"   ! Escena {i + 1} sin animación válida: se usará video de fondo.")
    return datos
