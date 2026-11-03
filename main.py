"""Coordinador: une a los 5 agentes (Guionista -> Narrador -> Animador -> Productor -> Community Manager).

Uso rápido:
  python main.py crear "cómo funcionan los temblores y terremotos"
  python main.py crear --guion guiones/como-funcionan-los-temblores-y-terremotos.json
  python main.py voces             # escuchar todas las voces antes de elegir
  python main.py elegir-voz es-MX-JorgeNeural
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

from agentes import community_manager as cm
from agentes import guionista, narrador, productor


def crear(tema: str | None, guion_path: str | None, sin_voz: bool, sin_publicar: bool,
          sin_animacion: bool = False):
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
    item = cm.preparar_publicacion(guion, video)
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
    ev = sub.add_parser("elegir-voz"); ev.add_argument("nombre")
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
        pagina = narrador.presentar_voces(args.frase, args.solo_espanol)
        print(f"\n✅ Abre esta página para escucharlas y comparar:\n   {pagina}\n"
              "Luego elige con: python main.py elegir-voz <nombre>")
    elif args.cmd == "elegir-voz":
        narrador.elegir_voz(args.nombre)
        print(f"✅ Voz del canal: {args.nombre} (guardada en .env)")
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
