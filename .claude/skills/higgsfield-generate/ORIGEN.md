# Origen

Skills oficiales de Higgsfield AI: https://github.com/higgsfield-ai/skills
Versión 0.14.0, commit 27000402070db19d958789d05b3b52b6f4718d7c. Licencia MIT (ver LICENSE).

Instaladas en este proyecto: higgsfield-generate, higgsfield-faceless-video,
higgsfield-video-explainer y higgsfield-youtube-thumbnail (las de brandkit, websites,
marketplace, photoshoot y soul-id no aplican a los Reels y no se copiaron).

**Ojo: Higgsfield es de pago.** Cada imagen o video generado gasta créditos de tu cuenta
higgsfield.ai. Usan el programa `higgsfield` (CLI oficial), que se instala y se conecta en tu Mac:

    brew install higgsfield-ai/tap/higgsfield
    higgsfield auth login

En este proyecto, antes de generar, pide siempre el costo estimado (`higgsfield generate cost`)
y confirma con el usuario. El pipeline principal (animaciones con Claude Code + edge-tts) sigue
siendo gratis; Higgsfield es opcional, para tomas puntuales (p. ej. un gancho cinematográfico).
