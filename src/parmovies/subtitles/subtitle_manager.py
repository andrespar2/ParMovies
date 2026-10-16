"""Gestion de subtitulos: descarga y conversion de formatos."""

from __future__ import annotations

import re
from pathlib import Path

from ..api.models import SubtitleTrack
from ..utilities import paths
from ..utilities.logging_setup import get_logger

_log = get_logger("subtitles")

_TIMESTAMP = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
_SHORT_TIMESTAMP = re.compile(
    r"(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})"
)


def language_suffix(track: SubtitleTrack) -> str:
    """Genera un sufijo de archivo a partir del idioma de la pista."""

    code = (track.language or track.label or "und").strip().lower()
    code = code.replace("_", "-")
    code = re.sub(r"[^a-z0-9\-]", "", code)
    return paths.safe_filename(code or "und", max_length=24)


def subtitle_path(base: Path, track: SubtitleTrack, extension: str) -> Path:
    """Construye la ruta de un archivo de subtitulos externo."""

    return base.parent / f"{base.stem}.{language_suffix(track)}.{extension}"


def vtt_to_srt(content: str) -> str:
    """Convierte contenido WebVTT en SRT sencillo."""

    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    index = 0
    counter = 1
    while index < len(lines):
        line = lines[index].strip("\ufeff")
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("WEBVTT"):
            index += 1
            continue
        if stripped.upper().startswith(("NOTE", "STYLE", "REGION")):
            index += 1
            continue
        if _SHORT_TIMESTAMP.search(stripped) or "-->" in stripped:
            timestamps = _normalize_timestamp(stripped)
            output.append(str(counter))
            output.append(timestamps)
            counter += 1
            index += 1
            while index < len(lines) and lines[index].strip():
                output.append(lines[index].strip())
                index += 1
            output.append("")
            continue
        index += 1
    return "\n".join(output).strip() + "\n"


def _normalize_timestamp(line: str) -> str:
    """Normaliza una linea de tiempos a formato SRT (``HH:MM:SS,mmm``)."""

    def fix(match: re.Match) -> str:
        groups = match.groups()
        # Acepta formato largo (8 grupos) o corto (8 grupos con horas opcionales).
        if len(groups) == 8:
            if groups[0] is not None:  # formato largo HH:MM:SS,mmm
                left = f"{groups[0]}:{groups[1]}:{groups[2]},{groups[3]}"
                right = f"{groups[4]}:{groups[5]}:{groups[6]},{groups[7]}"
            else:  # formato corto MM:SS,mmm
                left = f"00:{groups[1]}:{groups[2]},{groups[3]}"
                right = f"00:{groups[5]}:{groups[6]},{groups[7]}"
            return f"{left} --> {right}"
        # Fallback al formato largo.
        m = _TIMESTAMP.search(line)
        if m:
            g = m.groups()
            left = f"{g[0]}:{g[1]}:{g[2]},{g[3]}"
            right = f"{g[4]}:{g[5]}:{g[6]},{g[7]}"
            return f"{left} --> {right}"
        return line.strip()

    result = _SHORT_TIMESTAMP.sub(fix, line)
    return result.strip()


def save_subtitle(
    track: SubtitleTrack,
    content: str,
    base_path: Path,
    *,
    convert_to_srt: bool = True,
) -> Path | None:
    """Guarda el contenido de un subtitulo como archivo externo."""

    url_lower = track.url.lower()
    if url_lower.endswith(".srt"):
        extension = "srt"
        text = content
    elif url_lower.endswith(".vtt") or "webvtt" in content[:64].lower():
        if convert_to_srt:
            extension = "srt"
            text = vtt_to_srt(content)
        else:
            extension = "vtt"
            text = content
    else:
        extension = "srt" if convert_to_srt else "vtt"
        text = vtt_to_srt(content) if convert_to_srt else content

    target = subtitle_path(base_path, track, extension)
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as exc:
        _log.warning("No se pudo guardar el subtitulo %s: %s", target, exc)
        return None
    return target
