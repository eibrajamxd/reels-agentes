"""AGENTE — Narrador: dirige la locución del Reel y genera la voz.

1. `presentar_voces()` graba la misma frase con todas las voces neurales en español y arma una
   página para compararlas antes de elegir (python main.py voces).
2. `dirigir_locucion()` (Claude como director de doblaje) adapta el texto para ser dicho en voz alta
   (números en letra, siglas, pausas con puntuación) y marca ritmo y tono por escena:
   gancho con energía, explicación clara, golpe dramático más lento, cierre cercano.
3. `locutar()` genera el audio de cada escena con esa dirección y devuelve los tiempos por palabra
   (los usan los subtítulos y el Animador para sincronizarse).
"""
import asyncio
import html
import json
import re
from pathlib import Path

from .claude import pedir_json
from .config import CANAL_NOMBRE, DIR_SALIDA, RAIZ, VELOCIDAD_VOZ, VOZ

FRASE_MUESTRA = ("Ahora mismo, el suelo bajo tus pies se está moviendo. "
                 "Y cada punto de magnitud libera unas treinta y dos veces más energía.")

SYSTEM = f"""Eres el director de locución de "{CANAL_NOMBRE}", un canal de Reels en español que explica
cómo funcionan las cosas. Preparas el texto que leerá una voz sintética neural para que suene humana,
con energía y que retenga al espectador.

Para cada escena devuelve:
- `texto_hablado`: la narración lista para leer en voz alta. Respeta el contenido y el orden de las ideas;
  solo ajusta forma: números y símbolos en letras ("32" -> "treinta y dos", "km/h" -> "kilómetros por hora"),
  siglas como se pronuncian, comas y puntos suspensivos para crear pausas dramáticas, frases cortas.
  No agregues información nueva ni quites datos.
- `velocidad`: porcentaje relativo como "+12%", "+0%" o "-6%" (rango -15% a +25%). El gancho suele ir rápido
  y con energía; los momentos de impacto o revelación más lentos; el cierre, natural.
- `tono`: ajuste de tono como "+0Hz", "+2Hz" o "-3Hz" (rango -6Hz a +6Hz). Úsalo con moderación.
- `pausa_despues`: segundos de silencio al final de la escena (0.1 a 0.8). Pausa más larga antes de una revelación.
- `intencion`: 2-5 palabras sobre cómo debe sonar (p. ej. "intriga, urgente", "asombro contenido")."""

SCHEMA = {
    "type": "object",
    "properties": {
        "escenas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texto_hablado": {"type": "string"},
                    "velocidad": {"type": "string"},
                    "tono": {"type": "string"},
                    "pausa_despues": {"type": "number"},
                    "intencion": {"type": "string"},
                },
                "required": ["texto_hablado", "velocidad", "tono", "pausa_despues", "intencion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["escenas"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------- dirección de locución
def _pct(valor: str, defecto: str, lo: int, hi: int, unidad: str) -> str:
    m = re.fullmatch(r"\s*([+-]?\d+)\s*" + re.escape(unidad) + r"\s*", str(valor))
    if not m:
        return defecto
    n = max(lo, min(hi, int(m.group(1))))
    return f"{n:+d}{unidad}"


def dirigir_locucion(guion: dict) -> dict:
    """Añade `locucion` a cada escena (solo si falta). Modifica el guion en sitio."""
    if all(e.get("locucion") for e in guion["escenas"]):
        return guion
    narr = [{"n": i + 1, "narracion": e["narracion"], "titular": e["texto_pantalla"]}
            for i, e in enumerate(guion["escenas"])]
    prompt = (f"Reel: {guion['titulo']}\nVelocidad base de la voz: {VELOCIDAD_VOZ}\n"
              f"Escenas:\n{json.dumps(narr, ensure_ascii=False, indent=1)}\n\n"
              f"Devuelve exactamente {len(narr)} escenas en el mismo orden.")
    r = pedir_json(SYSTEM, prompt, SCHEMA, effort="medium")["escenas"]
    if len(r) != len(guion["escenas"]):
        print("   ! El narrador devolvió otro número de escenas; uso la narración original.")
        return guion
    for e, d in zip(guion["escenas"], r):
        e["locucion"] = {
            "texto_hablado": d["texto_hablado"].strip() or e["narracion"],
            "velocidad": _pct(d["velocidad"], VELOCIDAD_VOZ, -15, 25, "%"),
            "tono": _pct(d["tono"], "+0Hz", -6, 6, "Hz"),
            "pausa_despues": max(0.1, min(0.8, float(d["pausa_despues"]))),
            "intencion": d["intencion"],
        }
    return guion


# ---------------------------------------------------------------- síntesis
async def _tts(texto: str, mp3: Path, voz: str, velocidad: str, tono: str):
    import edge_tts

    com = edge_tts.Communicate(texto, voz, rate=velocidad, pitch=tono, boundary="WordBoundary")
    palabras = []
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                ini = chunk["offset"] / 1e7
                palabras.append((ini, ini + chunk["duration"] / 1e7, chunk["text"]))
    return palabras


def locutar(escena: dict, mp3: Path, voz: str = VOZ) -> tuple[list, float]:
    """Genera el audio de una escena. Devuelve (tiempos_por_palabra, pausa_final)."""
    loc = escena.get("locucion") or {}
    texto = loc.get("texto_hablado") or escena["narracion"]
    palabras = asyncio.run(_tts(texto, mp3, voz, loc.get("velocidad", VELOCIDAD_VOZ), loc.get("tono", "+0Hz")))
    return palabras, loc.get("pausa_despues", 0.25)


# ---------------------------------------------------------------- catálogo de voces
async def _listar():
    import edge_tts

    voces = await edge_tts.list_voices()
    return [v for v in voces if v["Locale"].startswith("es-") or "Multilingual" in v["ShortName"]]


def presentar_voces(frase: str = FRASE_MUESTRA, solo_espanol: bool = False) -> Path:
    """Graba la frase con cada voz y crea salida/voces/index.html para escucharlas y comparar."""
    carpeta = DIR_SALIDA / "voces"
    carpeta.mkdir(parents=True, exist_ok=True)
    voces = asyncio.run(_listar())
    if solo_espanol:
        voces = [v for v in voces if v["Locale"].startswith("es-")]
    voces.sort(key=lambda v: (not v["Locale"].startswith("es-"), v["Locale"], v["Gender"]))
    filas = []
    for v in voces:
        nombre = v["ShortName"]
        archivo = carpeta / f"{nombre}.mp3"
        if not archivo.exists():
            try:
                asyncio.run(_tts(frase, archivo, nombre, VELOCIDAD_VOZ, "+0Hz"))
            except Exception as e:
                print(f"   ! {nombre}: {e}")
                continue
        genero = "Mujer" if v["Gender"] == "Female" else "Hombre"
        estilo = ", ".join(v.get("VoiceTag", {}).get("VoicePersonalities", [])[:3])
        print(f"   🔊 {nombre:<34} {genero:<7} {v['Locale']}")
        filas.append(
            f"<tr><td><b>{html.escape(nombre)}</b><br><small>{html.escape(v['Locale'])} · {genero}"
            f"{' · ' + html.escape(estilo) if estilo else ''}</small></td>"
            f"<td><audio controls preload='none' src='{html.escape(archivo.name)}'></audio></td>"
            f"<td><code>python main.py elegir-voz {html.escape(nombre)}</code></td></tr>")
    pagina = carpeta / "index.html"
    pagina.write_text(f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Voces del canal</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;background:#111;color:#eee}}
table{{width:100%;border-collapse:collapse}}td{{padding:10px;border-bottom:1px solid #333;vertical-align:middle}}
code{{background:#222;padding:4px 6px;border-radius:6px;font-size:12px}}small{{color:#aaa}}</style>
<h1>Elige la voz de {html.escape(CANAL_NOMBRE)}</h1>
<p>Todas leen: <i>“{html.escape(frase)}”</i> a velocidad {html.escape(VELOCIDAD_VOZ)}.
Las voces <b>Multilingual</b> son de otros idiomas pero hablan español; suelen sonar más expresivas,
a veces con un leve acento.</p><table>{''.join(filas)}</table></html>""", encoding="utf-8")
    return pagina


def elegir_voz(nombre: str):
    """Guarda la voz elegida en .env."""
    env = RAIZ / ".env"
    lineas = env.read_text("utf-8").splitlines() if env.exists() else []
    lineas = [l for l in lineas if not l.startswith("VOZ=")] + [f"VOZ={nombre}"]
    env.write_text("\n".join(lineas) + "\n", encoding="utf-8")
