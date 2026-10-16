"""Extraccion de la configuracion del reproductor externo.

El reproductor externo (por ejemplo ``vimeos.net``) entrega su configuracion
dentro de un bloque JavaScript empaquetado. Tras desofuscarlo con
:mod:`parmovies.analyzers.js_unpacker` se localizan las fuentes (HLS o MP4) y
las pistas de subtitulos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from ..utilities.logging_setup import get_logger
from .js_unpacker import unpack_program

_log = get_logger("player")

_SIMPLE_STRING = re.compile(r"""["']?(\w+)["']?\s*:\s*(?:"([^"]*)"|'([^']*)')""")
_BOOL_TRUE = re.compile(r"""["']?(\w+)["']?\s*:\s*true\b""")
_IMAGE = re.compile(r"""image\s*:\s*(?:"([^"]*)"|'([^']*)')""")
_DURATION = re.compile(r"""duration\s*:\s*(?:"([^"]*)"|'([^']*)')""")


@dataclass
class PlayerSource:
    """Fuente de video declarada por el reproductor."""

    url: str = ""
    label: str = ""
    mime: str = ""


@dataclass
class PlayerConfig:
    """Configuracion interpretada del reproductor externo."""

    sources: list[PlayerSource] = field(default_factory=list)
    tracks: list[dict] = field(default_factory=list)
    image: str = ""
    duration_seconds: float | None = None


def _extract_array(js: str, key: str) -> str | None:
    """Devuelve el texto del array ``key:[...]`` respetando comillas y anidamiento."""

    match = re.search(re.escape(key) + r"\s*:\s*\[", js)
    if not match:
        return None
    start = match.end() - 1  # posicion del '['
    depth = 0
    index = start
    while index < len(js):
        char = js[index]
        if char in "\"'":
            quote = char
            index += 1
            while index < len(js) and js[index] != quote:
                if js[index] == "\\":
                    index += 1
                index += 1
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return js[start + 1 : index]
        index += 1
    return None


def _iter_objects(array_text: str) -> list[str]:
    """Devuelve los objetos ``{...}`` de nivel superior de un array."""

    objects: list[str] = []
    depth = 0
    start = None
    index = 0
    while index < len(array_text):
        char = array_text[index]
        if char in "\"'":
            quote = char
            index += 1
            while index < len(array_text) and array_text[index] != quote:
                if array_text[index] == "\\":
                    index += 1
                index += 1
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(array_text[start : index + 1])
                start = None
        index += 1
    return objects


def _parse_object(obj_text: str) -> dict:
    """Convierte un objeto JavaScript sencillo en un diccionario Python."""

    result: dict[str, object] = {}
    for match in _SIMPLE_STRING.finditer(obj_text):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        result[match.group(1)] = value
    for match in _BOOL_TRUE.finditer(obj_text):
        result[match.group(1)] = True
    return result


def parse_player_config(html: str) -> PlayerConfig | None:
    """Extrae la configuracion del reproductor desde el HTML del player."""

    js = unpack_program(html)
    if js is None:
        # Algunos reproductores no empaquetan la configuracion.
        js = html

    config = PlayerConfig()

    sources_text = _extract_array(js, "sources")
    if sources_text:
        for obj_text in _iter_objects(sources_text):
            data = _parse_object(obj_text)
            url = str(data.get("file") or "").strip()
            if not url:
                continue
            config.sources.append(
                PlayerSource(
                    url=urljoin("https://vimeos.net/", url) if url.startswith("/") else url,
                    label=str(data.get("label") or ""),
                    mime=str(data.get("type") or ""),
                )
            )

    tracks_text = _extract_array(js, "tracks")
    if tracks_text:
        for obj_text in _iter_objects(tracks_text):
            data = _parse_object(obj_text)
            url = str(data.get("file") or "").strip()
            if not url:
                continue
            config.tracks.append(
                {
                    "file": urljoin("https://vimeos.net/", url) if url.startswith("/") else url,
                    "label": str(data.get("label") or ""),
                    "kind": str(data.get("kind") or ""),
                    "default": bool(data.get("default")),
                }
            )

    image_match = _IMAGE.search(js)
    if image_match:
        config.image = image_match.group(1) or image_match.group(2) or ""

    duration_match = _DURATION.search(js)
    if duration_match:
        raw = duration_match.group(1) or duration_match.group(2) or ""
        try:
            config.duration_seconds = float(raw)
        except ValueError:
            config.duration_seconds = None

    if not config.sources:
        _log.warning("No se encontraron fuentes en la configuracion del reproductor.")
    return config
