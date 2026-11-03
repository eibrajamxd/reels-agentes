"""AGENTE 3 — Community Manager: copy, hashtags, horarios, publicación y análisis de métricas."""
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .claude import pedir_json
from .config import (CANAL_HANDLE, CANAL_NOMBRE, DIR_DATA, HORARIOS_BASE, IG_ACCESS_TOKEN,
                     IG_API_BASE, IG_API_VERSION, IG_USER_ID, PUBLICACIONES_MAX_POR_DIA,
                     REVISION_MANUAL, ZONA_HORARIA)

TZ = ZoneInfo(ZONA_HORARIA)
COLA = DIR_DATA / "cola.json"
HORARIOS = DIR_DATA / "horarios.json"
METRICAS = DIR_DATA / "metricas.json"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

SYSTEM = f"""Eres el Community Manager de "{CANAL_NOMBRE}" ({CANAL_HANDLE}), una cuenta nueva de
Instagram Reels en español que explica cómo funcionan las cosas. Tu meta es crecer rápido con
alcance orgánico: más reproducciones completas, guardados, compartidos y seguidores.

Al escribir el copy:
- Primera línea = gancho que complementa (no repite) el texto del video; se lee antes del "más".
- 2 a 4 líneas cortas que aporten un dato extra, sin spoilear todo.
- Llamado a guardar/compartir + una pregunta concreta que invite a comentar.
- Español neutro, máximo 2 emojis, nada de clickbait falso.
- 3 a 6 hashtags relevantes (mezcla nicho y medianos), nunca hashtags prohibidos o de spam.

Al elegir horario usa los datos de rendimiento si existen; si no, los horarios base. Evita
publicar dos Reels del mismo tipo de tema seguidos."""

SCHEMA_PUB = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "primer_comentario": {"type": "string"},
        "indice_horario": {"type": "integer"},
        "razon_horario": {"type": "string"},
    },
    "required": ["caption", "hashtags", "primer_comentario", "indice_horario", "razon_horario"],
    "additionalProperties": False,
}

SCHEMA_ANALISIS = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "que_funciona": {"type": "array", "items": {"type": "string"}},
        "que_mejorar": {"type": "array", "items": {"type": "string"}},
        "temas_recomendados": {"type": "array", "items": {"type": "string"}},
        "horarios": {
            "type": "array",
            "description": "Nuevos horarios por día. dia: 0=lunes..6=domingo; horas en HH:MM local.",
            "items": {
                "type": "object",
                "properties": {"dia": {"type": "integer"}, "horas": {"type": "array", "items": {"type": "string"}}},
                "required": ["dia", "horas"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["resumen", "que_funciona", "que_mejorar", "temas_recomendados", "horarios"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------- cola
def leer_cola() -> list[dict]:
    return json.loads(COLA.read_text("utf-8")) if COLA.exists() else []


def guardar_cola(cola: list[dict]):
    COLA.write_text(json.dumps(cola, ensure_ascii=False, indent=2), encoding="utf-8")


def _horarios() -> dict[int, list[str]]:
    if HORARIOS.exists():
        return {int(k): v for k, v in json.loads(HORARIOS.read_text("utf-8")).items()}
    return HORARIOS_BASE


def huecos_libres(n: int = 10, desde: datetime | None = None) -> list[datetime]:
    """Próximos horarios disponibles respetando el máximo de publicaciones por día."""
    ahora = desde or datetime.now(TZ)
    ocupados: dict[str, int] = {}
    for item in leer_cola():
        if item["estado"] in ("programado", "pendiente_revision"):
            dia = item["publicar_en"][:10]
            ocupados[dia] = ocupados.get(dia, 0) + 1
    res = []
    for delta in range(0, 30):
        dia = (ahora + timedelta(days=delta)).date()
        if ocupados.get(dia.isoformat(), 0) >= PUBLICACIONES_MAX_POR_DIA:
            continue
        for hora in _horarios().get(dia.weekday(), []):
            hh, mm = map(int, hora.split(":"))
            dt = datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=TZ)
            if dt > ahora + timedelta(minutes=30):
                res.append(dt)
        if len(res) >= n:
            break
    return res[:n]


def preparar_publicacion(guion: dict, video: str) -> dict:
    """El CM escribe el copy, elige horario y mete el Reel en la cola."""
    huecos = huecos_libres()
    opciones = "\n".join(f"{i}: {DIAS[h.weekday()]} {h:%Y-%m-%d %H:%M}" for i, h in enumerate(huecos))
    metricas = METRICAS.read_text("utf-8")[:6000] if METRICAS.exists() else "Aún no hay datos (cuenta nueva)."
    recientes = [f"{c['publicar_en'][:10]} - {c['tema']}" for c in leer_cola()[-6:]]
    prompt = (
        f"Guion del Reel:\n{json.dumps(guion, ensure_ascii=False)}\n\n"
        f"Publicaciones recientes/programadas: {recientes}\n\n"
        f"Métricas recientes:\n{metricas}\n\n"
        f"Horarios disponibles (zona {ZONA_HORARIA}):\n{opciones}\n\n"
        "Escribe el copy y elige el índice del mejor horario."
    )
    r = pedir_json(SYSTEM, prompt, SCHEMA_PUB, effort="medium")
    idx = min(max(r["indice_horario"], 0), len(huecos) - 1)
    tags = " ".join(h if h.startswith("#") else f"#{h}" for h in r["hashtags"])
    item = {
        "id": uuid.uuid4().hex[:8],
        "tema": guion.get("tema", guion["titulo"]),
        "video": video,
        "caption": f"{r['caption'].strip()}\n\n{tags}",
        "primer_comentario": r["primer_comentario"],
        "publicar_en": huecos[idx].isoformat(),
        "razon_horario": r["razon_horario"],
        "datos_a_verificar": guion.get("datos_a_verificar", []),
        "estado": "pendiente_revision" if REVISION_MANUAL else "programado",
    }
    cola = leer_cola()
    cola.append(item)
    guardar_cola(cola)
    return item


# ---------------------------------------------------------------- Instagram Graph API
def _url(ruta: str) -> str:
    return f"{IG_API_BASE}/{IG_API_VERSION}/{ruta}"


def _ig(metodo: str, ruta: str, **params) -> dict:
    params["access_token"] = IG_ACCESS_TOKEN
    r = requests.request(metodo, _url(ruta), params=params, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram {r.status_code}: {r.text}")
    return r.json()


def publicar_reel(video: str, caption: str, primer_comentario: str = "") -> str:
    """Sube el MP4 local con carga reanudable (no necesita hosting público) y lo publica."""
    if not (IG_ACCESS_TOKEN and IG_USER_ID):
        raise RuntimeError("Faltan IG_ACCESS_TOKEN / IG_USER_ID en .env")
    cont = _ig("POST", f"{IG_USER_ID}/media", media_type="REELS", upload_type="resumable",
               caption=caption, share_to_feed="true", thumb_offset=800)
    cid = cont["id"]
    datos = Path(video).read_bytes()
    up = requests.post(
        f"https://rupload.facebook.com/ig-api-upload/{IG_API_VERSION}/{cid}",
        headers={"Authorization": f"OAuth {IG_ACCESS_TOKEN}", "offset": "0", "file_size": str(len(datos))},
        data=datos, timeout=600,
    )
    if not up.ok:
        raise RuntimeError(f"Subida falló {up.status_code}: {up.text}")
    for _ in range(60):  # hasta ~10 min de procesamiento
        estado = _ig("GET", cid, fields="status_code,status").get("status_code")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el video: {estado}")
        time.sleep(10)
    else:
        raise RuntimeError("Tiempo de espera agotado procesando el video")
    media_id = _ig("POST", f"{IG_USER_ID}/media_publish", creation_id=cid)["id"]
    if primer_comentario:
        try:
            _ig("POST", f"{media_id}/comments", message=primer_comentario)
        except RuntimeError as e:
            print(f"   ! No se pudo dejar el primer comentario: {e}")
    return media_id


def publicar_pendientes() -> int:
    """Publica todo lo programado cuya hora ya llegó. Pensado para cron cada 5-10 min."""
    cola, n = leer_cola(), 0
    ahora = datetime.now(TZ)
    for item in cola:
        if item["estado"] != "programado" or datetime.fromisoformat(item["publicar_en"]) > ahora:
            continue
        print(f"📤 Publicando '{item['tema']}'...")
        try:
            item["media_id"] = publicar_reel(item["video"], item["caption"], item.get("primer_comentario", ""))
            item["estado"], item["publicado_en"] = "publicado", datetime.now(TZ).isoformat()
            n += 1
            print(f"   ✅ Publicado (media {item['media_id']})")
        except Exception as e:  # se guarda el error y se reintenta en la próxima pasada
            item["intentos"] = item.get("intentos", 0) + 1
            item["error"] = str(e)
            if item["intentos"] >= 3:
                item["estado"] = "error"
            print(f"   ❌ {e}")
        guardar_cola(cola)
    return n


# ---------------------------------------------------------------- análisis
def recolectar_metricas(limite: int = 25) -> list[dict]:
    medios = _ig("GET", f"{IG_USER_ID}/media", limit=limite,
                 fields="id,caption,media_product_type,timestamp,like_count,comments_count,permalink")["data"]
    res = []
    for m in medios:
        if m.get("media_product_type") != "REELS":
            continue
        for metricas in ("reach,views,saved,shares,total_interactions,ig_reels_avg_watch_time",
                         "reach,saved,shares,total_interactions"):
            try:
                ins = _ig("GET", f"{m['id']}/insights", metric=metricas)
                m["insights"] = {d["name"]: d["values"][0]["value"] for d in ins["data"]}
                break
            except RuntimeError as e:
                m["insights_error"] = str(e)[:200]
        dt = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")).astimezone(TZ)
        m["hora_local"] = f"{DIAS[dt.weekday()]} {dt:%H:%M}"
        m["caption"] = (m.get("caption") or "")[:120]
        res.append(m)
    try:
        cuenta = _ig("GET", IG_USER_ID, fields="followers_count,media_count")
    except RuntimeError:
        cuenta = {}
    METRICAS.write_text(json.dumps({"cuenta": cuenta, "reels": res}, ensure_ascii=False, indent=2), "utf-8")
    return res


def analizar() -> dict:
    """Recolecta métricas, pide al CM un diagnóstico y actualiza los horarios de publicación."""
    reels = recolectar_metricas()
    if len(reels) < 5:
        print(f"ℹ️  Solo hay {len(reels)} Reels; con menos de 5 se mantienen los horarios base.")
    prompt = (
        f"Métricas de los últimos Reels (zona {ZONA_HORARIA}):\n{METRICAS.read_text('utf-8')[:20000]}\n\n"
        f"Horarios actuales: {json.dumps(_horarios())}\n\n"
        "Diagnostica qué funciona, qué mejorar, sugiere 5 temas y propone horarios por día "
        "(1 a 2 horas por día). Si hay menos de 5 Reels, devuelve los horarios actuales sin cambios."
    )
    r = pedir_json(SYSTEM, prompt, SCHEMA_ANALISIS, effort="high")
    if len(reels) >= 5 and r["horarios"]:
        nuevos = {h["dia"]: h["horas"] for h in r["horarios"] if 0 <= h["dia"] <= 6 and h["horas"]}
        HORARIOS.write_text(json.dumps(nuevos, indent=2), "utf-8")
    (DIR_DATA / "ultimo_analisis.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), "utf-8")
    return r
