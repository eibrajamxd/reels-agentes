# Fábrica de Reels "¿Cómo Funciona?" (@como_funcionatv): 5 agentes con Claude

Sistema que produce y publica Reels educativos del tipo *"cómo funciona…"* en Instagram.

```
 tema ─► 🧠 GUIONISTA ─► 🎙️ NARRADOR ─► ✨ ANIMADOR ─► 🎬 PRODUCTOR ─► 📣 COMMUNITY MANAGER ─► Instagram
         guion viral     dirige la       animación por   montaje,       copy, hashtags, horario,
         + datos a       locución y      escena, sincro- subtítulos,    publica, mide y ajusta
         verificar       graba la voz    nizada con voz  música         horarios
```

| Agente | Archivo | Qué hace |
|---|---|---|
| Guionista | `agentes/guionista.py` | Escribe guiones de 30–60 s con gancho en los primeros 2 s, bucle abierto, 1 idea por escena y una lista de **datos a verificar**. También propone temas nuevos (`ideas`). |
| Narrador | `agentes/narrador.py` | Te **presenta todas las voces** en español (y las multilingües) leyendo la misma frase para que elijas la del canal. En cada video actúa como director de locución: adapta el texto para decirlo en voz alta (números en letra, pausas dramáticas) y marca velocidad, tono y silencios por escena (gancho con energía, revelación más lenta). Graba la voz con tiempos por palabra para subtítulos y animación. |
| Animador | `agentes/animador.py` + `anim_lib.js` | Programa una animación explicativa para cada escena (cortes transversales, flechas de fuerza, contadores, ondas, comparaciones) que aparece **justo cuando la voz dice cada palabra**. La prueba en un navegador sin ventana; si falla, corrige el error. Luego un **director** (Claude con visión) mira 4 fotogramas reales y aprueba o pide cambios (hasta 3 intentos). Lo aprobado queda guardado en el guion. |
| Productor | `agentes/productor.py` | Voz neural en español (edge-tts, gratis), B-roll vertical de Pexels (gratis) o fondos animados, subtítulos palabra por palabra, titular por escena, barra de progreso y música opcional. |
| Community Manager | `agentes/community_manager.py` | Escribe caption, hashtags y primer comentario; elige el horario; mantiene la cola; publica vía Instagram Graph API; lee métricas (alcance, vistas, guardados, compartidos, tiempo de visualización) y **reajusta los horarios** con datos reales. |

`main.py` es el coordinador que los encadena.

---

## 1. Instalación (en tu computadora)

Requisitos: Python 3.10+ y **ffmpeg**.

```bash
# macOS:  brew install ffmpeg      Ubuntu: sudo apt install ffmpeg      Windows: winget install ffmpeg
cd reels-agentes
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium     # navegador sin ventana que graba las animaciones
cp .env.example .env    # y rellena las claves
```

- **ANTHROPIC_API_KEY**: https://console.anthropic.com
- **PEXELS_API_KEY** (opcional, gratis): https://www.pexels.com/api/ — sin ella se usan fondos animados generados.
- Fuente de subtítulos: el estilo usa **Inter** (gratis en Google Fonts). Instálala o cambia `Inter ExtraBold` en `productor.py`.
- Música: deja archivos `.mp3` **libres de derechos** en `musica/` (p. ej. YouTube Audio Library) y se usa una al azar.

## 2. Crear la cuenta nueva de Instagram y conectarla

1. Crea la cuenta y pásala a **Cuenta profesional → Creador** (Configuración → Tipo de cuenta).
2. En https://developers.facebook.com crea una app con el caso de uso **"Administrar mensajes y contenido en Instagram"**.
3. Crea un **portfolio comercial** (lo pide Meta), vincúlalo a la app y agrega tu cuenta como **Evaluador de Instagram**
   (acepta la invitación en instagram.com/accounts/manage_access → Invitaciones de prueba).

**Opción A, recomendada: "API setup with Unified login"** (token de usuario del sistema que no caduca)

4. Crea la configuración con la cuenta de Instagram como activo y los permisos `instagram_basic`,
   `instagram_content_publish`, `instagram_manage_comments` e `instagram_manage_insights`. Genera el token (empieza con `EAA`).
5. El `IG_USER_ID` es el identificador de la cuenta de Instagram que aparece en el portfolio comercial
   (Configuración del negocio → Cuentas → Cuentas de Instagram).
6. En `.env`: `IG_ACCESS_TOKEN`, `IG_USER_ID` e `IG_API_BASE=https://graph.facebook.com`.

**Opción B: "API setup with Instagram login"** (token que empieza con `IG`, dura 60 días)

4. Genera el token con `instagram_business_basic`, `instagram_business_content_publish`,
   `instagram_business_manage_comments` e `instagram_business_manage_insights`.
5. Obtén el `IG_USER_ID`:
   ```bash
   curl "https://graph.instagram.com/v23.0/me?fields=user_id,username&access_token=TU_TOKEN"
   ```
6. En `.env`: `IG_ACCESS_TOKEN`, `IG_USER_ID` e `IG_API_BASE=https://graph.instagram.com`. Renueva el token antes de 60 días:
   ```bash
   curl "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=TU_TOKEN"
   ```

El token es una contraseña: guárdalo solo en `.env` (que no se sube a GitHub) y nunca lo compartas.

El video se sube directo desde tu PC (carga reanudable), **no necesitas hosting**.

## 3. Voz del canal

Voz elegida: **es-MX-JorgeNeural** (hombre, español de México, clara y neutra). Ya viene configurada.
Para escuchar alternativas o cambiarla más adelante:

```bash
python main.py voces                 # graba la misma frase con cada voz y crea salida/voces/index.html
python main.py voces --frase "Tu frase de prueba"   # opcional: prueba con otro texto
python main.py elegir-voz es-MX-JorgeNeural         # guarda la elegida en .env
```
Abre `salida/voces/index.html` en el navegador y compáralas. La velocidad base se ajusta con `VELOCIDAD_VOZ` en `.env`.

## 4. Uso

```bash
# Primer video (el guion de terremotos ya viene escrito y revisado en guiones/)
python main.py crear --guion guiones/como-funcionan-los-temblores-y-terremotos.json

# Cualquier tema nuevo: el guionista escribe, el productor graba, el CM programa
python main.py crear "cómo funciona un microondas"

# Plan de la semana: el Community Manager respeta el orden de tus temas, propone los que faltan,
# elige la mejor hora de cada día, produce cada Reel y lo deja en la cola para tu aprobación
python main.py semana "cómo funciona la electricidad" "cómo se forma un arcoíris" --total 5
python main.py semana ... --solo-plan   # solo ver el calendario, sin producir

python main.py ideas 15      # banco de temas con su gancho

# Guardar un guion para una fecha: agrega "publicar_desde": "AAAA-MM-DD" al JSON del guion.
# Hasta ese día, `priorizar` no lo considera (ej.: Santa Teresa de Los Andes, desde 2027-09-20).
python main.py auto 5        # produce y programa los 5 siguientes temas
python main.py cola          # calendario de publicaciones
python main.py aprobar a1b2c3d4
python main.py publicar      # publica lo que ya toca
python main.py analizar      # cada semana: métricas → diagnóstico → nuevos horarios
```

Solo el video, sin publicar: `--sin-publicar`. Probar sin internet (sin voz): `--sin-voz`.
Sin animaciones (solo stock): `--sin-animacion`.

### Animación
- `MODO_VISUAL=animacion` (por defecto): todas las escenas animadas.
  `mixto`: alterna animación y video real de Pexels (más variedad visual). `broll`: solo stock.
- Las animaciones aprobadas se guardan dentro del guion (`"animacion"` en cada escena). Si cambias la
  voz y vuelves a renderizar, se reutilizan y se resincronizan solas con las palabras.
- Para rehacer la animación de una escena, borra su campo `"animacion"` en el JSON y vuelve a correr `crear --guion`.
- El guion de terremotos ya trae sus 9 animaciones hechas: renderizarlo no gasta tokens del animador.

### Publicación manual (modo por defecto)
Con `MODO_PUBLICACION=manual` (en `.env`), `crear` y `semana` no suben nada a Instagram: dejan cada Reel en
`~/Desktop/Reels listos/<fecha_hora>_<tema>/` con `reel.mp4` y `publicacion.txt` (caption, primer comentario,
horario sugerido y datos a verificar). Lo subes desde la app y luego lo marcas con `python main.py publicado <id>`,
para que el Community Manager sepa qué ya salió. Para volver a la publicación automática: `MODO_PUBLICACION=automatica`.

### Revisión humana (recomendado)
Con `REVISION_MANUAL=true` cada Reel queda en `pendiente_revision`: mira el MP4, revisa la lista
de **datos a verificar** que imprime el guionista y apruébalo. Un dato falso en una cuenta de
divulgación destruye la credibilidad, y la cuenta es nueva. Cuando confíes en el flujo, ponlo en `false`.

### Publicación automática a la hora elegida
Instagram no programa publicaciones por API, así que el sistema publica cuando llega la hora:

```bash
# Linux/macOS (crontab -e): revisa cada 10 minutos
*/10 * * * * cd /ruta/reels-agentes && .venv/bin/python main.py publicar >> data/publicar.log 2>&1
```
O deja una terminal con `python main.py vigilar`. (Windows: Programador de tareas.)

## 5. Estrategia de horarios
- Arranca con `HORARIOS_BASE` en `agentes/config.py` (mediodía y 19:30–20:00 entre semana,
  mañana y tarde el fin de semana; hora local de `ZONA_HORARIA`). Ajusta `ZONA_HORARIA` al país de tu público.
- Con 5+ Reels publicados, `python main.py analizar` hace que el CM estudie qué horarios y temas
  rindieron más y guarda los nuevos horarios en `data/horarios.json`, que se usan desde ese momento.
- `PUBLICACIONES_MAX_POR_DIA=1` es lo sano al inicio: constancia diaria > ráfagas.

## 6. Consejos para que se viralice
- Los primeros 2 segundos lo son todo: el titular grande + la primera frase deben funcionar **sin sonido**.
- 35–60 s es la duración ideal para este formato. Si el video pasa de 60 s, pide guiones más cortos.
- El audio en tendencia de Instagram **no** se puede añadir por API. Para un Reel clave, descarga el
  MP4 y súbelo a mano con un audio en tendencia a volumen bajo.
- Responde comentarios en la primera hora; el CM ya deja un primer comentario con pregunta.
- Series ("Cómo funciona… #1, #2") generan seguidores recurrentes.

## Estructura
```
reels-agentes/
├── main.py                 coordinador / CLI
├── agentes/
│   ├── config.py           claves, voz, zona horaria, horarios base
│   ├── claude.py           llamada a Claude con salida JSON validada
│   ├── guionista.py        AGENTE 1
│   ├── narrador.py         AGENTE 2 (voces, dirección de locución)
│   ├── animador.py         AGENTE 3 (animador + director)
│   ├── anim_lib.js         motor de animación que usa el animador
│   ├── productor.py        AGENTE 4 (montaje, subtítulos, música)
│   └── community_manager.py AGENTE 5 (+ Instagram Graph API)
├── guiones/                guiones JSON (editables a mano)
├── salida/<tema>/reel.mp4  videos terminados
├── musica/                 tus pistas libres de derechos
└── data/                   cola.json, ideas.json, metricas.json, horarios.json
```

## Skills de animación instaladas (`.claude/skills/`)
| Skill | Origen y licencia | Uso en el proyecto |
|---|---|---|
| procedural-film | kuhnhomeuk-cell/procedural-film (MIT) | Trazo a mano y plano blueprint (`ESTILO_ANIMACION=pelicula`) |
| motionmaxxing | Tejashmakwana/motionmaxxing (Apache-2.0) | 12 curvas de animación medidas (`A.p(..., 'softLand')`) y criterio de motion design del Animador |
| gsap-* (8 skills) | greensock/gsap-skills (MIT) | Líneas de tiempo GSAP en las escenas (`A.tl(...)`); GSAP en `agentes/vendor/` |

Claude Code las carga automáticamente al trabajar en esta carpeta.

