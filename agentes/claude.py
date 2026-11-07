"""Llamada común a Claude con salida JSON validada por esquema.

Dos motores (MOTOR_IA en .env):
- "claude-code" (por defecto): usa el programa `claude` (Claude Code) con tu sesión de claude.ai.
  Cuenta dentro de los límites de tu plan Pro/Max y no gasta saldo de la API.
- "api": usa la API de Anthropic con ANTHROPIC_API_KEY (se paga por uso).
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import MODELO, MOTOR_IA

_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        import anthropic

        _cliente = anthropic.Anthropic()
    return _cliente


def pedir_json(system: str, prompt: str | list, schema: dict, effort: str = "high",
               max_tokens: int = 16000) -> dict:
    if MOTOR_IA == "claude-code":
        return _pedir_json_claude_code(system, prompt, schema)
    return _pedir_json_api(system, prompt, schema, effort, max_tokens)


# ---------------------------------------------------------------- Claude Code (plan de claude.ai)
def _pedir_json_claude_code(system: str, prompt: str | list, schema: dict) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("No encontré el programa `claude` (Claude Code). Instálalo o usa MOTOR_IA=api en .env.")
    with tempfile.TemporaryDirectory(prefix="reels-ia-") as tmp:
        partes, hay_imagen = [], False
        for bloque in (prompt if isinstance(prompt, list) else [{"type": "text", "text": prompt}]):
            if bloque.get("type") == "image":
                ruta = Path(tmp) / f"imagen_{len(partes)}.png"
                ruta.write_bytes(base64.b64decode(bloque["source"]["data"]))
                partes.append(f"[Imagen adjunta: {ruta} — ábrela con la herramienta Read antes de responder.]")
                hay_imagen = True
            else:
                partes.append(bloque.get("text", ""))
        cmd = [exe, "-p", "\n\n".join(partes), "--output-format", "json",
               "--json-schema", json.dumps(schema), "--system-prompt", system,
               "--no-session-persistence"]
        cmd += ["--tools", "Read", "--allowedTools", "Read", "--add-dir", tmp] if hay_imagen else ["--tools", ""]
        # Sin clave de API en el entorno: así Claude Code usa tu sesión de claude.ai y no cobra por uso.
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, env=env, cwd=tmp)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude Code no respondió en 30 minutos.")
    try:
        datos = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude Code falló (código {r.returncode}): {(r.stderr or r.stdout)[-800:]}")
    if datos.get("is_error"):
        raise RuntimeError(f"Claude Code devolvió un error: {str(datos.get('result'))[:800]}")
    if datos.get("structured_output") is not None:
        return datos["structured_output"]
    return json.loads(datos["result"])


# ---------------------------------------------------------------- API de Anthropic (pago por uso)
def _pedir_json_api(system, prompt, schema, effort, max_tokens) -> dict:
    # Siempre en streaming: con max_tokens alto (el Animador pide 24 000) el SDK rechaza las
    # peticiones sin streaming ("Streaming is required for operations that may take longer than 10 minutes").
    with cliente().beta.messages.stream(
        model=MODELO,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        # Si un clasificador rechaza la petición, la API la reintenta en el
        # modelo de respaldo recomendado en vez de devolver el rechazo.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        resp = stream.get_final_message()
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Claude rechazó la petición: {resp.stop_details}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Respuesta cortada por max_tokens; súbelo e intenta de nuevo.")
    texto = next(b.text for b in resp.content if b.type == "text")
    return json.loads(texto)
