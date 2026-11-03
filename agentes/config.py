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
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_API_BASE = os.getenv("IG_API_BASE", "https://graph.instagram.com").rstrip("/")
IG_API_VERSION = os.getenv("IG_API_VERSION", "v23.0")

CANAL_NOMBRE = os.getenv("CANAL_NOMBRE", "Así Funciona")
CANAL_HANDLE = os.getenv("CANAL_HANDLE", "@asifunciona")
ZONA_HORARIA = os.getenv("ZONA_HORARIA", "America/Mexico_City")
VOZ = os.getenv("VOZ", "")  # se elige con `python main.py voces` + `elegir-voz`
VELOCIDAD_VOZ = os.getenv("VELOCIDAD_VOZ", "+8%")
PUBLICACIONES_MAX_POR_DIA = int(os.getenv("PUBLICACIONES_MAX_POR_DIA", "1"))
# animacion = todas las escenas animadas | mixto = alterna animación y video de stock | broll = solo stock
MODO_VISUAL = os.getenv("MODO_VISUAL", "animacion")
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "")  # solo si Playwright no encuentra su navegador
REVISION_MANUAL = os.getenv("REVISION_MANUAL", "true").lower() == "true"

# Horarios iniciales (hora local) para Reels con audiencia hispana.
# Son un punto de partida: el comando `analizar` los reemplaza con datos reales.
HORARIOS_BASE = {
    0: ["13:00", "19:30"],  # lunes
    1: ["13:00", "19:30"],
    2: ["13:00", "20:00"],
    3: ["13:00", "19:30"],
    4: ["12:30", "18:00"],
    5: ["10:30", "18:30"],  # sábado
    6: ["11:00", "19:00"],  # domingo
}
