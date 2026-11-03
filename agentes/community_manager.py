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
                     IG_API_BASE, IG_API_VERSION, IG_USER_ID, PUBLICACIONES_MAX_POR_DIA, PUBLICO,
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
- El público es de {PUBLICO}: español claro y cercano para {PUBLICO}, máximo 2 emojis, nada de clickbait falso.
- Incluye 1 o 2 hashtags locales de {PUBLICO} cuando el tema lo permita.
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


def dias_libres(n_dias: int, desde: datetime | None = None) -> list[list[datetime]]:
    """Próximos `n_dias` días con espacio para publicar; cada uno con sus horarios candidatos."""
    ahora = desde or datetime.now(TZ)
    ocupados: dict[str, int] = {}
    for item in leer_cola():
        if item["estado"] in ("programado", "pendiente_revision"):
            dia = item["publicar_en"][:10]
            ocupados[dia] = ocupados.get(dia, 0) + 1
    res = []
    for delta in range(0, 60):
        dia = (ahora + timedelta(days=delta)).date()
        if ocupados.get(dia.isoformat(), 0) >= PUBLICACIONES_MAX_POR_DIA:
            continue
        horas = []
        for hora in _horarios().get(dia.weekday(), []):
            hh, mm = map(int, hora.split(":"))
            dt = datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=TZ)
            if dt > ahora + timedelta(minutes=30):
                horas.append(dt)
        if horas:
            res.append(horas)
        if len(res) >= n_dias:
            break
    return res


def huecos_libres(n: int = 10, desde: datetime | None = None) -> list[datetime]:
    """Próximos horarios disponibles respetando el máximo de publicaciones por día."""
    return [h for dia in dias_libres(n, desde) for h in dia][:n]


SCHEMA_SEMANA = {
    "type": "object",
    "properties": {
        "dias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tema": {"type": "string"},
                    "indice_horario": {"type": "integer"},
                    "motivo": {"type": "string"},
                },
                "required": ["tema", "indice_horario", "motivo"],
                "additionalProperties": False,
            },
        },
        "estrategia": {"type": "string"},
    },
    "required": ["dias", "estrategia"],
    "additionalProperties": False,
}


def planificar_semana(temas_fijos: list[str], total: int) -> dict:
    """El CM arma el calendario: respeta el orden de los temas fijos, propone los que faltan
    y elige la mejor hora de cada día. Guarda el plan en data/plan_semana.json."""
    dias = dias_libres(total)
    if not dias:
        raise RuntimeError("No hay días libres en el calendario.")
    total = len(dias)
    opciones = "\n".join(
        f"Día {i + 1} ({DIAS[d[0].weekday()]} {d[0]:%d/%m}): "
        + ", ".join(f"{j}={h:%H:%M}" for j, h in enumerate(d))
        for i, d in enumerate(dias))
    from .config import DIR_GUIONES
    hechos = [json.loads(p.read_text("utf-8")).get("tema", p.stem) for p in DIR_GUIONES.glob("*.json")]
    metricas = METRICAS.read_text("utf-8")[:6000] if METRICAS.exists() else "Aún no hay datos (cuenta nueva)."
    prompt = (
        f"Planifica {total} Reels, uno por día, en este orden de días:\n{opciones}\n\n"
        f"Los primeros {len(temas_fijos)} días ya tienen tema fijo, en este orden exacto: "
        f"{json.dumps(temas_fijos, ensure_ascii=False)}. Cópialos tal cual en `tema`.\n"
        f"Propón tú los temas de los días restantes (estilo 'cómo funciona...'), que hagan serie con los "
        f"anteriores y alternen categorías. Evita estos temas ya hechos: {json.dumps(hechos, ensure_ascii=False)}\n"
        f"Para cada día elige `indice_horario` (el número antes del '=') con la mejor hora.\n"
        f"Métricas: {metricas}\nDevuelve exactamente {total} días en orden."
    )
    r = pedir_json(SYSTEM, prompt, SCHEMA_SEMANA, effort="medium")
    plan = []
    for i, d in enumerate(dias):
        item = r["dias"][i] if i < len(r["dias"]) else {"tema": "", "indice_horario": 0, "motivo": ""}
        tema = temas_fijos[i] if i < len(temas_fijos) else item["tema"]
        idx = min(max(item["indice_horario"], 0), len(d) - 1)
        plan.append({"dia": i + 1, "tema": tema, "publicar_en": d[idx].isoformat(), "motivo": item["motivo"]})
    resultado = {"estrategia": r["estrategia"], "plan": plan}
    (DIR_DATA / "plan_semana.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), "utf-8")
    return resultado


SCHEMA_PRIORIDAD = {
    "type": "object",
    "properties": {
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "archivo": {"type": "string"},
                    "puntaje": {"type": "integer", "description": "0 a 100, potencial de alcance"},
                    "fuerza_del_gancho": {"type": "string"},
                    "motivo": {"type": "string"},
                    "mejora_sugerida": {"type": "string"},
                },
                "required": ["archivo", "puntaje", "fuerza_del_gancho", "motivo", "mejora_sugerida"],
                "additionalProperties": False,
            },
        },
        "primero": {"type": "string", "description": "archivo del Reel que conviene publicar primero"},
        "por_que_primero": {"type": "string"},
    },
    "required": ["ranking", "primero", "por_que_primero"],
    "additionalProperties": False,
}


def priorizar(rutas: list[str]) -> dict:
    """El CM compara guiones y decide cuál publicar primero (y en qué orden los demás)."""
    guiones = []
    for r in rutas:
        g = json.loads(Path(r).read_text("utf-8"))
        guiones.append({"archivo": r, "titulo": g["titulo"],
                        "narracion": [e["narracion"] for e in g["escenas"]],
                        "titulares": [e["texto_pantalla"] for e in g["escenas"]]})
    publicados = [c["tema"] for c in leer_cola() if c["estado"] == "publicado"]
    metricas = METRICAS.read_text("utf-8")[:6000] if METRICAS.exists() else "Aún no hay datos (cuenta nueva)."
    prompt = (
        f"Guiones candidatos:\n{json.dumps(guiones, ensure_ascii=False, indent=1)}\n\n"
        f"Ya publicados: {json.dumps(publicados, ensure_ascii=False)}\nMétricas: {metricas}\n\n"
        "Evalúa cada guion como Reel para una cuenta nueva en crecimiento: fuerza del gancho en los primeros "
        "2 segundos, curiosidad universal (¿le pasa a todo el mundo?), probabilidad de que lo guarden y lo "
        "compartan, y potencial de comentarios. Ordénalos de mayor a menor puntaje y elige cuál publicar primero. "
        "Usa en `archivo` exactamente la ruta recibida."
    )
    r = pedir_json(SYSTEM, prompt, SCHEMA_PRIORIDAD, effort="high")
    r["ranking"].sort(key=lambda x: -x["puntaje"])
    (DIR_DATA / "priorizacion.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), "utf-8")
    return r


def preparar_publicacion(guion: dict, video: str, horario: datetime | None = None) -> dict:
    """El CM escribe el copy, elige horario (o usa el ya planificado) y mete el Reel en la cola."""
    huecos = [horario] if horario else huecos_libres()
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
    # Instagram devuelve la URL de subida en "uri"; se usa tal cual (si falta, se arma con la versión configurada).
    up = requests.post(
        cont.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{IG_API_VERSION}/{cid}",
        headers={"Authorization": f"OAuth {IG_ACCESS_TOKEN}", "offset": "0", "file_size": str(len(datos))},
        data=datos, timeout=600,
    )
    if not up.ok:
        raise RuntimeError(f"Subida falló {up.status_code}: {up.text}")
    for _ in range(60):  # hasta ~10 min de procesamiento
        info = _ig("GET", cid, fields="status_code,status")
        estado = info.get("status_code")
        if estado == "FINISHED":
            break
        if estado in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el video: {estado} — {info.get('status', '')}")
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
