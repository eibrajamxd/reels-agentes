"""AGENTE 2 — Productor de video: guion -> Reel vertical 1080x1920 con voz, subtítulos y B-roll.

Pasos: locución dirigida por el Agente Narrador (voz neural con tiempos por palabra) -> animación por escena hecha por
el Agente Animador (o video de Pexels / fondo generado) -> subtítulos animados palabra por palabra (ASS) ->
barra de progreso -> música opcional -> MP4 listo para Instagram.
"""
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from .config import CANAL_HANDLE, DIR_MUSICA, DIR_SALIDA, MODO_VISUAL, PEXELS_API_KEY, VOZ
from .guionista import slug

W, H, FPS = 1080, 1920, 30
PAUSA = 0.25  # silencio entre escenas (s)


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *map(str, args)], check=True)


def _duracion(ruta) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


# ---------------------------------------------------------------- voz
def _tiempos_estimados(texto: str, duracion: float) -> list[tuple[float, float, str]]:
    ps = texto.split()
    paso = duracion / max(len(ps), 1)
    return [(i * paso, (i + 1) * paso, p) for i, p in enumerate(ps)]


def generar_voz(escenas, tmp: Path, con_voz: bool):
    """Devuelve [(wav, duracion, palabras)] por escena. La voz la pone el Agente Narrador."""
    from . import narrador

    res = []
    for i, e in enumerate(escenas):
        wav = tmp / f"voz_{i}.wav"
        texto = (e.get("locucion") or {}).get("texto_hablado") or e["narracion"]
        if con_voz:
            mp3 = tmp / f"voz_{i}.mp3"
            palabras, pausa = narrador.locutar(e, mp3)
            dur = _duracion(mp3) + pausa
            _ff("-i", mp3, "-af", f"apad,atrim=0:{dur:.3f}", "-ar", 44100, "-ac", 2, wav)
            if not palabras:
                palabras = _tiempos_estimados(texto, dur - pausa)
        else:  # modo sin conexión: silencio con tiempos estimados (~3 palabras/s)
            dur = len(texto.split()) / 3.0 + PAUSA
            _ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{dur:.3f}", wav)
            palabras = _tiempos_estimados(texto, dur - PAUSA)
        res.append((wav, dur, palabras))
    return res


# ---------------------------------------------------------------- fondos
def _buscar_pexels(consulta: str, usados: set, tmp: Path) -> Path | None:
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": consulta, "orientation": "portrait", "per_page": 8},
            timeout=20,
        )
        r.raise_for_status()
        for v in r.json().get("videos", []):
            if v["id"] in usados:
                continue
            archivos = [a for a in v["video_files"] if a.get("height") and a["height"] >= a.get("width", 0)
                        and a["height"] >= 1280 and a.get("file_type") == "video/mp4"]
            if not archivos:
                continue
            mejor = min(archivos, key=lambda a: abs(a["height"] - 1920))
            destino = tmp / f"pexels_{v['id']}.mp4"
            with requests.get(mejor["link"], stream=True, timeout=60) as d:
                d.raise_for_status()
                with open(destino, "wb") as f:
                    shutil.copyfileobj(d.raw, f)
            usados.add(v["id"])
            return destino
    except requests.RequestException as e:
        print(f"   ! Pexels falló para '{consulta}': {e}")
    return None


def _hex(c: str, defecto=(255, 196, 0)):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", c.strip())
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if m else defecto


def _fondo_generado(color: str, png: Path, semilla: int):
    """Fondo oscuro con degradado y orbes de luz del color de la escena."""
    base = _hex(color)
    img = Image.new("RGB", (W + 160, H + 160))
    d = ImageDraw.Draw(img)
    for y in range(img.height):
        k = y / img.height
        d.line([(0, y), (img.width, y)], fill=tuple(int(c * (0.10 + 0.22 * k)) + 8 for c in base))
    capa = Image.new("RGB", img.size, (0, 0, 0))
    dc = ImageDraw.Draw(capa)
    rnd = random.Random(semilla)
    for _ in range(7):
        r = rnd.randint(140, 420)
        x, y = rnd.randint(0, img.width), rnd.randint(0, img.height)
        dc.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(c * rnd.uniform(0.35, 0.8)) for c in base))
    capa = capa.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, capa, 0.55)
    # rejilla sutil tipo "plano técnico"
    d = ImageDraw.Draw(img)
    for x in range(0, img.width, 90):
        d.line([(x, 0), (x, img.height)], fill=tuple(min(255, c + 14) for c in img.getpixel((x, 10))), width=1)
    for y in range(0, img.height, 90):
        d.line([(0, y), (img.width, y)], fill=tuple(min(255, c + 14) for c in img.getpixel((10, y))), width=1)
    img.save(png)


def generar_fondo(escena, i, dur, tmp: Path, usados: set) -> Path:
    salida = tmp / f"escena_{i}.mp4"
    clip = _buscar_pexels(escena["busqueda_video"], usados, tmp)
    comunes = ["-t", f"{dur:.3f}", "-r", FPS, "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", 20, "-pix_fmt", "yuv420p", salida]
    if clip:
        _ff("-stream_loop", -1, "-i", clip,
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                   f"eq=brightness=-0.06:saturation=1.1,fps={FPS}", *comunes)
    else:
        png = tmp / f"fondo_{i}.png"
        _fondo_generado(escena.get("color", "#FFC400"), png, i)
        mov = f"80+70*sin(2*PI*t/{max(dur, 1) * 1.6:.2f})"
        _ff("-loop", 1, "-i", png, "-vf", f"crop={W}:{H}:x='{mov}':y='{mov}',fps={FPS}", *comunes)
    return salida


# ---------------------------------------------------------------- subtítulos
def _t(s: float) -> str:
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(txt: str) -> str:
    return txt.replace("\\", "").replace("{", "(").replace("}", ")")


def _bloques(palabras, max_palabras=3):
    bloque = []
    for p in palabras:
        bloque.append(p)
        if len(bloque) >= max_palabras or re.search(r"[.,;:?!…]$", p[2]):
            yield bloque
            bloque = []
    if bloque:
        yield bloque


def generar_ass(escenas, voces, ruta: Path, total: float):
    lineas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Sub,Inter ExtraBold,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,4,5,60,60,0,1",
        "Style: Titulo,Inter ExtraBold,74,&H00111111,&H00FFFFFF,&H0000D4FF,&H0000D4FF,-1,0,0,0,100,100,1,0,3,22,0,8,80,80,250,1",
        "Style: Marca,Inter SemiBold,40,&H66FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,2,0,2,40,40,120,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    t0 = 0.0
    for escena, (_, dur, palabras) in zip(escenas, voces):
        r, g, b = _hex(escena.get("color", "#FFD400"))
        acento = f"&H00{b:02X}{g:02X}{r:02X}&"
        # Titular de la escena (arriba, en caja de color)
        lineas.append(
            f"Dialogue: 1,{_t(t0)},{_t(t0 + dur)},Titulo,,0,0,0,,"
            f"{{\\3c{acento}\\4c{acento}\\fad(180,120)\\t(0,180,\\fscx100\\fscy100)\\fscx85\\fscy85}}"
            f"{_esc(escena['texto_pantalla'].upper())}"
        )
        # Subtítulos palabra por palabra con la palabra activa resaltada
        for bloque in _bloques(palabras):
            for j, (ini, fin, _) in enumerate(bloque):
                sig = bloque[j + 1][0] if j + 1 < len(bloque) else fin + 0.12
                partes = []
                for k, (_, _, w) in enumerate(bloque):
                    w = _esc(w.upper())
                    partes.append(f"{{\\c{acento}\\fscx108\\fscy108}}{w}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}" if k == j else w)
                lineas.append(
                    f"Dialogue: 0,{_t(t0 + ini)},{_t(t0 + max(sig, ini + 0.08))},Sub,,0,0,0,,"
                    f"{{\\pos({W // 2},{int(H * 0.64)})}}" + " ".join(partes)
                )
        t0 += dur
    lineas.append(f"Dialogue: 0,{_t(0)},{_t(total)},Marca,,0,0,0,,{_esc(CANAL_HANDLE)}")
    ruta.write_text("\n".join(lineas), encoding="utf-8")


# ---------------------------------------------------------------- ensamblado
def escenas_a_animar(n: int, modo: str = MODO_VISUAL) -> list[int]:
    if modo == "broll":
        return []
    if modo == "mixto":  # gancho, cierre y escenas pares animadas; el resto con video real
        return sorted({0, n - 1, *range(0, n, 2)})
    return list(range(n))


def producir_video(guion: dict, con_voz: bool = True, musica: str | None = None,
                   animar: bool = True, ruta_guion: str | None = None) -> str:
    escenas = guion["escenas"]
    carpeta = DIR_SALIDA / slug(guion.get("tema") or guion["titulo"])
    tmp = carpeta / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    def guardar_guion():
        if ruta_guion:  # guarda locución y animaciones aprobadas para no volver a pagarlas
            Path(ruta_guion).write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")

    if con_voz:
        if not VOZ:
            raise SystemExit("Aún no eliges voz. Escúchalas con `python main.py voces` y luego "
                             "`python main.py elegir-voz <nombre>`.")
        from .narrador import dirigir_locucion

        print("🎭 Agente Narrador dirigiendo la locución...")
        dirigir_locucion(guion)
        guardar_guion()
        for i, e in enumerate(escenas):
            loc = e.get("locucion", {})
            print(f"   {i + 1}. {loc.get('intencion', '')}  ({loc.get('velocidad', '')}, {loc.get('tono', '')})")
    print(f"🎙️  Grabando voz ({VOZ or 'sin voz'})...")
    voces = generar_voz(escenas, tmp, con_voz)
    total = sum(d for _, d, _ in voces)

    usados: set = set()
    clips = []
    indices = escenas_a_animar(len(escenas)) if animar else []
    if indices:
        from .animador import Renderizador, animar_guion

        print("✨ Agente Animador trabajando...")
        with Renderizador() as rend:
            datos = animar_guion(guion, voces, indices, rend)
            guardar_guion()
            print("🎞️  Grabando escenas...")
            for i, (e, (_, d, _)) in enumerate(zip(escenas, voces)):
                if i in datos and e.get("animacion"):
                    salida = tmp / f"escena_{i}.mp4"
                    try:
                        rend.grabar(e["animacion"], datos[i], salida)
                        clips.append(salida)
                        continue
                    except Exception as err:
                        print(f"   ! Escena {i + 1}: {err}; uso video de fondo")
                clips.append(generar_fondo(e, i, d, tmp, usados))
    else:
        print("🎞️  Preparando fondos de cada escena...")
        clips = [generar_fondo(e, i, d, tmp, usados) for i, (e, (_, d, _)) in enumerate(zip(escenas, voces))]

    lista_v = tmp / "videos.txt"
    lista_v.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    lista_a = tmp / "audios.txt"
    lista_a.write_text("".join(f"file '{w.resolve()}'\n" for w, _, _ in voces))
    _ff("-f", "concat", "-safe", 0, "-i", lista_v, "-c", "copy", tmp / "fondo.mp4")
    _ff("-f", "concat", "-safe", 0, "-i", lista_a, tmp / "voz.wav")

    print("🔤 Subtítulos animados...")
    ass = tmp / "subs.ass"
    generar_ass(escenas, voces, ass, total)

    if musica is None:
        pistas = sorted(DIR_MUSICA.glob("*.mp3")) + sorted(DIR_MUSICA.glob("*.m4a"))
        musica = str(random.choice(pistas)) if pistas else None

    print("🎬 Render final...")
    final = carpeta / "reel.mp4"
    ass_ruta = str(ass.resolve()).replace(":", "\\:").replace("'", "\\'")
    vf = (f"[0:v]ass='{ass_ruta}'[v1];color=c=0xFFD400:s={W}x12:r={FPS}[barra];"
          f"[v1][barra]overlay=x='-w+w*t/{total:.3f}':y=0:shortest=1[v]")
    entradas = ["-i", tmp / "fondo.mp4", "-i", tmp / "voz.wav"]
    if musica:
        entradas += ["-stream_loop", -1, "-i", musica]
        af = (f"[2:a]volume=0.12,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[m];"
              f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        af = "[1:a]anull[a]"
    _ff(*entradas, "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
        "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", 19, "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", 44100, "-movflags", "+faststart", final)

    (carpeta / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"✅ Video listo: {final}  ({total:.1f} s)")
    return str(final)
