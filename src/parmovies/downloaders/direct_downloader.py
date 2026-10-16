"""Descarga progresiva directa de archivos multimedia (MP4, MKV, etc.).

Soporta reanudacion mediante peticiones ``Range`` cuando el servidor la ofrece.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx

from ..utilities.logging_setup import get_logger
from .base import (
    DownloadCancelled,
    DownloadProgress,
    DownloadResult,
    DownloadStatus,
    ProgressCallback,
)

_log = get_logger("direct")

_CHUNK = 256 * 1024


class DirectDownloader:
    """Descarga un archivo multimedia mediante HTTP con reanudacion."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        retries: int = 3,
        timeout: float = 60.0,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        self.headers = headers or {}
        self.retries = max(1, retries)
        self.timeout = timeout
        self._progress = progress
        self._cancel = cancel or threading.Event()

    def _emit(self, progress: DownloadProgress) -> None:
        if self._progress:
            try:
                self._progress(progress)
            except Exception:  # pragma: no cover
                pass

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("Descarga cancelada por el usuario.")

    def download(self, url: str, destination: Path) -> DownloadResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_suffix(destination.suffix + ".part")

        for attempt in range(1, self.retries + 1):
            self._check_cancel()
            try:
                result = self._attempt(url, part, destination)
                if result is not None:
                    return result
            except DownloadCancelled as exc:
                return DownloadResult(status=DownloadStatus.CANCELLED, error=str(exc))
            except (httpx.HTTPError, OSError) as exc:
                _log.warning("Fallo en la descarga directa (intento %s): %s", attempt, exc)
                if attempt < self.retries:
                    self._emit(
                        DownloadProgress(
                            status=DownloadStatus.RETRYING,
                            message=f"Reintentando descarga ({attempt}/{self.retries})",
                        )
                    )
                    time.sleep(min(2 ** attempt, 10))

        return DownloadResult(
            status=DownloadStatus.ERROR,
            error="No se pudo completar la descarga directa tras varios intentos.",
        )

    def _attempt(self, url: str, part: Path, destination: Path) -> DownloadResult | None:
        resume_from = part.stat().st_size if part.exists() else 0
        headers = dict(self.headers)
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"

        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            with client.stream("GET", url, headers=headers) as response:
                if response.status_code == 416:
                    # El archivo parcial ya esta completo.
                    part.replace(destination)
                    return DownloadResult(
                        status=DownloadStatus.COMPLETED,
                        output_path=destination,
                        bytes_written=destination.stat().st_size,
                    )
                response.raise_for_status()

                if response.status_code == 200 and resume_from:
                    resume_from = 0  # el servidor ignoro el Range

                total = None
                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdigit():
                    total = int(content_length) + resume_from

                downloaded = resume_from
                start = time.monotonic()
                mode = "ab" if resume_from else "wb"
                with open(part, mode) as handle:
                    for chunk in response.iter_bytes(_CHUNK):
                        self._check_cancel()
                        handle.write(chunk)
                        downloaded += len(chunk)
                        elapsed = max(time.monotonic() - start, 0.001)
                        speed = (downloaded - resume_from) / elapsed
                        percent = (downloaded / total * 100.0) if total else None
                        eta = ((total - downloaded) / speed) if (total and speed > 0) else None
                        self._emit(
                            DownloadProgress(
                                status=DownloadStatus.DOWNLOADING,
                                downloaded_bytes=downloaded,
                                total_bytes=total,
                                percent=percent,
                                speed_bps=speed,
                                eta_seconds=eta,
                                message="Descargando archivo",
                            )
                        )

        part.replace(destination)
        return DownloadResult(
            status=DownloadStatus.COMPLETED,
            output_path=destination,
            bytes_written=destination.stat().st_size,
        )
