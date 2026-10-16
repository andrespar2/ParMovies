"""Extraccion de datos de la pagina de embed de Vimeus (``/e/...``).

La pagina de embed incluye un bloque:

.. code-block:: html

    <script type="text/json" id="data"> { ... "embeds": [ ... ] ... } </script>

con la lista de servidores de reproduccion autorizados.
"""

from __future__ import annotations

import json
import re

from ..api.models import EmbedSource, tmdb_image_url
from ..utilities.logging_setup import get_logger

_log = get_logger("embed")

_DATA_BLOCK = re.compile(
    r"<script[^>]*type=[\"']text/json[\"'][^>]*id=[\"']data[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_DATA_BLOCK_ALT = re.compile(
    r"<script[^>]*id=[\"']data[\"'][^>]*type=[\"']text/json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


class EmbedData:
    """Datos interpretados de la pagina de embed."""

    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.title = str(raw.get("title") or "").strip()
        self.content_type = str(raw.get("type") or "").strip()
        self.poster = tmdb_image_url(raw.get("poster"))
        self.backdrop = tmdb_image_url(raw.get("backdrop"))
        self.season = _as_int(raw.get("season"))
        self.episode = _as_int(raw.get("episode"))
        self.tmdb_id = _as_int(raw.get("tmdb_id"))
        self.embeds: list[EmbedSource] = []
        embeds_raw = raw.get("embeds")
        if isinstance(embeds_raw, list):
            for item in embeds_raw:
                if isinstance(item, dict):
                    self.embeds.append(EmbedSource.from_api(item))


def _as_int(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_embed_page(html: str) -> EmbedData | None:
    """Extrae y parsea el bloque JSON de la pagina de embed."""

    match = _DATA_BLOCK.search(html) or _DATA_BLOCK_ALT.search(html)
    if not match:
        _log.warning("No se encontro el bloque JSON de datos en la pagina de embed.")
        return None
    payload = match.group(1).strip()
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        # El bloque puede contener entidades HTML simples.
        cleaned = payload.replace("&quot;", '"').replace("&amp;", "&")
        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError:
            _log.warning("El bloque JSON de la pagina de embed no es valido.")
            return None
    if not isinstance(raw, dict):
        return None
    return EmbedData(raw)
