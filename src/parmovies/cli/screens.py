"""Pantallas de la interfaz: analisis, progreso, listados e historial."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rich.console import Console, Group
from rich.text import Text
from rich.live import Live

from ..api.models import ListingPage, MediaAnalysis, MediaVariant
from ..downloaders.base import DownloadProgress, DownloadStatus
from ..history.history_store import HistoryEntry
from ..media.formats import sort_variants, spanish_kind
from ..version import APP_NAME
from . import widgets
from .theme import separator

_CODEC_NAMES = {
    "avc1": "H.264",
    "avc3": "H.264",
    "hvc1": "H.265",
    "hev1": "H.265",
    "av01": "AV1",
    "vp09": "VP9",
    "mp4a": "AAC",
    "ac-3": "AC-3",
    "ec-3": "E-AC-3",
    "opus": "Opus",
}


def codec_name(codecs: str) -> str:
    """Traduce un descriptor de codecs a nombres legibles."""

    if not codecs:
        return "desconocido"
    names: list[str] = []
    for token in codecs.split(","):
        prefix = token.strip().split(".")[0].lower()
        name = _CODEC_NAMES.get(prefix)
        if name and name not in names:
            names.append(name)
        elif not name and token.strip():
            names.append(token.strip())
    return " / ".join(names) if names else "desconocido"


def video_codec_name(variant: MediaVariant | None) -> str:
    """Devuelve solo el codec de video de una variante."""

    if variant is None or not variant.codecs:
        return "desconocido"
    parts = [p.strip() for p in variant.codecs.split(",")]
    for part in parts:
        prefix = part.split(".")[0].lower()
        if prefix in ("avc1", "avc3", "hvc1", "hev1", "av01", "vp09"):
            return codec_name(part)
    return codec_name(parts[0])


def estimate_size(variant: MediaVariant | None, duration_seconds: float | None) -> int | None:
    """Estima el tamano de descarga a partir del bitrate y la duracion."""

    if variant is None or not variant.bandwidth or not duration_seconds:
        return None
    return int(variant.bandwidth / 8 * duration_seconds)


def best_variant(analysis: MediaAnalysis) -> MediaVariant | None:
    if not analysis.playback:
        return None
    variants = sort_variants([v for v in analysis.playback.variants if not v.is_audio_only])
    return variants[0] if variants else None


def audio_description(analysis: MediaAnalysis) -> str:
    """Describe el audio disponible a partir de los servidores y el idioma."""

    labels: list[str] = []
    for embed in analysis.embeds:
        if embed.lang and embed.lang not in labels:
            labels.append(embed.lang)
    if not labels:
        return "desconocido"
    return " | ".join(labels)


def subtitle_description(analysis: MediaAnalysis) -> str:
    if not analysis.playback or not analysis.playback.subtitles:
        return "ninguno detectado"
    labels = []
    for track in analysis.playback.subtitles:
        label = track.label or track.language or "desconocido"
        if label not in labels:
            labels.append(label)
    return ", ".join(labels)


def render_analysis(console: Console, analysis: MediaAnalysis) -> None:
    """Muestra la pantalla de analisis de contenido."""

    variant = best_variant(analysis)
    duration = analysis.playback.duration_seconds if analysis.playback else None
    size = estimate_size(variant, duration)

    console.print()
    console.print("  [pm.title]ANALISIS DE CONTENIDO[/pm.title]")
    separator(console, min(console.width, 62))
    console.print()

    rows = [
        ("Titulo", analysis.title or "desconocido"),
        ("Tipo", analysis.request.describe_kind()),
    ]
    if analysis.request.tmdb_id:
        rows.append(("TMDb", str(analysis.request.tmdb_id)))
    if analysis.request.imdb_id:
        rows.append(("IMDb", analysis.request.imdb_id))
    rows.append(("Resolucion", variant.resolution_label if variant else "desconocida"))
    rows.append(("Video", video_codec_name(variant)))
    rows.append(("Audio", audio_description(analysis)))
    rows.append(("Subtitulos", subtitle_description(analysis)))
    rows.append(
        ("Duracion", widgets.format_duration(duration) if duration else "desconocida")
    )
    rows.append(
        ("Tamano", f"~{widgets.format_bytes(size)} (estimado)" if size else "desconocido")
    )
    rows.append(("Servidores", ", ".join(e.server for e in analysis.embeds) or "ninguno"))

    for label, value in rows:
        console.print(f"  [pm.label]{label:<13}[/pm.label] [pm.value]{value}[/pm.value]")

    console.print()
    if not analysis.is_downloadable:
        widgets.warn(console, "No se detecto una fuente multimedia descargable compatible.")
    separator(console, min(console.width, 62))
    console.print()


def render_variants(console: Console, analysis: MediaAnalysis) -> list[MediaVariant]:
    """Muestra las calidades reales disponibles y las devuelve ordenadas."""

    variants = sort_variants(
        [v for v in (analysis.playback.variants if analysis.playback else []) if not v.is_audio_only]
    )
    if not variants:
        return []
    console.print("  [pm.soft]Calidades disponibles (reales):[/pm.soft]")
    for index, variant in enumerate(variants, start=1):
        bitrate = f"{variant.bandwidth // 1000} kbps" if variant.bandwidth else "bitrate desconocido"
        console.print(
            f"  [pm.menu.key][{index:02d}][/pm.menu.key]  "
            f"[pm.menu.item]{variant.resolution_label:<11} {bitrate:<18} "
            f"{codec_name(variant.codecs)}[/pm.menu.item]"
        )
    console.print()
    return variants


def render_listing(console: Console, page: ListingPage, *, title: str) -> None:
    """Muestra una pagina de resultados de un listado."""

    console.print()
    console.print(f"  [pm.title]{title}[/pm.title]")
    separator(console, min(console.width, 62))
    if not page.items:
        widgets.warn(console, "No hay resultados en esta pagina.")
        return

    table = widgets.build_table("#", "Titulo", "Tipo", "Calidad", "TMDb")
    for index, item in enumerate(page.items, start=1):
        item_type = item.content_type or ("Serie" if item.parent_type else "--")
        table.add_row(
            f"{index:02d}",
            item.display_title[:54],
            item_type[:10],
            (item.quality or "--")[:10],
            str(item.tmdb_id or "--"),
        )
    console.print(table)
    widgets.dim(
        console,
        f"Pagina {page.current_page} de {page.total_pages}"
        + (f"  ·  {page.total_results} resultados" if page.total_results else ""),
    )


def render_history(console: Console, entries: list[HistoryEntry]) -> None:
    """Muestra el historial de descargas."""

    console.print()
    console.print("  [pm.title]MIS DESCARGAS[/pm.title]")
    separator(console, min(console.width, 62))
    if not entries:
        widgets.dim(console, "Todavia no hay descargas registradas.")
        return
    table = widgets.build_table("#", "Titulo", "Fecha", "Tamano", "Calidad", "Estado")
    for index, entry in enumerate(entries, start=1):
        table.add_row(
            f"{index:02d}",
            entry.title[:40],
            (entry.downloaded_at or "")[:16].replace("T", " "),
            widgets.format_bytes(entry.size_bytes),
            (entry.quality or entry.resolution or "--")[:12],
            (entry.status or "--")[:12],
        )
    console.print(table)


@dataclass
class ProgressContext:
    """Datos estaticos que acompanan a la pantalla de progreso."""

    title: str = ""
    filename: str = ""
    resolution: str = "desconocida"
    container: str = "mkv"
    audio: str = "desconocido"


class ProgressDisplay:
    """Pantalla de progreso que actualiza solo su propia seccion."""

    def __init__(self, console: Console, context: ProgressContext) -> None:
        self.console = console
        self.context = context
        self._live = Live(console=console, refresh_per_second=10, transient=False)
        self._last_update = 0.0
        self._progress = DownloadProgress()

    def __enter__(self) -> "ProgressDisplay":
        self._live.start()
        self._live.update(self._render())
        return self

    def __exit__(self, *exc: object) -> None:
        self._live.update(self._render())
        self._live.stop()

    def update(self, progress: DownloadProgress) -> None:
        """Actualiza el estado mostrado (limitado para evitar parpadeos)."""

        self._progress = progress
        now = time.monotonic()
        force = progress.status != DownloadStatus.DOWNLOADING
        if force or (now - self._last_update) >= 0.1:
            self._last_update = now
            self._live.update(self._render())

    def _render(self) -> Group:
        p = self._progress
        lines: list[Text] = []
        lines.append(Text.from_markup("  [pm.title]DESCARGA[/pm.title]"))
        lines.append(Text.from_markup("[pm.rule]" + "-" * min(self.console.width, 62) + "[/pm.rule]"))
        lines.append(Text(""))
        lines.append(Text.from_markup(f"  [pm.label]Archivo    [/pm.label] [pm.value]{self.context.filename}[/pm.value]"))
        lines.append(Text.from_markup(f"  [pm.label]Titulo     [/pm.label] [pm.value]{self.context.title}[/pm.value]"))
        lines.append(Text.from_markup(f"  [pm.label]Resolucion [/pm.label] [pm.value]{self.context.resolution}[/pm.value]"))
        lines.append(Text.from_markup(f"  [pm.label]Formato    [/pm.label] [pm.value]{self.context.container}[/pm.value]"))
        lines.append(Text.from_markup(f"  [pm.label]Audio      [/pm.label] [pm.value]{self.context.audio}[/pm.value]"))
        lines.append(Text(""))

        bar = widgets.render_bar(p.percent, width=30)
        percent_text = f"{p.percent:5.1f}%" if p.percent is not None else "  --.-%"
        lines.append(Text.from_markup(f"  {bar} [pm.text]{percent_text}[/pm.text]"))
        lines.append(Text(""))

        total = widgets.format_bytes(p.total_bytes) if p.total_bytes else "desconocido"
        lines.append(
            Text.from_markup(
                f"  [pm.label]Descargado [/pm.label] [pm.value]{widgets.format_bytes(p.downloaded_bytes)}"
                f" / {total}[/pm.value]"
            )
        )
        lines.append(Text.from_markup(f"  [pm.label]Velocidad  [/pm.label] [pm.value]{widgets.format_speed(p.speed_bps)}[/pm.value]"))
        lines.append(Text.from_markup(f"  [pm.label]Restante   [/pm.label] [pm.value]{widgets.format_eta(p.eta_seconds)}[/pm.value]"))
        lines.append(Text(""))
        lines.append(Text.from_markup(f"  [pm.label]Estado     [/pm.label] [pm.value]{p.status.value}[/pm.value] [pm.dim]{p.message}[/pm.dim]"))
        return Group(*lines)
