"""Organizacion de archivos descargados.

Estructura generada dentro de la carpeta de descargas:

.. code-block:: text

    Descargas/
        Peliculas/Titulo (2025)/Titulo (2025) [1080p] [ES-LAT].mkv
        Series/Nombre/Temporada 01/Nombre - S01E01 [1080p].mkv
        Anime/Nombre/Temporada 01/Nombre - S01E01.mkv
"""

from __future__ import annotations

from pathlib import Path

from ..api.models import MediaAnalysis
from ..media.ffmpeg import MediaInfo
from ..media.formats import spanish_kind
from . import paths

_CATEGORY = {
    "movie": "Peliculas",
    "serie": "Series",
    "series": "Series",
    "episode": "Series",
    "anime": "Anime",
}

_AUDIO_TAG = {
    "latino": "ES-LAT",
    "espana": "ES-ES",
    "generico": "ES",
}


def audio_tag(audio_language: str) -> str:
    """Etiqueta corta de idioma solo si esta verificado."""

    kind = spanish_kind(audio_language)
    if kind:
        return _AUDIO_TAG.get(kind, "ES")
    value = (audio_language or "").strip().upper()
    if value and len(value) <= 6 and value.isalpha():
        return value
    return ""


def category_for(analysis: MediaAnalysis) -> str:
    """Categoria de carpeta segun el tipo de contenido."""

    key = (analysis.request.kind or analysis.content_type or "movie").lower()
    if key == "series":
        key = "serie"
    return _CATEGORY.get(key, "Peliculas")


def build_output_path(
    downloads_dir: Path,
    analysis: MediaAnalysis,
    *,
    height: int | None = None,
    year: int | None = None,
    audio_language: str = "",
    container: str = "mkv",
) -> Path:
    """Calcula la ruta final del archivo multimedia."""

    request = analysis.request
    title = paths.sanitize_component(analysis.title or "Contenido")
    category = category_for(analysis)
    extension = container.lstrip(".")
    tag = audio_tag(audio_language)

    is_episode = request.season is not None or request.episode is not None or request.kind in ("episode",)
    quality = f" [{height}p]" if height else ""

    if is_episode:
        season = request.season if request.season is not None else 1
        episode = request.episode if request.episode is not None else 1
        folder = downloads_dir / category / title / f"Temporada {season:02d}"
        name = f"{title} - S{season:02d}E{episode:02d}{quality}"
    else:
        folder_name = f"{title} ({year})" if year else title
        folder = downloads_dir / category / paths.sanitize_component(folder_name)
        name = f"{folder_name}{quality}"

    if tag:
        name = f"{name} [{tag}]"

    return folder / f"{paths.safe_filename(name)}.{extension}"


def choose_target(path: Path, strategy: str = "ask") -> Path:
    """Determina la ruta final evitando sobrescribir archivos existentes.

    ``strategy`` puede ser ``overwrite`` (no recomendado), ``skip`` (devuelve la
    ruta original para que el motor la omita) o ``rename`` (anade sufijo).
    """

    if not path.exists():
        return path
    if strategy == "overwrite":
        return path
    if strategy == "skip":
        return path
    return paths.unique_path(path)


def format_size(size_bytes: int) -> str:
    """Formatea un tamano en unidades legibles."""

    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def describe_media(info: MediaInfo | None, fallback_height: int | None = None) -> str:
    """Descripcion breve de la resolucion verificada."""

    if info and info.resolution != "desconocida":
        return info.resolution
    if fallback_height:
        return f"{fallback_height}p"
    return "desconocida"
