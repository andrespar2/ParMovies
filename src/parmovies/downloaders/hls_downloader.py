"""Descargador HLS nativo (sin dependencias externas obligatorias).

Permite descargar manifiestos HLS accesibles de forma autorizada, con
reanudacion de segmentos, reintentos, cancelacion segura y control opcional de
velocidad. No descifra contenido protegido: si el manifiesto declara cifrado se
detiene y se informa al usuario.
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import httpx

from ..media.hls import parse_media_playlist
from ..utilities.logging_setup import get_logger
from .base import (
    DownloadCancelled,
    DownloadProgress,
    DownloadResult,
    DownloadStatus,
    ProgressCallback,
)

_log = get_logger("hls")

_CHUNK = 256 * 1024


class HlsDownloader:
    """Descarga un manifiesto HLS a un archivo contenedor local."""

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        retries: int = 3,
        timeout: float = 30.0,
        speed_limit_kib: int = 0,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
        resume: bool = True,
    ) -> None:
        self.headers = headers or {}
        self.retries = max(1, retries)
        self.timeout = timeout
        self.speed_limit_bps = max(0, speed_limit_kib) * 1024
        self._progress = progress
        self._cancel = cancel or threading.Event()
        self.resume = resume

    # -- Emision de progreso ----------------------------------------------
    def _emit(self, progress: DownloadProgress) -> None:
        if self._progress:
            try:
                self._progress(progress)
            except Exception:  # pragma: no cover - la UI nunca debe romper la descarga
                pass

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("Descarga cancelada por el usuario.")

    # -- Descarga ----------------------------------------------------------
    def download(
        self,
        media_url: str,
        destination: Path,
        *,
        temp_dir: Path,
        total_duration_hint: float | None = None,
    ) -> DownloadResult:
        """Descarga el manifiesto y escribe el archivo resultante."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        cache_dir = temp_dir / hashlib.sha1(media_url.encode("utf-8")).hexdigest()[:16]
        cache_dir.mkdir(parents=True, exist_ok=True)

        client = httpx.Client(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        )
        try:
            self._emit(
                DownloadProgress(status=DownloadStatus.PREPARING, message="Leyendo manifiesto")
            )
            playlist = self._load_playlist(client, media_url)
            if playlist.encrypted:
                return DownloadResult(
                    status=DownloadStatus.ERROR,
                    error=(
                        "El manifiesto usa cifrado "
                        f"({playlist.encryption_method}); ParMovies no descifra contenido protegido."
                    ),
                )
            if not playlist.segments:
                return DownloadResult(
                    status=DownloadStatus.ERROR,
                    error="El manifiesto HLS no contiene segmentos descargables.",
                )

            total_duration = total_duration_hint or playlist.duration
            downloaded_bytes = 0
            downloaded_duration = 0.0
            start = time.monotonic()

            if playlist.init_uri:
                self._fetch_segment(client, playlist.init_uri, cache_dir / "init.seg")

            for index, segment in enumerate(playlist.segments):
                self._check_cancel()
                target = cache_dir / f"seg_{index:06d}.seg"
                if self.resume and target.is_file() and target.stat().st_size > 0:
                    downloaded_bytes += target.stat().st_size
                    downloaded_duration += segment.duration
                    self._emit_progress(
                        downloaded_bytes, downloaded_duration, total_duration, start, index, len(playlist.segments)
                    )
                    continue

                self._fetch_segment(client, segment.url, target)
                downloaded_bytes += target.stat().st_size
                downloaded_duration += segment.duration
                self._emit_progress(
                    downloaded_bytes, downloaded_duration, total_duration, start, index, len(playlist.segments)
                )
                if self.speed_limit_bps:
                    self._throttle(downloaded_bytes, start)

            self._check_cancel()
            self._emit(
                DownloadProgress(
                    status=DownloadStatus.PROCESSING,
                    message="Combinando segmentos",
                    downloaded_bytes=downloaded_bytes,
                )
            )
            self._concatenate(playlist.init_uri, playlist.segments, cache_dir, destination)
            size = destination.stat().st_size
            return DownloadResult(
                status=DownloadStatus.COMPLETED,
                output_path=destination,
                bytes_written=size,
                message="Descarga HLS completada",
            )
        except DownloadCancelled as exc:
            return DownloadResult(status=DownloadStatus.CANCELLED, error=str(exc))
        except httpx.HTTPError as exc:
            _log.warning("Error de red en la descarga HLS: %s", exc)
            return DownloadResult(
                status=DownloadStatus.ERROR,
                error=f"Error de red durante la descarga: {exc}",
            )
        finally:
            client.close()

    # -- Interno -----------------------------------------------------------
    def _load_playlist(self, client: httpx.Client, media_url: str):
        text = self._get_text(client, media_url)
        return parse_media_playlist(text, base_url=media_url)

    def _get_text(self, client: httpx.Client, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._check_cancel()
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.retries:
                    self._emit(
                        DownloadProgress(
                            status=DownloadStatus.RETRYING,
                            message=f"Reintentando manifiesto ({attempt}/{self.retries})",
                        )
                    )
                    time.sleep(min(2 ** attempt, 8))
        raise last_error if last_error else RuntimeError("Fallo al leer el manifiesto")

    def _fetch_segment(self, client: httpx.Client, url: str, target: Path) -> None:
        part = target.with_suffix(target.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._check_cancel()
            try:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(part, "wb") as handle:
                        for chunk in response.iter_bytes(_CHUNK):
                            self._check_cancel()
                            handle.write(chunk)
                part.replace(target)
                return
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if part.exists():
                    try:
                        part.unlink()
                    except OSError:
                        pass
                if attempt < self.retries:
                    self._emit(
                        DownloadProgress(
                            status=DownloadStatus.RETRYING,
                            message=f"Reintentando segmento ({attempt}/{self.retries})",
                        )
                    )
                    time.sleep(min(2 ** attempt, 8))
        if self._cancel.is_set():
            raise DownloadCancelled("Descarga cancelada por el usuario.")
        raise last_error if last_error else RuntimeError("Fallo al descargar un segmento")

    def _concatenate(self, init_uri: str, segments, cache_dir: Path, destination: Path) -> None:
        part = destination.with_suffix(destination.suffix + ".part")
        with open(part, "wb") as output:
            if init_uri:
                init_file = cache_dir / "init.seg"
                if init_file.is_file():
                    output.write(init_file.read_bytes())
            for index, _segment in enumerate(segments):
                seg_file = cache_dir / f"seg_{index:06d}.seg"
                if seg_file.is_file():
                    output.write(seg_file.read_bytes())
        part.replace(destination)

    def _emit_progress(
        self,
        downloaded_bytes: int,
        downloaded_duration: float,
        total_duration: float,
        start: float,
        index: int,
        count: int,
    ) -> None:
        elapsed = max(time.monotonic() - start, 0.001)
        speed = downloaded_bytes / elapsed
        percent = None
        eta = None
        total_bytes = None
        if total_duration > 0 and downloaded_duration > 0:
            percent = min(100.0, downloaded_duration / total_duration * 100.0)
            if speed > 0:
                eta = (total_duration - downloaded_duration) / (downloaded_duration / elapsed)
            total_bytes = int(downloaded_bytes * total_duration / downloaded_duration)
        self._emit(
            DownloadProgress(
                status=DownloadStatus.DOWNLOADING,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                percent=percent,
                speed_bps=speed,
                eta_seconds=eta,
                message=f"Segmento {index + 1} de {count}",
            )
        )

    def _throttle(self, downloaded_bytes: int, start: float) -> None:
        elapsed = time.monotonic() - start
        expected = downloaded_bytes / self.speed_limit_bps
        if expected > elapsed:
            delay = expected - elapsed
            # Respeta la cancelacion durante las esperas largas.
            waited = 0.0
            while waited < delay:
                self._check_cancel()
                step = min(0.25, delay - waited)
                time.sleep(step)
                waited += step
