"""Construccion y escritura de metadatos (``info.json``)."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..api.models import MediaAnalysis, MediaVariant, SubtitleTrack
from ..media.ffmpeg import MediaInfo
from ..security.redaction import redact_url
from ..utilities.logging_setup import get_logger

_log = get_logger("metadata")


def _duration_text(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return ""
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_info(
    analysis: MediaAnalysis,
    *,
    variant: MediaVariant | None = None,
    subtitles: list[SubtitleTrack] | None = None,
    media_info: MediaInfo | None = None,
    output_path: Path | None = None,
    audio_language: str = "",
) -> dict[str, Any]:
    """Construye el diccionario de metadatos verificables."""

    request = analysis.request
    height = (media_info.height if media_info and media_info.height else None) or (
        variant.height if variant else None
    )
    width = (media_info.width if media_info and media_info.width else None) or (
        variant.width if variant else None
    )
    resolution = (
        f"{width}x{height}" if width and height else (media_info.resolution if media_info else "desconocida")
    )

    payload: dict[str, Any] = {
        "title": analysis.title,
        "content_type": analysis.content_type or request.kind,
        "season": request.season,
        "episode": request.episode,
        "tmdb_id": request.tmdb_id,
        "imdb_id": request.imdb_id or None,
        "resolution": resolution,
        "height": height,
        "width": width,
        "format": (
            (media_info.format_name if media_info else "") or (output_path.suffix.lstrip(".") if output_path else "")
        ),
        "video_codec": media_info.video_codec if media_info else "",
        "audio_codec": media_info.audio_streams[0].codec if media_info and media_info.audio_streams else "",
        "audio_language": audio_language,
        "audio_streams": (
            [asdict(stream) for stream in media_info.audio_streams] if media_info else []
        ),
        "subtitle_languages": [track.language or track.label for track in (subtitles or [])],
        "duration": _duration_text(
            (media_info.duration_seconds if media_info else None) or (
                analysis.playback.duration_seconds if analysis.playback else None
            )
        ),
        "duration_seconds": (
            (media_info.duration_seconds if media_info else None)
            or (analysis.playback.duration_seconds if analysis.playback else None)
        ),
        "size_bytes": media_info.size_bytes if media_info else (output_path.stat().st_size if output_path and output_path.exists() else 0),
        "poster": analysis.poster,
        "backdrop": analysis.backdrop,
        "source": redact_url(request.source_url),
        "servers": [embed.server for embed in analysis.embeds],
        "downloaded_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "generator": "ParMovies",
    }

    if output_path:
        payload["file"] = output_path.name
    if is_dataclass(payload):
        payload = asdict(payload)
    return payload


def write_info_json(directory: Path, payload: dict[str, Any]) -> Path | None:
    """Escribe ``info.json`` en la carpeta indicada."""

    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "info.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return target
    except OSError as exc:
        _log.warning("No se pudo escribir info.json: %s", exc)
        return None
