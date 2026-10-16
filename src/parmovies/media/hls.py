"""Analisis de manifiestos HLS (m3u8).

Soporta manifiestos maestros (varias calidades y pistas de audio/subtitulos) y
manifiestos de medios. No implementa descifrado ni claves DRM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from ..api.models import MediaVariant, SubtitleTrack


@dataclass
class HlsMaster:
    """Contenido interpretado de un manifiesto HLS maestro."""

    variants: list[MediaVariant] = field(default_factory=list)
    audio_renditions: list[MediaVariant] = field(default_factory=list)
    subtitle_renditions: list[SubtitleTrack] = field(default_factory=list)
    is_master: bool = True


@dataclass
class HlsSegment:
    """Segmento de un manifiesto de medios HLS."""

    url: str
    duration: float = 0.0


@dataclass
class HlsMediaPlaylist:
    """Manifiesto de medios HLS (lista de segmentos)."""

    segments: list[HlsSegment] = field(default_factory=list)
    init_uri: str = ""
    duration: float = 0.0
    encrypted: bool = False
    encryption_method: str = ""
    is_live: bool = False


def parse_media_playlist(text: str, base_url: str = "") -> HlsMediaPlaylist:
    """Interpreta un manifiesto de medios HLS (lista de segmentos)."""

    playlist = HlsMediaPlaylist()
    pending_duration = 0.0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            value = line[len("#EXTINF:") :].split(",")[0].strip()
            try:
                pending_duration = float(value)
            except ValueError:
                pending_duration = 0.0
        elif line.startswith("#EXT-X-KEY:"):
            attrs = _parse_attributes(line[len("#EXT-X-KEY:") :])
            method = attrs.get("METHOD", "").upper()
            if method and method != "NONE":
                playlist.encrypted = True
                playlist.encryption_method = method
        elif line.startswith("#EXT-X-MAP:"):
            attrs = _parse_attributes(line[len("#EXT-X-MAP:") :])
            uri = attrs.get("URI", "")
            if uri:
                playlist.init_uri = urljoin(base_url, uri)
        elif line.startswith("#EXT-X-ENDLIST"):
            playlist.is_live = False
        elif not line.startswith("#"):
            playlist.segments.append(
                HlsSegment(url=urljoin(base_url, line), duration=pending_duration)
            )
            playlist.duration += pending_duration
            pending_duration = 0.0
    return playlist


def _parse_attributes(line: str) -> dict[str, str]:
    """Extrae los atributos ATTR=VALOR de una linea EXT-X."""

    attributes: dict[str, str] = {}
    # Separa respetando valores entre comillas.
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == "," and not in_quotes:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))

    for part in parts:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        attributes[key.strip().upper()] = value.strip().strip('"')
    return attributes


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_master(text: str, base_url: str = "") -> HlsMaster:
    """Interpreta un manifiesto HLS y devuelve sus variantes y pistas."""

    master = HlsMaster()
    lines = [line.strip() for line in text.splitlines()]
    found_stream_inf = False

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#EXT-X-MEDIA:"):
            attrs = _parse_attributes(line[len("#EXT-X-MEDIA:") :])
            media_type = attrs.get("TYPE", "").upper()
            uri = attrs.get("URI")
            resolved = urljoin(base_url, uri) if uri else ""
            if media_type == "AUDIO" and resolved:
                master.audio_renditions.append(
                    MediaVariant(
                        url=resolved,
                        is_audio_only=True,
                        codecs=attrs.get("CODECS", ""),
                    )
                )
            elif media_type == "SUBTITLES" and resolved:
                master.subtitle_renditions.append(
                    SubtitleTrack(
                        url=resolved,
                        label=attrs.get("NAME", "") or attrs.get("LANGUAGE", ""),
                        language=attrs.get("LANGUAGE", ""),
                        kind="captions",
                        is_default=attrs.get("DEFAULT", "").upper() == "YES",
                    )
                )
        elif line.startswith("#EXT-X-STREAM-INF:"):
            found_stream_inf = True
            attrs = _parse_attributes(line[len("#EXT-X-STREAM-INF:") :])
            width = height = None
            resolution = attrs.get("RESOLUTION", "")
            if "x" in resolution:
                w_str, _, h_str = resolution.partition("x")
                width, height = _to_int(w_str), _to_int(h_str)
            # La URI es la siguiente linea no comentada.
            uri = ""
            lookahead = index + 1
            while lookahead < len(lines):
                if lines[lookahead] and not lines[lookahead].startswith("#"):
                    uri = lines[lookahead]
                    break
                lookahead += 1
            if uri:
                master.variants.append(
                    MediaVariant(
                        url=urljoin(base_url, uri),
                        width=width,
                        height=height,
                        bandwidth=_to_int(attrs.get("BANDWIDTH") or attrs.get("AVERAGE-BANDWIDTH")),
                        codecs=attrs.get("CODECS", ""),
                        frame_rate=attrs.get("FRAME-RATE", ""),
                    )
                )
        index += 1

    if not found_stream_inf:
        # Manifiesto de medios: no se conoce la resolucion desde el indice.
        master.is_master = False
        master.variants.append(MediaVariant(url=base_url))

    return master
