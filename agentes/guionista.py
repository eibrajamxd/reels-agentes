"""AGENTE 1 — Guionista: convierte un tema en un guion de Reel viral y verificable."""
import json
import re
import unicodedata

from .claude import pedir_json
from .config import CANAL_NOMBRE, DIR_DATA, DIR_GUIONES

SYSTEM = f"""Eres el guionista principal de "{CANAL_NOMBRE}", un canal de Instagram Reels en
español que explica cómo funcionan las cosas (ciencia, tecnología, cuerpo humano, naturaleza,
ingeniería cotidiana). Tu trabajo es escribir guiones de 30 a 50 segundos que la gente vea
completos, guarde y comparta.

Reglas de retención:
- La primera escena es el GANCHO: una frase de menos de 12 palabras que genere curiosidad o
  rompa una creencia. Nada de "Hola" ni "En este video". Se entiende sin sonido.
- Una sola idea por escena, frases cortas, lenguaje de conversación en español neutro.
- Abre una pregunta al inicio y respóndela al final (bucle abierto) para que vean hasta el final.
- Usa comparaciones cotidianas ("se mueve lo que crecen tus uñas").
- Total de narración: 100 a 140 palabras, entre 6 y 9 escenas.
- La última escena invita a seguir la cuenta y hace una pregunta para comentarios.

Reglas de exactitud (son innegociables):
- Solo datos científicamente aceptados. Si una cifra es aproximada, dilo ("unas", "cerca de").
- Simplifica sin decir cosas falsas.
- Enumera en `datos_a_verificar` cada cifra o afirmación concreta para revisión humana.

Para cada escena:
- `narracion`: lo que dice la voz en off.
- `texto_pantalla`: 2 a 5 palabras en mayúsculas que resumen la escena (titular visual).
- `busqueda_video`: 2 a 4 palabras EN INGLÉS para buscar video de stock vertical en Pexels
  (cosas filmables y concretas: "cracked earth", "city skyline night", "seismograph").
- `color`: color hexadecimal de acento BRILLANTE (se usa de fondo del titular con texto negro
  y para resaltar subtítulos), p. ej. #FFD400, #FF6B35, #4DD0E1, #7CFC00."""

SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "escenas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narracion": {"type": "string"},
                    "texto_pantalla": {"type": "string"},
                    "busqueda_video": {"type": "string"},
                    "color": {"type": "string"},
                },
                "required": ["narracion", "texto_pantalla", "busqueda_video", "color"],
                "additionalProperties": False,
            },
        },
        "datos_a_verificar": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titulo", "escenas", "datos_a_verificar"],
    "additionalProperties": False,
}

SCHEMA_IDEAS = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tema": {"type": "string"},
                    "gancho": {"type": "string"},
                    "por_que_funciona": {"type": "string"},
                },
                "required": ["tema", "gancho", "por_que_funciona"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ideas"],
    "additionalProperties": False,
}


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "reel"


def escribir_guion(tema: str) -> tuple[dict, str]:
    guion = pedir_json(SYSTEM, f"Escribe el guion del Reel sobre: {tema}", SCHEMA, effort="high")
    guion["tema"] = tema
    ruta = DIR_GUIONES / f"{slug(tema)}.json"
    ruta.write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    return guion, str(ruta)


def proponer_ideas(n: int = 10) -> list[dict]:
    """Propone temas nuevos evitando los que ya existen."""
    hechos = [json.loads(p.read_text("utf-8")).get("tema", p.stem) for p in DIR_GUIONES.glob("*.json")]
    ruta_ideas = DIR_DATA / "ideas.json"
    previas = json.loads(ruta_ideas.read_text("utf-8")) if ruta_ideas.exists() else []
    prompt = (
        f"Propón {n} temas nuevos de 'cómo funciona...' con alto potencial viral para Reels. "
        "Mezcla fenómenos naturales, objetos cotidianos, cuerpo humano y tecnología. "
        f"No repitas estos temas: {json.dumps(hechos + [i['tema'] for i in previas], ensure_ascii=False)}"
    )
    ideas = pedir_json(SYSTEM, prompt, SCHEMA_IDEAS, effort="medium")["ideas"]
    ruta_ideas.write_text(json.dumps(previas + ideas, ensure_ascii=False, indent=2), encoding="utf-8")
    return ideas


def siguiente_idea() -> str | None:
    ruta_ideas = DIR_DATA / "ideas.json"
    if not ruta_ideas.exists():
        return None
    ideas = json.loads(ruta_ideas.read_text("utf-8"))
    if not ideas:
        return None
    idea = ideas.pop(0)
    ruta_ideas.write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
    return idea["tema"]
