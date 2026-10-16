"""Integracion segura con FFmpeg y FFprobe.

Todas las ejecuciones se realizan con listas de argumentos (sin ``shell=True``)
y con tiempo de espera. La deteccion de las herramientas tolera entornos donde
los binarios no pueden ejecutarse (por ejemplo, manifiestos que exigen
elevacion), devolviendo que no estan disponibles en lugar de fallar.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..utilities import paths
from ..utilities.logging_setup import get_logger

_log = get_logger("ffmpeg")

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class AudioStreamInfo:
    """Informacion de una pista de audio."""

    index: int
    codec: str = ""
    channels: int | None = None
    language: str = ""
    title: str = ""
    bit_rate: int | None = None


@dataclass
class MediaInfo:
    """Resumen verificable de un archivo multimedia."""

    path: str = ""
    duration_seconds: float | None = None
    size_bytes: int = 0
    format_name: str = ""
    video_codec: str = ""
    width: int | None = None
    height: int | None = None
    audio_streams: list[AudioStreamInfo] = field(default_factory=list)
    subtitle_streams: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "desconocida"


@dataclass
class FfmpegTools:
    """Conjunto de herramientas multimedia detectadas."""

    ffmpeg: Path | None = None
    ffprobe: Path | None = None

    @property
    def has_ffmpeg(self) -> bool:
        return self.ffmpeg is not None

    @property
    def has_ffprobe(self) -> bool:
        return self.ffprobe is not None

    @property
    def available(self) -> bool:
        return self.has_ffmpeg and self.has_ffprobe


def _can_execute(path: Path, args: list[str]) -> bool:
    """Comprueba que un binario puede ejecutarse en este entorno."""

    try:
        result = subprocess.run(
            [str(path), *args],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Incluye WinError 740 (elevacion requerida) y binarios incompatibles.
        _log.warning("No se pudo ejecutar %s: %s", path, exc)
        return False
    return result.returncode == 0


def locate(configured_dir: Path | None = None) -> FfmpegTools:
    """Localiza ffmpeg y ffprobe en el bin incluido, la configuracion o el PATH."""

    tools = FfmpegTools()

    def resolve(name: str) -> Path | None:
        exe = f"{name}.exe" if sys.platform == "win32" else name
        candidates: list[Path] = []
        if configured_dir:
            candidates.append(Path(configured_dir) / exe)
            candidates.append(Path(configured_dir))
        candidates.append(paths.bin_dir() / exe)
        on_path = shutil.which(exe) or shutil.which(name)
        if on_path:
            candidates.append(Path(on_path))
        for candidate in candidates:
            if candidate.is_file() and _can_execute(candidate, ["-version"]):
                return candidate
        return None

    tools.ffmpeg = resolve("ffmpeg")
    tools.ffprobe = resolve("ffprobe")
    if not tools.has_ffmpeg:
        _log.warning("FFmpeg no disponible o no ejecutable.")
    if not tools.has_ffprobe:
        _log.warning("FFprobe no disponible o no ejecutable.")
    return tools


def run(args: list[str], *, timeout: float = 600.0) -> subprocess.CompletedProcess:
    """Ejecuta un proceso externo de forma segura."""

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )


def probe(tools: FfmpegTools, path: str | Path, *, timeout: float = 60.0) -> MediaInfo | None:
    """Inspecciona un archivo con FFprobe y devuelve un resumen verificado."""

    if not tools.has_ffprobe:
        return None
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return None
    args = [
        str(tools.ffprobe),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("FFprobe fallo: %s", exc)
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return _summarize(file_path, payload)


def _summarize(path: Path, payload: dict) -> MediaInfo:
    fmt = payload.get("format", {}) if isinstance(payload, dict) else {}
    streams = payload.get("streams", []) if isinstance(payload, dict) else []
    info = MediaInfo(path=str(path), raw=payload)
    try:
        info.duration_seconds = float(fmt.get("duration")) if fmt.get("duration") else None
    except (TypeError, ValueError):
        info.duration_seconds = None
    try:
        info.size_bytes = int(fmt.get("size") or path.stat().st_size)
    except (TypeError, ValueError):
        info.size_bytes = path.stat().st_size
    info.format_name = str(fmt.get("format_name") or "")

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not info.video_codec:
            info.video_codec = str(stream.get("codec_name") or "")
            info.width = stream.get("width")
            info.height = stream.get("height")
        elif codec_type == "audio":
            tags = stream.get("tags", {}) or {}
            info.audio_streams.append(
                AudioStreamInfo(
                    index=int(stream.get("index", 0)),
                    codec=str(stream.get("codec_name") or ""),
                    channels=stream.get("channels"),
                    language=str(tags.get("language") or ""),
                    title=str(tags.get("title") or ""),
                    bit_rate=stream.get("bit_rate") and int(stream["bit_rate"]),
                )
            )
        elif codec_type == "subtitle":
            tags = stream.get("tags", {}) or {}
            info.subtitle_streams.append(
                {
                    "index": int(stream.get("index", 0)),
                    "codec": str(stream.get("codec_name") or ""),
                    "language": str(tags.get("language") or ""),
                    "title": str(tags.get("title") or ""),
                }
            )
    return info


def build_header_block(headers: dict[str, str]) -> str:
    """Construye el valor del argumento ``-headers`` de FFmpeg."""

    lines = [f"{key}: {value}\r\n" for key, value in headers.items() if value]
    return "".join(lines)


def remux(
    tools: FfmpegTools,
    source: str | Path,
    destination: str | Path,
    *,
    container: str = "mkv",
    headers: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
    timeout: float = 3600.0,
) -> subprocess.CompletedProcess | None:
    """Remultiplexa sin recodificar cuando es posible."""

    if not tools.has_ffmpeg:
        return None
    args = [str(tools.ffmpeg), "-y", "-hide_banner", "-loglevel", "error"]
    if headers:
        args += ["-headers", build_header_block(headers)]
    args += ["-i", str(source), "-c", "copy"]
    if container == "mp4":
        args += ["-bsf:a", "aac_adtstoasc"]
    if extra_args:
        args += extra_args
    args.append(str(destination))
    return run(args, timeout=timeout)


def download_with_ffmpeg(
    tools: FfmpegTools,
    url: str,
    destination: str | Path,
    *,
    container: str = "mkv",
    headers: dict[str, str] | None = None,
    timeout: float = 7200.0,
) -> subprocess.CompletedProcess | None:
    """Descarga un manifiesto HLS directamente con FFmpeg (sin recodificar)."""

    if not tools.has_ffmpeg:
        return None
    args = [str(tools.ffmpeg), "-y", "-hide_banner", "-loglevel", "error"]
    if headers:
        args += ["-headers", build_header_block(headers)]
    args += ["-i", url, "-c", "copy"]
    if container == "mp4":
        args += ["-bsf:a", "aac_adtstoasc"]
    args.append(str(destination))
    return run(args, timeout=timeout)
