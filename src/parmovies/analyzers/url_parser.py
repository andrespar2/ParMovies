"""Analizador de enlaces y entradas de Vimeus.

Acepta URLs de peliculas, series, anime y episodios, ademas de codigo HTML de
``<iframe>`` pegado directamente por el usuario. Normaliza la entrada, valida
el protocolo y el dominio (previniendo SSRF) y extrae los parametros de forma
segura, admitiendo parametros en cualquier orden y parametros adicionales.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qs, urlparse

from ..api.models import ContentRequest
from .errors import AnalysisError

_IFRAME_SRC = re.compile(r"""src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_URL_IN_TEXT = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)

# Tipos de contenido admitidos en la ruta (segmento posterior a /e/ o /d/).
_KIND_ALIASES = {
    "movie": "movie",
    "movies": "movie",
    "pelicula": "movie",
    "serie": "serie",
    "series": "serie",
    "anime": "anime",
    "animes": "anime",
    "episode": "episode",
    "episodes": "episode",
    "episodio": "episode",
}

_ALLOWED_SCHEMES = ("http", "https")


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().rstrip(".")


def is_domain_trusted(host: str, trusted_domains: list[str] | tuple[str, ...]) -> bool:
    """Comprueba si un host pertenece a los dominios permitidos."""

    if not host:
        return False
    host = _normalize_domain(host)
    for allowed in trusted_domains:
        allowed = _normalize_domain(allowed)
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _extract_url(text: str) -> str:
    """Extrae una URL de un texto que puede contener un iframe o HTML."""

    candidate = (text or "").strip()
    if not candidate:
        raise AnalysisError("No se introdujo ningun enlace.")

    # Si parece HTML con iframe, extrae el atributo src.
    if "<" in candidate and ">" in candidate:
        match = _IFRAME_SRC.search(candidate)
        if match:
            return match.group(1).strip()
        url_match = _URL_IN_TEXT.search(candidate)
        if url_match:
            return url_match.group(0).strip()
        raise AnalysisError("No se encontro una URL valida dentro del codigo HTML.")

    # Si la primera linea contiene la URL rodeada de texto, extrae ese fragmento.
    match = _URL_IN_TEXT.search(candidate)
    if match:
        return match.group(0).strip()
    return candidate


def _reject_unsafe_host(host: str) -> None:
    """Bloquea destinos locales o direcciones IP (prevencion de SSRF)."""

    host = _normalize_domain(host)
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise AnalysisError("El destino apunta a un recurso local y fue rechazado.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise AnalysisError("El destino apunta a una direccion privada y fue rechazado.")


def _parse_kind(segments: list[str]) -> str | None:
    """Determina el tipo de contenido a partir de la ruta."""

    for segment in segments:
        key = segment.lower()
        if key in _KIND_ALIASES:
            return _KIND_ALIASES[key]
    return None


def parse_input(
    text: str,
    trusted_domains: list[str] | tuple[str, ...] = ("vimeus.com",),
) -> ContentRequest:
    """Analiza la entrada del usuario y devuelve una peticion de contenido.

    Lanza :class:`AnalysisError` con un mensaje en espanol cuando la entrada no
    es valida o no proviene de un dominio autorizado.
    """

    origin = "iframe" if ("<" in (text or "")) else "url"
    raw_url = _extract_url(text)
    parsed = urlparse(raw_url)

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise AnalysisError(
            "El enlace debe usar el protocolo http o https. Otros protocolos no estan permitidos."
        )

    host = parsed.hostname or ""
    if not host:
        raise AnalysisError("El enlace no contiene un dominio valido.")
    _reject_unsafe_host(host)
    if not is_domain_trusted(host, trusted_domains):
        allowed = ", ".join(sorted(set(trusted_domains)))
        raise AnalysisError(
            f"El dominio '{host}' no esta autorizado. Dominios admitidos: {allowed}."
        )

    segments = [seg for seg in parsed.path.split("/") if seg]
    kind = _parse_kind(segments)
    if kind is None:
        raise AnalysisError(
            "No se pudo identificar el tipo de contenido en la ruta del enlace "
            "(se esperaba movie, serie, anime o episode)."
        )

    params = parse_qs(parsed.query, keep_blank_values=False)

    def first(name: str) -> str:
        values = params.get(name)
        return values[0].strip() if values else ""

    tmdb_raw = first("tmdb") or first("tmdb_id")
    imdb_raw = first("imdb") or first("imdb_id")
    season_raw = first("se") or first("season")
    episode_raw = first("ep") or first("episode")
    view_key = first("view_key")

    tmdb_id = _to_int(tmdb_raw, "tmdb") if tmdb_raw else None
    season = _to_int(season_raw, "se") if season_raw else None
    episode = _to_int(episode_raw, "ep") if episode_raw else None

    if imdb_raw and not re.fullmatch(r"tt\d{5,10}", imdb_raw):
        raise AnalysisError(f"El identificador de IMDb '{imdb_raw}' no tiene un formato valido.")

    if tmdb_id is None and not imdb_raw:
        raise AnalysisError(
            "El enlace no incluye un identificador tmdb ni imdb; no es posible consultar el contenido."
        )

    if (season is None) != (episode is None) and kind in ("serie", "anime"):
        raise AnalysisError(
            "Para un episodio debe indicarse la temporada (se) y el episodio (ep)."
        )

    return ContentRequest(
        kind=kind,
        endpoint=kind,
        tmdb_id=tmdb_id,
        imdb_id=imdb_raw,
        season=season,
        episode=episode,
        view_key=view_key,
        source_url=raw_url,
        origin=origin,
    )


def _to_int(value: str, param: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise AnalysisError(f"El parametro '{param}' debe ser un numero entero.") from None
    if number < 0:
        raise AnalysisError(f"El parametro '{param}' no puede ser negativo.")
    return number
