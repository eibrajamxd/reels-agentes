"""Coordinador: une a los 5 agentes (Guionista -> Narrador -> Animador -> Productor -> Community Manager).

Uso rápido:
  python main.py crear "cómo funcionan los temblores y terremotos"
  python main.py crear --guion guiones/como-funcionan-los-temblores-y-terremotos.json
  python main.py voces             # escuchar todas las voces antes de elegir
  python main.py elegir-voz es-MX-JorgeNeural
  python main.py semana guiones/a.json "tema 2" "tema 3" --total 5   # el CM planifica y produce la semana
  python main.py priorizar          # el CM ordena los guiones sin publicar y elige el primero
  python main.py ideas 10          # el guionista propone temas
  python main.py auto 3            # produce y programa los 3 siguientes temas de ideas.json
  python main.py cola              # ver calendario
  python main.py aprobar <id>      # aprobar un Reel en revisión
  python main.py publicar          # publica lo que ya toca (pon esto en cron)
  python main.py vigilar           # bucle: publica a su hora, sin cron
  python main.py analizar          # métricas -> diagnóstico -> nuevos horarios
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from agentes import community_manager as cm
from agentes import guionista, narrador, productor


def buscar_guion(tema_o_ruta: str) -> str | None:
    """Acepta la ruta de un guion o un tema; si ya existe un guion de ese tema, lo reutiliza."""
    if tema_o_ruta.endswith(".json") and Path(tema_o_ruta).exists():
        return tema_o_ruta
    clave = guionista.slug(tema_o_ruta)
    for ruta in sorted(Path("guiones").glob("*.json")):
        tema = json.loads(ruta.read_text("utf-8")).get("tema", "")
        if clave in (ruta.stem, guionista.slug(tema)):
            return str(ruta)
    return None


def semana(temas: list[str], total: int, solo_plan: bool):
    fijos = []
    for t in temas:
        ruta = buscar_guion(t)
        fijos.append(json.loads(Path(ruta).read_text("utf-8"))["tema"] if ruta else t)
    print("📅 Community Manager planificando la semana...")
    plan = cm.planificar_semana(fijos, total)
    print(f"\nEstrategia: {plan['estrategia']}\n")
    for d in plan["plan"]:
        dt = datetime.fromisoformat(d["publicar_en"])
        print(f"  Día {d['dia']}  {cm.DIAS[dt.weekday()]:<9} {dt:%d/%m %H:%M}  {d['tema']}")
        print(f"         {d['motivo']}")
    print("\n(Plan guardado en data/plan_semana.json)")
    if solo_plan:
        return
    for d in plan["plan"]:
        print(f"\n==================== Día {d['dia']}: {d['tema']} ====================")
        ruta = buscar_guion(d["tema"])
        crear(d["tema"], ruta, False, False, horario=datetime.fromisoformat(d["publicar_en"]))


def crear(tema: str | None, guion_path: str | None, sin_voz: bool, sin_publicar: bool,
          sin_animacion: bool = False, horario: datetime | None = None):
    if guion_path:
        guion = json.loads(open(guion_path, encoding="utf-8").read())
        print(f"📄 Usando guion existente: {guion['titulo']}")
    else:
        print(f"✍️  Guionista escribiendo: {tema}")
        guion, guion_path = guionista.escribir_guion(tema)
        print(f"   Guion guardado en {guion_path}")
    print("\n🔎 Datos a verificar antes de publicar:")
    for d in guion.get("datos_a_verificar", []):
        print(f"   • {d}")
    video = productor.producir_video(guion, con_voz=not sin_voz, animar=not sin_animacion,
                                     ruta_guion=guion_path)
    if sin_publicar:
        return
    print("\n📣 Community Manager preparando la publicación...")
    item = cm.preparar_publicacion(guion, video, horario)
    _mostrar(item)


def _mostrar(item):
    dt = datetime.fromisoformat(item["publicar_en"])
    print(f"\n[{item['id']}] {item['estado'].upper()} — {cm.DIAS[dt.weekday()]} {dt:%d/%m %H:%M}  ·  {item['tema']}")
    print(f"   Por qué: {item.get('razon_horario', '')}")
    print("   Caption:\n      " + item["caption"].replace("\n", "\n      "))
    if item["estado"] == "pendiente_revision":
        print(f"   👉 Revisa el video ({item['video']}) y aprueba con: python main.py aprobar {item['id']}")


def main():
    p = argparse.ArgumentParser(description="Fábrica de Reels con agentes")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crear")
    c.add_argument("tema", nargs="?")
    c.add_argument("--guion", help="usar un guion JSON ya escrito")
    c.add_argument("--sin-voz", action="store_true", help="sin narración (prueba offline)")
    c.add_argument("--sin-publicar", action="store_true", help="solo generar el video")
    c.add_argument("--sin-animacion", action="store_true", help="solo video de stock / fondos")
    vo = sub.add_parser("voces"); vo.add_argument("--frase", default=narrador.FRASE_MUESTRA)
    vo.add_argument("--solo-espanol", action="store_true")
    vo.add_argument("--pais", help="código de país, p. ej. CL para voces de Chile")
    ev = sub.add_parser("elegir-voz"); ev.add_argument("nombre")
    se = sub.add_parser("semana", help="el CM planifica la semana y produce cada Reel")
    se.add_argument("temas", nargs="*", help="temas fijos en orden (texto o ruta de guion)")
    se.add_argument("--total", type=int, default=5, help="días a planificar")
    se.add_argument("--solo-plan", action="store_true", help="solo mostrar el calendario")
    pr = sub.add_parser("priorizar", help="el CM decide qué guion publicar primero")
    pr.add_argument("guiones", nargs="*", help="rutas de guiones (por defecto, todos los no publicados)")
    i = sub.add_parser("ideas"); i.add_argument("n", type=int, nargs="?", default=10)
    a = sub.add_parser("auto"); a.add_argument("n", type=int, nargs="?", default=1)
    sub.add_parser("cola")
    ap = sub.add_parser("aprobar"); ap.add_argument("id")
    sub.add_parser("publicar")
    v = sub.add_parser("vigilar"); v.add_argument("--cada", type=int, default=300, help="segundos")
    sub.add_parser("analizar")
    args = p.parse_args()

    if args.cmd == "crear":
        if not (args.tema or args.guion):
            sys.exit("Indica un tema o --guion")
        crear(args.tema, args.guion, args.sin_voz, args.sin_publicar, args.sin_animacion)
    elif args.cmd == "voces":
        print("🎧 Grabando la misma frase con cada voz...")
        pagina = narrador.presentar_voces(args.frase, args.solo_espanol, args.pais)
        print(f"\n✅ Abre esta página para escucharlas y comparar:\n   {pagina}\n"
              "Luego elige con: python main.py elegir-voz <nombre>")
    elif args.cmd == "elegir-voz":
        narrador.elegir_voz(args.nombre)
        print(f"✅ Voz del canal: {args.nombre} (guardada en .env)")
    elif args.cmd == "semana":
        semana(args.temas, args.total, args.solo_plan)
    elif args.cmd == "priorizar":
        rutas = args.guiones
        if not rutas:
            publicados = {guionista.slug(c["tema"]) for c in cm.leer_cola() if c["estado"] == "publicado"}
            hoy = datetime.now(cm.TZ).date().isoformat()
            rutas, reservados = [], []
            for r in sorted(Path("guiones").glob("*.json")):
                g = json.loads(r.read_text("utf-8"))
                if guionista.slug(g["tema"]) in publicados:
                    continue
                if g.get("publicar_desde", "") > hoy:  # guion guardado para más adelante
                    reservados.append(f"{r.name} (desde {g['publicar_desde']})")
                    continue
                rutas.append(str(r))
            if reservados:
                print("📦 Guardados para más adelante (no se evalúan): " + ", ".join(reservados))
        print(f"📊 Community Manager evaluando {len(rutas)} guiones...")
        r = cm.priorizar(rutas)
        for k, g in enumerate(r["ranking"], 1):
            print(f"\n{k}. [{g['puntaje']}/100] {g['archivo']}")
            print(f"   Gancho: {g['fuerza_del_gancho']}\n   Por qué: {g['motivo']}\n   Mejora: {g['mejora_sugerida']}")
        print(f"\n🥇 Publicar primero: {r['primero']}\n   {r['por_que_primero']}")
    elif args.cmd == "ideas":
        for k, idea in enumerate(guionista.proponer_ideas(args.n), 1):
            print(f"{k:>2}. {idea['tema']}\n    Gancho: {idea['gancho']}")
    elif args.cmd == "auto":
        for _ in range(args.n):
            tema = guionista.siguiente_idea()
            if not tema:
                guionista.proponer_ideas(10)
                tema = guionista.siguiente_idea()
            crear(tema, None, False, False)
    elif args.cmd == "cola":
        cola = sorted(cm.leer_cola(), key=lambda x: x["publicar_en"])
        if not cola:
            print("La cola está vacía.")
        for item in cola:
            dt = datetime.fromisoformat(item["publicar_en"])
            print(f"[{item['id']}] {item['estado']:<19} {cm.DIAS[dt.weekday()]:<9} {dt:%d/%m %H:%M}  {item['tema']}")
    elif args.cmd == "aprobar":
        cola = cm.leer_cola()
        for item in cola:
            if item["id"] == args.id:
                item["estado"] = "programado"
                cm.guardar_cola(cola)
                print(f"✅ Aprobado. Se publicará el {item['publicar_en'][:16].replace('T', ' ')}")
                break
        else:
            sys.exit("No encontré ese id")
    elif args.cmd == "publicar":
        print(f"Publicados: {cm.publicar_pendientes()}")
    elif args.cmd == "vigilar":
        print(f"👀 Vigilando la cola cada {args.cada}s (Ctrl+C para salir)")
        while True:
            cm.publicar_pendientes()
            time.sleep(args.cada)
    elif args.cmd == "analizar":
        r = cm.analizar()
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
