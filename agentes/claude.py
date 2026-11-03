"""Llamada común a Claude con salida JSON validada por esquema."""
import json

import anthropic

from .config import MODELO

_cliente = None


def cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


def pedir_json(system: str, prompt: str | list, schema: dict, effort: str = "high",
               max_tokens: int = 16000) -> dict:
    resp = cliente().beta.messages.create(
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
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Claude rechazó la petición: {resp.stop_details}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Respuesta cortada por max_tokens; súbelo e intenta de nuevo.")
    texto = next(b.text for b in resp.content if b.type == "text")
    return json.loads(texto)
