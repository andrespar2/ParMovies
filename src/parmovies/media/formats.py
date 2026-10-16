"""Seleccion de calidad, audio y subtitulos.

Contiene la logica de prioridades de ParMovies: calidad maxima disponible y
preferencia por el audio en espanol latinoamericano.
"""

from __future__ import annotations

from ..api.models import MediaVariant, SubtitleTrack

# Etiquetas que identifican espanol latinoamericano.
_LATINO_MARKERS = (
    "latino",
    "latam",
    "latin",
    "es-419",
    "es-mx",
    "es-co",
    "es-ar",
    "es-cl",
    "es-pe",
    "es-ve",
    "es-us",
    "mexico",
    "colombia",
    "argentina",
    "chile",
    "peru",
)
# Etiquetas que identifican espanol de Espana.
_SPAIN_MARKERS = ("espa\u00f1a", "espana", "castellano", "spain", "es-es", "peninsular")
_GENERIC_ES_MARKERS = ("spanish", "espa\u00f1ol", "espanol", "es")

RESOLUTION_OPTIONS = (2160, 1440, 1080, 720, 480)


def spanish_kind(text: str) -> str | None:
    """Clasifica un idioma como 'latino', 'espana' o 'generico'."""

    value = (text or "").strip().lower()
    if not value:
        return None
    for marker in _LATINO_MARKERS:
        if marker in value:
            return "latino"
    for marker in _SPAIN_MARKERS:
        if marker in value:
            return "espana"
    for marker in _GENERIC_ES_MARKERS:
        if value == marker or marker in value:
            return "generico"
    return None


def audio_rank(text: str, *, original_language: str = "") -> int:
    """Prioridad de una pista de audio (menor es mejor)."""

    value = (text or "").strip().lower()
    kind = spanish_kind(value)
    if kind == "latino":
        return 0
    if kind == "espana":
        return 1
    if kind == "generico":
        return 2
    if not value:
        return 9
    if original_language and value == original_language.strip().lower():
        return 3
    return 5


def subtitle_rank(text: str) -> int:
    """Prioridad de un subtitulo: latino > espana > generico > ingles > otros."""

    value = (text or "").strip().lower()
    kind = spanish_kind(value)
    if kind == "latino":
        return 0
    if kind == "espana":
        return 1
    if kind == "generico":
        return 2
    if value in ("en", "eng", "english", "ingles", "ingl\u00e9s"):
        return 3
    if "english" in value or "ingl" in value:
        return 3
    if not value:
        return 9
    return 5


# -- Calidad de video ------------------------------------------------------
def sort_variants(variants: list[MediaVariant]) -> list[MediaVariant]:
    """Ordena las variantes de mayor a menor calidad."""

    return sorted(
        variants,
        key=lambda v: (v.height or 0, v.bandwidth or 0),
        reverse=True,
    )


def available_heights(variants: list[MediaVariant]) -> list[int]:
    """Devuelve las alturas reales disponibles, de mayor a menor."""

    heights = {v.height for v in variants if v.height}
    return sorted(heights, reverse=True)


def pick_variant(
    variants: list[MediaVariant], preferred: str | int | None = "best"
) -> MediaVariant | None:
    """Selecciona una variante segun la preferencia de calidad.

    ``preferred`` puede ser ``"best"`` o una altura (int o cadena como
    ``"1080"``). Si la altura pedida no existe, se devuelve la inmediatamente
    inferior disponible (nunca se simula una resolucion superior).
    """

    candidates = [v for v in variants if not v.is_audio_only]
    if not candidates:
        return None
    ordered = sort_variants(candidates)
    if preferred in ("best", None, ""):
        return ordered[0]
    try:
        target = int(str(preferred).replace("p", "").strip())
    except ValueError:
        return ordered[0]

    exact = [v for v in ordered if (v.height or 0) == target]
    if exact:
        return exact[0]
    lower = [v for v in ordered if (v.height or 0) < target]
    if lower:
        return lower[0]
    return ordered[-1]


# -- Audio -----------------------------------------------------------------
def order_audio_labels(labels: list[str], *, original_language: str = "") -> list[str]:
    """Ordena etiquetas de audio segun la prioridad de idioma."""

    return sorted(labels, key=lambda label: (audio_rank(label, original_language=original_language), label))


def preferred_audio_index(labels: list[str], *, original_language: str = "") -> int:
    """Devuelve el indice de la mejor pista de audio disponible."""

    if not labels:
        return -1
    ranked = order_audio_labels(labels, original_language=original_language)
    return labels.index(ranked[0])


# -- Subtitulos ------------------------------------------------------------
def select_subtitles(
    tracks: list[SubtitleTrack],
    mode: str,
    *,
    manual_indices: list[int] | None = None,
) -> list[SubtitleTrack]:
    """Selecciona subtitulos segun el modo configurado.

    Modos: ``spanish`` (solo espanol), ``all`` (todos), ``none`` (ninguno) y
    ``manual`` (indices indicados por el usuario).
    """

    if mode == "none":
        return []
    if mode == "all":
        return sort_subtitles(tracks)
    if mode == "manual":
        if not manual_indices:
            return []
        return [tracks[i] for i in manual_indices if 0 <= i < len(tracks)]
    # Modo por defecto: solo espanol.
    spanish = [t for t in tracks if spanish_kind(t.language) or spanish_kind(t.label)]
    return sort_subtitles(spanish)


def sort_subtitles(tracks: list[SubtitleTrack]) -> list[SubtitleTrack]:
    """Ordena los subtitulos por preferencia de idioma."""

    return sorted(
        tracks,
        key=lambda t: (subtitle_rank(t.language or t.label), t.language or t.label),
    )
