"""Redaccion y ocultamiento de credenciales.

Ningun secreto debe aparecer en registros, mensajes de error, historial ni en
los archivos versionados. Estas utilidades centralizan esa proteccion.
"""

from __future__ import annotations

import re
from typing import Iterable

# Nombres de parametros o claves que nunca deben mostrarse completos.
SENSITIVE_KEYS = ("view_key", "api_key", "apikey", "x-api-key", "token", "hash")

_VIEW_KEY_PATTERN = re.compile(r"(view_key=)([^&\s\"'<>]+)", re.IGNORECASE)
_QUERY_SECRET_PATTERN = re.compile(
    r"((?:api_key|apikey|token|hash)=)([^&\s\"'<>]+)", re.IGNORECASE
)

_MASK = "********"


def mask_secret(value: str | None, *, visible: int = 4) -> str:
    """Enmascara un secreto mostrando como maximo ``visible`` caracteres finales."""

    if not value:
        return "(sin definir)"
    text = str(value)
    if len(text) <= visible:
        return _MASK
    return f"{_MASK}{text[-visible:]}"


def redact_url(url: str) -> str:
    """Sustituye los valores sensibles de una URL por una mascara."""

    if not url:
        return url
    redacted = _VIEW_KEY_PATTERN.sub(r"\1" + _MASK, url)
    redacted = _QUERY_SECRET_PATTERN.sub(r"\1" + _MASK, redacted)
    return redacted


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Elimina de un texto cualquier credencial conocida o patron sensible."""

    if not text:
        return text
    result = redact_url(str(text))
    for secret in secrets:
        if secret and len(str(secret)) >= 6:
            result = result.replace(str(secret), _MASK)
    return result
