"""Prueba de integracion manual (no forma parte de la suite rapida).

Descarga una parte real de un HLS, remultiplexa con FFmpeg y verifica con
FFprobe. Requiere conectividad y credenciales validas. Uso:

    python scripts/integration_check.py [tmdb_id] [segments]
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parmovies.analyzers.resolver import MediaResolver  # noqa: E402
from parmovies.analyzers.url_parser import parse_input  # noqa: E402
from parmovies.api.vimeus import VimeusClient  # noqa: E402
from parmovies.configuration.settings import AppSettings  # noqa: E402
from parmovies.downloaders.base import DownloadProgress  # noqa: E402
from parmovies.downloaders.hls_downloader import HlsDownloader  # noqa: E402
from parmovies.media import ffmpeg as ffmpeg_mod  # noqa: E402
from parmovies.media.formats import pick_variant  # noqa: E402

TEMP = Path(__file__).resolve().parents[1] / "temp" / "integration"


def main() -> int:
    tmdb = int(sys.argv[1]) if len(sys.argv) > 1 else 264420
    max_segments = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    settings = AppSettings.load()
    tools = ffmpeg_mod.locate()
    print(f"FFmpeg disponible: {tools.available}")

    cancel = threading.Event()

    def on_progress(p: DownloadProgress) -> None:
        if p.percent is not None:
            print(
                f"  {p.status.value:<12} {p.percent:5.1f}%  "
                f"{p.downloaded_bytes/1e6:6.2f} MB  {p.speed_bps/1e6:5.2f} MB/s",
                end="\r",
            )

    with VimeusClient(settings.api_key, settings.base_url) as client:
        resolver = MediaResolver(
            client,
            base_url=settings.base_url,
            trusted_domains=settings.trusted_domains,
            default_view_key=settings.view_key,
        )
        request = parse_input(f"https://vimeus.com/e/movie?tmdb={tmdb}", settings.trusted_domains)
        analysis = resolver.resolve(request)
        print(f"Contenido: {analysis.title} ({analysis.content_type})")
        variant = pick_variant(analysis.playback.variants, "480")
        print(f"Variante: {variant.resolution_label} bw={variant.bandwidth}")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        playback = analysis.playback
        if playback and playback.headers.get("Referer"):
            headers["Referer"] = playback.headers["Referer"]
            headers["Origin"] = "https://vimeos.net"
        TEMP.mkdir(parents=True, exist_ok=True)
        raw = TEMP / "raw.ts"
        downloader = HlsDownloader(headers=headers, retries=3, progress=on_progress, cancel=cancel)
        start = time.monotonic()
        result = downloader.download(
            variant.url, raw, temp_dir=TEMP / "cache", max_segments=max_segments
        )
        elapsed = time.monotonic() - start
        print()
        print(f"Descarga: {result.status.value} ({result.bytes_written/1e6:.2f} MB en {elapsed:.1f}s)")

    if not raw.exists() or raw.stat().st_size == 0:
        print("No se genero archivo parcial.")
        return 1

    final = TEMP / "verificado.mkv"
    remux = ffmpeg_mod.remux(tools, raw, final, container="mkv")
    print(f"Remux returncode: {remux.returncode if remux else None}")
    if remux and remux.returncode != 0:
        print(remux.stderr[-500:])
        return 1

    info = ffmpeg_mod.probe(tools, final)
    if info is None:
        print("FFprobe no pudo verificar el archivo.")
        return 1
    print("VERIFICADO:")
    print(f"  resolucion: {info.resolution}")
    print(f"  video: {info.video_codec}")
    print(f"  audio: {[a.codec for a in info.audio_streams]}")
    print(f"  duracion del fragmento: {info.duration_seconds}")
    print(f"  tamano: {info.size_bytes} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
