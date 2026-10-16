"""Motor de descargas: orquesta descarga, muxing, subtitulos y verificacion."""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..api.models import MediaAnalysis, MediaVariant, SubtitleTrack
from ..configuration.settings import AppSettings
from ..media import ffmpeg as ffmpeg_mod
from ..metadata.metadata_writer import build_info, write_info_json
from ..subtitles.subtitle_manager import save_subtitle
from ..utilities import paths as path_utils
from ..utilities.logging_setup import get_logger
from ..utilities.organizer import build_output_path
from .base import (
    DownloadProgress,
    DownloadResult,
    DownloadStatus,
    ProgressCallback,
)
from .direct_downloader import DirectDownloader
from .hls_downloader import HlsDownloader

_log = get_logger("engine")


@dataclass
class DownloadTask:
    """Descripcion completa de una descarga a realizar."""

    analysis: MediaAnalysis
    variant: MediaVariant
    output_path: Path
    subtitle_tracks: list[SubtitleTrack] = field(default_factory=list)
    download_subtitles: bool = True
    embed_subtitles: bool = False
    write_metadata: bool = True
    audio_language: str = ""
    original_language: str = ""
    exists_strategy: str = "rename"  # rename | skip | overwrite
    year: int | None = None


class DownloadEngine:
    """Ejecuta tareas de descarga de principio a fin."""

    def __init__(
        self,
        settings: AppSettings,
        tools: ffmpeg_mod.FfmpegTools,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        self.settings = settings
        self.tools = tools
        self._progress = progress
        self._cancel = cancel or threading.Event()

    # -- Progreso ----------------------------------------------------------
    def _emit(self, event: DownloadProgress) -> None:
        if self._progress:
            try:
                self._progress(event)
            except Exception:  # pragma: no cover
                pass

    def _cancelled(self) -> bool:
        return self._cancel.is_set()

    # -- API principal -----------------------------------------------------
    def run(self, task: DownloadTask) -> DownloadResult:
        output_path = self._resolve_output(task)
        if output_path is None:
            return DownloadResult(
                status=DownloadStatus.COMPLETED,
                message="El archivo ya existe; se omitio la descarga.",
            )

        container = self.settings.output_format
        temp_root = path_utils.ensure_dir(path_utils.project_root() / "temp")
        temp_dir = temp_root / path_utils.sanitize_component(output_path.stem, max_length=40)
        path_utils.ensure_dir(temp_dir)

        raw_path = self._download_source(task, temp_dir)
        if isinstance(raw_path, DownloadResult):
            return raw_path

        self._emit(DownloadProgress(status=DownloadStatus.PROCESSING, message="Preparando archivo final"))
        final_path = self._finalize(task, raw_path, output_path, container)
        if isinstance(final_path, DownloadResult):
            return final_path

        if not self.settings.keep_temp_files:
            shutil.rmtree(temp_dir, ignore_errors=True)

        subtitle_files = self._save_subtitles(task, final_path)

        info_file = None
        if task.write_metadata:
            media_info_pre = ffmpeg_mod.probe(self.tools, final_path)
            info = build_info(
                task.analysis,
                variant=task.variant,
                subtitles=task.subtitle_tracks,
                media_info=media_info_pre,
                output_path=final_path,
                audio_language=task.audio_language,
            )
            info_file = write_info_json(final_path.parent, info)

        verified, media_info = self._verify(final_path)
        size = final_path.stat().st_size if final_path.exists() else 0
        status = DownloadStatus.COMPLETED
        message = "Descarga completada y verificada" if verified else "Descarga completada"
        if not self.tools.available:
            message += " (sin FFmpeg: no se pudo verificar con FFprobe)"

        return DownloadResult(
            status=status,
            output_path=final_path,
            bytes_written=size,
            message=message,
            verified=verified,
            media_info=media_info,
            subtitle_files=subtitle_files,
            info_file=info_file,
        )

    # -- Pasos internos ----------------------------------------------------
    def _resolve_output(self, task: DownloadTask) -> Path | None:
        path = task.output_path
        if not path.exists():
            return path
        if task.exists_strategy == "skip":
            return None
        if task.exists_strategy == "overwrite":
            return path
        return path_utils.unique_path(path)

    def _client_headers(self, task: DownloadTask) -> dict[str, str]:
        headers = {"User-Agent": _BROWSER_UA}
        playback = task.analysis.playback
        if playback and playback.headers.get("Referer"):
            headers["Referer"] = playback.headers["Referer"]
            headers["Origin"] = _origin_of(playback.headers["Referer"])
        return headers

    def _download_source(self, task: DownloadTask, temp_dir: Path) -> Path | DownloadResult:
        url = task.variant.url
        headers = self._client_headers(task)
        is_hls = ".m3u8" in url.lower()

        if is_hls:
            raw = temp_dir / "raw.ts"
            downloader = HlsDownloader(
                headers=headers,
                retries=self.settings.retries,
                speed_limit_kib=self.settings.speed_limit_kib,
                progress=self._progress,
                cancel=self._cancel,
                resume=True,
            )
            result = downloader.download(
                url,
                raw,
                temp_dir=temp_dir,
                total_duration_hint=None,
            )
            if result.status != DownloadStatus.COMPLETED or result.output_path is None:
                return result
            return result.output_path

        # Descarga progresiva directa.
        raw = temp_dir / f"raw{suffix_for(url)}"
        downloader = DirectDownloader(
            headers=headers,
            retries=self.settings.retries,
            progress=self._progress,
            cancel=self._cancel,
        )
        result = downloader.download(url, raw)
        if result.status != DownloadStatus.COMPLETED or result.output_path is None:
            return result
        return result.output_path

    def _finalize(
        self, task: DownloadTask, raw_path: Path, output_path: Path, container: str
    ) -> Path | DownloadResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.tools.has_ffmpeg:
            metadata_args = self._metadata_args(task)
            extra = list(metadata_args)
            result = ffmpeg_mod.remux(
                self.tools,
                raw_path,
                output_path,
                container=container,
                extra_args=extra,
            )
            if result is None or result.returncode != 0:
                detail = (result.stderr[-400:] if result and result.stderr else "sin detalle")
                _log.warning("FFmpeg fallo al remultiplexar: %s", detail)
                # Sin remux, se conserva el archivo original si es reproducible.
                fallback = output_path.with_suffix(raw_path.suffix)
                shutil.move(str(raw_path), str(fallback))
                return fallback
            return output_path

        # Sin FFmpeg: se conserva el contenedor original.
        target_suffix = output_path.suffix.lstrip(".")
        raw_suffix = raw_path.suffix.lstrip(".")
        if raw_suffix and raw_suffix != target_suffix:
            fallback = output_path.with_suffix(f".{raw_suffix}")
            shutil.move(str(raw_path), str(fallback))
            return fallback
        shutil.move(str(raw_path), str(output_path))
        return output_path

    def _metadata_args(self, task: DownloadTask) -> list[str]:
        args: list[str] = []
        title = task.analysis.title
        request = task.analysis.request
        if title:
            args += ["-metadata", f"title={title}"]
        if request.season is not None and request.episode is not None:
            args += ["-metadata", f"comment=Temporada {request.season} Episodio {request.episode}"]
        if task.audio_language:
            args += ["-metadata:s:a:0", f"language={_iso_language(task.audio_language)}"]
        return args

    def _save_subtitles(self, task: DownloadTask, final_path: Path) -> list[Path]:
        if not task.download_subtitles or not task.subtitle_tracks:
            return []
        headers = self._client_headers(task)
        saved: list[Path] = []
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            for track in task.subtitle_tracks:
                if self._cancelled():
                    break
                try:
                    response = client.get(track.url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    _log.warning("No se pudo descargar el subtitulo: %s", exc)
                    continue
                path = save_subtitle(track, response.text, final_path)
                if path:
                    saved.append(path)
        return saved

    def _verify(self, final_path: Path) -> tuple[bool, ffmpeg_mod.MediaInfo | None]:
        self._emit(DownloadProgress(status=DownloadStatus.VERIFYING, message="Verificando archivo"))
        if not final_path.exists() or final_path.stat().st_size == 0:
            return False, None
        info = ffmpeg_mod.probe(self.tools, final_path)
        if info is None:
            # Sin FFprobe no se puede verificar la integridad real.
            return False, None
        has_video = bool(info.video_codec)
        return has_video, info


def _origin_of(url: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return ""


def _iso_language(language: str) -> str:
    """Normaliza un idioma a un codigo ISO-639 utilizable por FFmpeg."""

    value = (language or "").strip().lower()
    if not value:
        return "und"
    if value.startswith("es"):
        return "spa"
    if value.startswith("en"):
        return "eng"
    if value.startswith("pt"):
        return "por"
    if value.startswith("fr"):
        return "fra"
    if value.startswith("de"):
        return "deu"
    return value[:3] if value.isalpha() else "und"


def suffix_for(url: str) -> str:
    """Deduce la extension de un enlace directo."""

    lowered = url.split("?")[0].lower()
    for ext in (".mp4", ".mkv", ".webm", ".m4v", ".avi", ".mov"):
        if lowered.endswith(ext):
            return ext
    return ".mp4"


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def make_task(
    settings: AppSettings,
    analysis: MediaAnalysis,
    variant: MediaVariant,
    *,
    subtitle_tracks: list[SubtitleTrack] | None = None,
    audio_language: str = "",
    year: int | None = None,
    exists_strategy: str = "rename",
) -> DownloadTask:
    """Construye una tarea de descarga con la ruta organizada."""

    output = build_output_path(
        settings.resolved_downloads_dir(),
        analysis,
        height=variant.height,
        year=year,
        audio_language=audio_language,
        container=settings.output_format,
    )
    return DownloadTask(
        analysis=analysis,
        variant=variant,
        output_path=output,
        subtitle_tracks=subtitle_tracks or [],
        download_subtitles=settings.subtitle_mode != "none" and bool(subtitle_tracks),
        embed_subtitles=False,
        write_metadata=settings.download_metadata,
        audio_language=audio_language,
        exists_strategy=exists_strategy,
        year=year,
    )
