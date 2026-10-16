"""Estructuras comunes del motor de descargas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from ..media.ffmpeg import MediaInfo


class DownloadStatus(str, Enum):
    """Estados posibles de una descarga."""

    ANALYZING = "Analizando"
    PREPARING = "Preparando"
    DOWNLOADING = "Descargando"
    RETRYING = "Reintentando"
    PROCESSING = "Procesando"
    MUXING = "Combinando pistas"
    VERIFYING = "Verificando"
    COMPLETED = "Completado"
    CANCELLED = "Cancelado"
    ERROR = "Error"


@dataclass
class DownloadProgress:
    """Instantanea del progreso de una descarga."""

    status: DownloadStatus = DownloadStatus.PREPARING
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    percent: float | None = None
    speed_bps: float = 0.0
    eta_seconds: float | None = None
    message: str = ""
    filename: str = ""


@dataclass
class DownloadResult:
    """Resultado final de una descarga."""

    status: DownloadStatus
    output_path: Path | None = None
    bytes_written: int = 0
    message: str = ""
    verified: bool = False
    media_info: MediaInfo | None = None
    error: str | None = None
    subtitle_files: list[Path] = field(default_factory=list)
    info_file: Path | None = None

    @property
    def ok(self) -> bool:
        return self.status == DownloadStatus.COMPLETED


class DownloadCancelled(Exception):
    """Se lanza cuando el usuario cancela una descarga."""


ProgressCallback = Callable[[DownloadProgress], None]
