import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

RAIZ = Path(__file__).resolve().parent.parent
DIR_GUIONES = RAIZ / "guiones"
DIR_SALIDA = RAIZ / "salida"
DIR_DATA = RAIZ / "data"
DIR_MUSICA = RAIZ / "musica"
for d in (DIR_GUIONES, DIR_SALIDA, DIR_DATA, DIR_MUSICA):
    d.mkdir(exist_ok=True)

MODELO = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
# claude-code = usa Claude Code con tu plan de claude.ai (sin costo extra) | api = API de pago por uso
MOTOR_IA = os.getenv("MOTOR_IA", "claude-code").lower()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_API_BASE = os.getenv("IG_API_BASE", "https://graph.instagram.com").rstrip("/")
IG_API_VERSION = os.getenv("IG_API_VERSION", "v23.0")

CANAL_NOMBRE = os.getenv("CANAL_NOMBRE", "¿Cómo Funciona?")
CANAL_HANDLE = os.getenv("CANAL_HANDLE", "@como_funcionatv")
PUBLICO = os.getenv("PUBLICO", "Chile")
ZONA_HORARIA = os.getenv("ZONA_HORARIA", "America/Santiago")
VOZ = os.getenv("VOZ", "es-MX-JorgeNeural")  # voz elegida del canal; cámbiala con `voces` + `elegir-voz`
VELOCIDAD_VOZ = os.getenv("VELOCIDAD_VOZ", "+8%")
PUBLICACIONES_MAX_POR_DIA = int(os.getenv("PUBLICACIONES_MAX_POR_DIA", "1"))
# animacion = todas las escenas animadas | mixto = alterna animación y video de stock | broll = solo stock
MODO_VISUAL = os.getenv("MODO_VISUAL", "animacion")
# pelicula = acabado de ilustración a mano (skill procedural-film) | plano = gráficos planos
ESTILO_ANIMACION = os.getenv("ESTILO_ANIMACION", "pelicula")
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "")  # solo si Playwright no encuentra su navegador
REVISION_MANUAL = os.getenv("REVISION_MANUAL", "true").lower() == "true"
# manual = el sistema deja el video y el texto listos en tu computador y tú lo subes desde la app
# automatica = el vigilante lo publica solo en Instagram a la hora elegida
MODO_PUBLICACION = os.getenv("MODO_PUBLICACION", "manual").lower()
CARPETA_LISTOS = Path(os.path.expanduser(os.getenv("CARPETA_LISTOS", "~/Desktop/Reels listos")))

# Horarios iniciales (hora de Chile) para Reels: colación (13:00–14:30) y noche (20:30–22:00),
# que es cuando más se usa Instagram en Chile. Son un punto de partida: `analizar` los reemplaza con datos reales.
HORARIOS_BASE = {
    0: ["13:30", "21:00"],  # lunes
    1: ["13:30", "21:00"],
    2: ["13:30", "21:00"],
    3: ["13:30", "21:00"],
    4: ["13:30", "20:30"],
    5: ["11:30", "20:30"],  # sábado
    6: ["12:00", "21:00"],  # domingo
}
