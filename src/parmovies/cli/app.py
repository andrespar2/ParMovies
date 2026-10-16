"""Menu principal e interfaz interactiva de ParMovies.

Este modulo es el punto de entrada de la aplicacion (``python -m parmovies`` o
el ejecutable portable). Ofrece un menu numerico con estetica Black Modern
AMOLED para analizar enlaces de Vimeus de forma autorizada, explorar los
listados de la API, descargar con verificacion real mediante FFprobe, revisar
el historial y ajustar la configuracion local.
"""

from __future__ import annotations

from contextlib import contextmanager
import sys
import threading
import time

from rich.console import Console

from ..analyzers.errors import AnalysisError
from ..analyzers.resolver import MediaResolver
from ..analyzers.url_parser import parse_input
from ..api.errors import VimeusError
from ..api.models import (
    ContentRequest,
    ListingItem,
    ListingPage,
    MediaAnalysis,
    MediaVariant,
    SubtitleTrack,
)
from ..api.vimeus import VimeusClient
from ..configuration.settings import AppSettings
from ..downloaders.base import (
    DownloadProgress,
    DownloadResult,
    DownloadStatus,
)
from ..downloaders.engine import DownloadEngine, make_task
from ..history.history_store import HistoryEntry, HistoryStore
from ..media import ffmpeg as ffmpeg_mod
from ..media.formats import (
    order_audio_labels,
    pick_variant,
    select_subtitles,
)
from ..utilities.logging_setup import configure_logging, log_path, update_secrets
from ..version import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_TAGLINE,
    DEVELOPERS,
    INTERFACE_STYLE,
    LICENSE_NAME,
    PLATFORM,
    REPOSITORY_URL,
    __version__,
)
from . import screens, widgets
from .art import render_header
from .theme import create_console, separator

_KIND_LABELS = {
    "movie": "Pelicula",
    "serie": "Serie",
    "anime": "Anime",
    "episode": "Episodio",
}

_LEGAL_NOTE = (
    "ParMovies solo debe usarse con contenido al que tengas derecho de acceso. "
    "No descifra protecciones ni elude controles de acceso tecnicos."
)


class ParMoviesApp:
    """Aplicacion interactiva de terminal."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or create_console()
        self.settings = AppSettings.load()
        configure_logging(
            enabled=self.settings.enable_logs,
            secrets=(self.settings.api_key, self.settings.view_key),
        )
        self.tools = ffmpeg_mod.locate(self.settings.resolved_ffmpeg_dir())
        self.history = HistoryStore()

    # -- Ciclo principal ---------------------------------------------------
    def run(self, initial_input: str | None = None) -> int:
        """Bucle principal del menu. Devuelve el codigo de salida."""

        try:
            if initial_input:
                return self._flow_analyze(initial_input)
            while True:
                self.console.clear()
                self._render_main_menu()
                choice = widgets.prompt_choice(self.console, "Elige una opcion")
                key = _normalize_key(choice)
                if key in ("0", "q", "salir"):
                    self.console.clear()
                    widgets.dim(self.console, "Hasta pronto.")
                    return 0
                self._dispatch_main(key)
        except KeyboardInterrupt:
            self.console.print()
            widgets.warn(self.console, "Operacion interrumpida por el usuario.")
            return 130

    def _dispatch_main(self, key: str) -> None:
        if key == "1":
            self._flow_analyze()
        elif key == "2":
            self._flow_search_id()
        elif key == "3":
            self._flow_listing("movies")
        elif key == "4":
            self._flow_listing("series")
        elif key == "5":
            self._flow_listing("animes")
        elif key == "6":
            self._flow_episode_search()
        elif key == "7":
            self._screen_history()
        elif key == "8":
            self._screen_settings()
        elif key == "9":
            self._screen_about()
        else:
            widgets.warn(self.console, "Opcion no reconocida.")

    # -- Pantallas estaticas ----------------------------------------------
    def _render_main_menu(self) -> None:
        render_header(self.console)
        self.console.print()
        widgets.dim(
            self.console,
            f"FFmpeg: {'disponible' if self.tools.available else 'no disponible'}"
            f"   ·   API Key: {self.settings.masked_api_key()}"
            f"   ·   View Key: {self.settings.masked_view_key()}",
        )
        self.console.print()
        widgets.render_menu(
            self.console,
            [
                ("01", "Analizar y descargar un enlace de Vimeus"),
                ("02", "Buscar por identificador (TMDb / IMDb)"),
                ("03", "Explorar peliculas"),
                ("04", "Explorar series"),
                ("05", "Explorar animes"),
                ("06", "Explorar episodios de una serie"),
                ("07", "Mis descargas (historial)"),
                ("08", "Configuracion"),
                ("09", "Acerca de ParMovies"),
                ("00", "Salir"),
            ],
            note="Los enlaces y el codigo <iframe> de Vimeus pueden pegarse directamente.",
        )

    def _screen_about(self) -> None:
        self.console.clear()
        render_header(self.console)
        self.console.print()
        rows = [
            ("Nombre", APP_NAME),
            ("Version", __version__),
            ("Descripcion", APP_DESCRIPTION),
            ("Lema", APP_TAGLINE),
            ("Interfaz", INTERFACE_STYLE),
            ("Plataforma", PLATFORM),
            ("Licencia", LICENSE_NAME),
            ("Desarrolladores", " / ".join(DEVELOPERS)),
            ("Repositorio", REPOSITORY_URL),
        ]
        for label, value in rows:
            self.console.print(f"  [pm.label]{label:<15}[/pm.label] [pm.value]{value}[/pm.value]")
        self.console.print()
        separator(self.console, min(self.console.width, 62))
        self.console.print()
        widgets.dim(self.console, _LEGAL_NOTE)
        self.console.print()
        widgets.dim(self.console, f"Registro de actividad: {log_path()}")
        widgets.pause(self.console)

    def _screen_history(self) -> None:
        self.console.clear()
        render_header(self.console, subtitle="Historial de descargas")
        entries = self.history.entries
        screens.render_history(self.console, entries)
        self.console.print()
        if entries:
            widgets.dim(self.console, f"Total: {len(entries)} descarga(s) registrada(s).")
        widgets.pause(self.console)

    # -- Acerca de la configuracion ---------------------------------------
    def _screen_settings(self) -> None:
        while True:
            self.console.clear()
            render_header(self.console, subtitle="Configuracion local")
            s = self.settings
            rows = [
                ("API Key", s.masked_api_key()),
                ("View Key", s.masked_view_key()),
                ("Descargas", str(s.resolved_downloads_dir())),
                ("Calidad", s.preferred_quality),
                ("Audio", s.preferred_audio_language),
                ("Subtitulos", s.subtitle_mode),
                ("Formato", s.output_format),
                ("Metadatos", "si" if s.download_metadata else "no"),
                ("Reintentos", str(s.retries)),
                ("Limite KB/s", str(s.speed_limit_kib)),
                ("Temporales", "conservar" if s.keep_temp_files else "borrar"),
                ("Registros", "activados" if s.enable_logs else "desactivados"),
            ]
            for label, value in rows:
                self.console.print(f"  [pm.label]{label:<13}[/pm.label] [pm.value]{value}[/pm.value]")
            self.console.print()
            widgets.render_menu(
                self.console,
                [
                    ("1", "Editar API Key"),
                    ("2", "Editar View Key"),
                    ("3", "Cambiar carpeta de descargas"),
                    ("4", "Calidad preferida"),
                    ("5", "Idioma de audio preferido"),
                    ("6", "Modo de subtitulos"),
                    ("7", "Formato de salida (mkv/mp4)"),
                    ("8", "Alternar metadatos (.info.json)"),
                    ("9", "Reintentos y limite de velocidad"),
                    ("10", "Alternar conservar temporales"),
                    ("11", "Alternar registros (logs)"),
                    ("12", "Validar credenciales con Vimeus"),
                    ("13", "Guardar cambios"),
                    ("0", "Volver"),
                ],
            )
            key = _normalize_key(widgets.prompt_choice(self.console, "Opcion"))
            if key == "0":
                return
            if key == "1":
                self.settings.api_key = widgets.prompt_text(self.console, "API Key")
            elif key == "2":
                self.settings.view_key = widgets.prompt_text(self.console, "View Key")
            elif key == "3":
                value = widgets.prompt_text(
                    self.console, "Carpeta de descargas", default=str(self.settings.resolved_downloads_dir())
                )
                self.settings.downloads_dir = "" if value == str(self.settings.resolved_downloads_dir()) else value
            elif key == "4":
                value = widgets.prompt_text(
                    self.console,
                    "Calidad (best/2160/1080/720/480)",
                    default=self.settings.preferred_quality,
                )
                self.settings.preferred_quality = value.strip() or "best"
            elif key == "5":
                value = widgets.prompt_text(
                    self.console,
                    "Idioma de audio (es-419/es-ES/es/original)",
                    default=self.settings.preferred_audio_language,
                )
                self.settings.preferred_audio_language = value.strip() or "es-419"
            elif key == "6":
                value = widgets.prompt_text(
                    self.console,
                    "Subtitulos (spanish/all/manual/none)",
                    default=self.settings.subtitle_mode,
                )
                self.settings.subtitle_mode = value.strip() or "spanish"
            elif key == "7":
                value = widgets.prompt_text(
                    self.console, "Formato (mkv/mp4)", default=self.settings.output_format
                )
                self.settings.output_format = value.strip().lower() or "mkv"
            elif key == "8":
                self.settings.download_metadata = not self.settings.download_metadata
            elif key == "9":
                retries = widgets.prompt_text(
                    self.console, "Reintentos", default=str(self.settings.retries)
                )
                speed = widgets.prompt_text(
                    self.console,
                    "Limite de velocidad en KB/s (0 = sin limite)",
                    default=str(self.settings.speed_limit_kib),
                )
                self.settings.retries = _safe_int(retries, self.settings.retries)
                self.settings.speed_limit_kib = _safe_int(speed, self.settings.speed_limit_kib)
            elif key == "10":
                self.settings.keep_temp_files = not self.settings.keep_temp_files
            elif key == "11":
                self.settings.enable_logs = not self.settings.enable_logs
            elif key == "12":
                self._validate_credentials()
            elif key == "13":
                self._save_settings()
                return
            else:
                widgets.warn(self.console, "Opcion no reconocida.")
                widgets.pause(self.console)

    def _save_settings(self) -> None:
        self.settings.normalize()
        path = self.settings.save()
        update_secrets((self.settings.api_key, self.settings.view_key))
        configure_logging(
            enabled=self.settings.enable_logs,
            secrets=(self.settings.api_key, self.settings.view_key),
        )
        widgets.success(self.console, f"Configuracion guardada en {path}.")
        widgets.pause(self.console)

    def _validate_credentials(self) -> None:
        if not self.settings.api_key:
            widgets.warn(self.console, "No hay una API Key configurada.")
            widgets.pause(self.console)
            return
        widgets.dim(self.console, "Validando credenciales...")
        try:
            with VimeusClient(self.settings.api_key, self.settings.base_url) as client:
                ok = client.validate_credentials()
        except VimeusError as exc:
            widgets.error(self.console, f"No se pudieron validar: {exc}")
        else:
            if ok:
                widgets.success(self.console, "Credenciales validas.")
            else:
                widgets.warn(self.console, "La API respondio, pero sin resultados.")
        widgets.pause(self.console)

    # -- Flujos de analisis ------------------------------------------------
    def _flow_analyze(self, initial_input: str | None = None) -> int:
        self.console.clear()
        render_header(self.console, subtitle="Analizar enlace")
        text = initial_input or widgets.prompt_text(
            self.console, "Pega el enlace de Vimeus o el codigo <iframe>"
        )
        if not text.strip():
            widgets.warn(self.console, "No se introdujo ningun enlace.")
            widgets.pause(self.console)
            return 0
        try:
            request = parse_input(text, self.settings.trusted_domains)
        except AnalysisError as exc:
            widgets.error(self.console, str(exc))
            widgets.pause(self.console)
            return 1
        return self._analyze_and_download(request)

    def _flow_search_id(self) -> None:
        self.console.clear()
        render_header(self.console, subtitle="Buscar por identificador")
        kind_raw = widgets.prompt_text(
            self.console, "Tipo (movie/serie/anime)", default="movie"
        ).strip().lower()
        kind = {"movie": "movie", "pelicula": "movie", "serie": "serie", "series": "serie", "anime": "anime"}.get(
            kind_raw, ""
        )
        if not kind:
            widgets.warn(self.console, "Tipo no valido. Usa movie, serie o anime.")
            widgets.pause(self.console)
            return
        identifier = widgets.prompt_text(self.console, "Identificador TMDb (numero) o IMDb (tt...)").strip()
        if not identifier:
            widgets.warn(self.console, "No se introdujo identificador.")
            widgets.pause(self.console)
            return

        tmdb_id = None
        imdb_id = ""
        if identifier.lower().startswith("tt"):
            imdb_id = identifier
        else:
            tmdb_id = _safe_int(identifier, None)
            if tmdb_id is None:
                widgets.error(self.console, "El identificador TMDb debe ser numerico.")
                widgets.pause(self.console)
                return

        season = episode = None
        if kind in ("serie", "anime"):
            season = _safe_int(
                widgets.prompt_text(self.console, "Temporada", default="1"), 1
            )
            episode = _safe_int(
                widgets.prompt_text(self.console, "Episodio", default="1"), 1
            )

        request = ContentRequest(
            kind=kind,
            endpoint=kind,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            origin="url",
        )
        self._analyze_and_download(request)

    # -- Exploracion de listados ------------------------------------------
    def _flow_listing(self, endpoint: str) -> None:
        title = {"movies": "PELICULAS", "series": "SERIES", "animes": "ANIMES"}.get(endpoint, "CONTENIDO")
        page_number = 1
        with self._session() as client:
            if client is None:
                return
            while True:
                try:
                    page = self._list(client, endpoint, page_number)
                except VimeusError as exc:
                    self.console.clear()
                    widgets.error(self.console, str(exc))
                    widgets.pause(self.console)
                    return
                self.console.clear()
                screens.render_listing(self.console, page, title=title)
                self.console.print()
                hint = "numero para elegir"
                if page.has_next:
                    hint += "  ·  [n] siguiente"
                if page.has_prev:
                    hint += "  ·  [p] anterior"
                hint += "  ·  [b] volver"
                widgets.dim(self.console, hint)
                raw = widgets.prompt_choice(self.console, "Opcion").strip().lower()
                if raw in ("b", "", "volver"):
                    return
                if raw == "n" and page.has_next:
                    page_number += 1
                    continue
                if raw == "p" and page.has_prev:
                    page_number = max(1, page_number - 1)
                    continue
                index = _safe_int(raw, None)
                if index is None or not (1 <= index <= len(page.items)):
                    widgets.warn(self.console, "Seleccion no valida.")
                    widgets.pause(self.console)
                    continue
                self._handle_listing_item(client, page.items[index - 1])

    def _flow_episode_search(self) -> None:
        self.console.clear()
        render_header(self.console, subtitle="Explorar episodios")
        identifier = widgets.prompt_text(self.console, "Identificador TMDb de la serie").strip()
        tmdb_id = _safe_int(identifier, None)
        if tmdb_id is None:
            widgets.warn(self.console, "El identificador TMDb debe ser numerico.")
            widgets.pause(self.console)
            return
        season = _safe_int(widgets.prompt_text(self.console, "Temporada", default="1"), 1)
        page_number = 1
        with self._session() as client:
            if client is None:
                return
            while True:
                try:
                    page = client.list_episodes(tmdb_id, season=season, page=page_number)
                except VimeusError as exc:
                    widgets.error(self.console, str(exc))
                    widgets.pause(self.console)
                    return
                self.console.clear()
                screens.render_listing(self.console, page, title=f"EPISODIOS · T{season:02d}")
                self.console.print()
                raw = widgets.prompt_choice(self.console, "Numero o [b] volver").strip().lower()
                if raw in ("b", "", "volver"):
                    return
                index = _safe_int(raw, None)
                if index is None or not (1 <= index <= len(page.items)):
                    widgets.warn(self.console, "Seleccion no valida.")
                    widgets.pause(self.console)
                    continue
                self._handle_listing_item(client, page.items[index - 1], forced_season=season)

    def _handle_listing_item(
        self, client: VimeusClient, item: ListingItem, *, forced_season: int | None = None
    ) -> None:
        content_type = (item.content_type or item.parent_type or "").lower()
        is_episode = item.season is not None or item.episode is not None

        if not is_episode and content_type in ("serie", "series", "serie", "anime"):
            kind = "anime" if content_type == "anime" else "serie"
            if item.tmdb_id is None:
                widgets.warn(self.console, "El elemento no tiene identificador TMDb para listar episodios.")
                widgets.pause(self.console)
                return
            season = forced_season
            if season is None:
                season = _safe_int(
                    widgets.prompt_text(self.console, "Temporada", default="1"), 1
                )
            try:
                page = client.list_episodes(item.tmdb_id, season=season, page=1)
            except VimeusError as exc:
                widgets.error(self.console, str(exc))
                widgets.pause(self.console)
                return
            if not page.items:
                widgets.warn(self.console, "No hay episodios disponibles para esa temporada.")
                widgets.pause(self.console)
                return
            self.console.clear()
            screens.render_listing(
                self.console, page, title=f"{item.display_title} · T{season:02d}"
            )
            self.console.print()
            raw = widgets.prompt_choice(self.console, "Numero de episodio o [b] volver").strip().lower()
            if raw in ("b", "", "volver"):
                return
            index = _safe_int(raw, None)
            if index is None or not (1 <= index <= len(page.items)):
                widgets.warn(self.console, "Seleccion no valida.")
                widgets.pause(self.console)
                return
            chosen = page.items[index - 1]
            request = ContentRequest(
                kind=kind,
                endpoint=kind,
                tmdb_id=chosen.tmdb_id or item.tmdb_id,
                imdb_id=chosen.imdb_id or item.imdb_id,
                season=chosen.season if chosen.season is not None else season,
                episode=chosen.episode,
                origin="url",
            )
            self._analyze_and_download(request)
            return

        if item.tmdb_id is None and not item.imdb_id:
            widgets.warn(self.console, "El elemento no tiene un identificador TMDb/IMDb utilizable.")
            widgets.pause(self.console)
            return

        kind = {"anime": "anime", "serie": "serie", "series": "serie", "episode": "episode"}.get(
            content_type, "movie"
        )
        request = ContentRequest(
            kind=kind,
            endpoint=kind,
            tmdb_id=item.tmdb_id,
            imdb_id=item.imdb_id,
            season=item.season,
            episode=item.episode,
            origin="url",
        )
        self._analyze_and_download(request)

    # -- Analisis y descarga ----------------------------------------------
    def _analyze_and_download(self, request: ContentRequest) -> int:
        widgets.dim(self.console, "Resolviendo el contenido...")
        try:
            with self._session() as client:
                if client is None:
                    return 1
                resolver = MediaResolver(
                    client,
                    base_url=self.settings.base_url,
                    trusted_domains=self.settings.trusted_domains,
                    default_view_key=self.settings.view_key,
                )
                analysis = resolver.resolve(request)
        except (AnalysisError, VimeusError) as exc:
            widgets.error(self.console, str(exc))
            widgets.pause(self.console)
            return 1
        except Exception as exc:  # pragma: no cover - robustez ante sorpresas
            widgets.error(self.console, f"Error inesperado: {exc}")
            widgets.pause(self.console)
            return 1

        self.console.clear()
        render_header(self.console, subtitle="Analisis de contenido")
        screens.render_analysis(self.console, analysis)

        if not analysis.is_downloadable or analysis.playback is None:
            widgets.warn(
                self.console,
                "No se encontro una fuente multimedia descargable compatible.",
            )
            widgets.pause(self.console)
            return 1

        variant = self._choose_variant(analysis)
        if variant is None:
            widgets.warn(self.console, "Descarga cancelada.")
            widgets.pause(self.console)
            return 1

        subtitle_tracks = self._choose_subtitles(analysis.playback.subtitles)
        audio_language = self._choose_audio_language(analysis)

        self.console.print()
        widgets.dim(
            self.console,
            f"Calidad {variant.resolution_label} · Audio {audio_language or 'original'} · "
            f"{len(subtitle_tracks)} subtitulo(s) · Formato {self.settings.output_format}",
        )
        if not widgets.prompt_si_no(self.console, "Iniciar la descarga", default=True):
            widgets.dim(self.console, "Descarga cancelada por el usuario.")
            widgets.pause(self.console)
            return 0

        task = make_task(
            self.settings,
            analysis,
            variant,
            subtitle_tracks=subtitle_tracks,
            audio_language=audio_language,
            exists_strategy="rename",
        )
        result = self._run_download(analysis, task, variant, audio_language, subtitle_tracks)
        self._record_history(analysis, variant, audio_language, subtitle_tracks, result)
        self.console.print()
        widgets.pause(self.console)
        return 0 if result.ok else 1

    def _choose_variant(self, analysis: MediaAnalysis) -> MediaVariant | None:
        playback = analysis.playback
        if playback is None:
            return None
        variants = screens.render_variants(self.console, analysis)
        if not variants:
            return None
        default = pick_variant(variants, self.settings.preferred_quality) or variants[0]
        self.console.print()
        widgets.dim(
            self.console,
            f"Pulsa Enter para usar la mejor calidad segun preferencia ({default.resolution_label}).",
        )
        raw = widgets.prompt_choice(self.console, "Calidad").strip()
        if not raw:
            return default
        index = _safe_int(raw, None)
        if index is not None and 1 <= index <= len(variants):
            return variants[index - 1]
        height_choice = pick_variant(variants, raw)
        return height_choice or default

    def _choose_subtitles(self, tracks: list[SubtitleTrack]) -> list[SubtitleTrack]:
        if not tracks:
            return []
        order = {
            "spanish": "1",
            "all": "2",
            "none": "3",
            "manual": "4",
        }
        default = order.get(self.settings.subtitle_mode, "1")
        self.console.print()
        widgets.dim(
            self.console,
            "Subtitulos: [1] solo espanol  [2] todos  [3] ninguno  [4] manual",
        )
        for index, track in enumerate(tracks, start=1):
            label = track.language_label
            widgets.dim(self.console, f"  {index:02d}) {label}")
        raw = widgets.prompt_choice(self.console, f"Modo de subtitulos (Enter = {default})").strip()
        choice = raw or default
        if choice == "3":
            return []
        if choice == "2":
            return select_subtitles(tracks, "all")
        if choice == "4":
            selection = widgets.prompt_text(
                self.console, "Numeros separados por coma, por ejemplo 1,3", default=""
            )
            indices = [n - 1 for n in _parse_int_list(selection) if 1 <= n <= len(tracks)]
            return select_subtitles(tracks, "manual", manual_indices=indices)
        return select_subtitles(tracks, "spanish")

    def _choose_audio_language(self, analysis: MediaAnalysis) -> str:
        labels: list[str] = []
        for embed in analysis.embeds:
            if embed.lang and embed.lang not in labels:
                labels.append(embed.lang)
        if not labels:
            return self.settings.preferred_audio_language
        if len(labels) == 1:
            return labels[0]
        ordered = order_audio_labels(labels, original_language=self.settings.preferred_audio_language)
        return ordered[0]

    def _run_download(
        self,
        analysis: MediaAnalysis,
        task,
        variant: MediaVariant,
        audio_language: str,
        subtitle_tracks: list[SubtitleTrack],
    ) -> DownloadResult:
        state: dict[str, DownloadProgress] = {"progress": DownloadProgress(status=DownloadStatus.PREPARING)}
        lock = threading.Lock()
        result_box: dict[str, DownloadResult] = {}
        cancel = threading.Event()

        def on_progress(progress: DownloadProgress) -> None:
            with lock:
                state["progress"] = progress

        engine = DownloadEngine(
            self.settings,
            self.tools,
            progress=on_progress,
            cancel=cancel,
        )

        def worker() -> None:
            try:
                result_box["result"] = engine.run(task)
            except Exception as exc:  # pragma: no cover - se informa al usuario
                result_box["result"] = DownloadResult(
                    status=DownloadStatus.ERROR, error=f"Error inesperado: {exc}"
                )

        context = screens.ProgressContext(
            title=analysis.title,
            filename=task.output_path.name,
            resolution=variant.resolution_label,
            container=self.settings.output_format,
            audio=audio_language or "original",
        )

        thread = threading.Thread(target=worker, name="parmovies-download", daemon=True)
        self.console.print()
        with screens.ProgressDisplay(self.console, context) as display:
            thread.start()
            try:
                while thread.is_alive():
                    with lock:
                        display.update(state["progress"])
                    time.sleep(0.12)
            except KeyboardInterrupt:
                cancel.set()
                widgets.warn(self.console, "Cancelando la descarga...")
                thread.join(timeout=10)
            with lock:
                display.update(state["progress"])
            thread.join(timeout=5)

        result = result_box.get(
            "result",
            DownloadResult(status=DownloadStatus.CANCELLED, error="Descarga cancelada."),
        )
        self.console.print()
        self._report_result(result)
        return result

    def _report_result(self, result: DownloadResult) -> None:
        if result.status == DownloadStatus.CANCELLED:
            widgets.warn(self.console, result.error or "Descarga cancelada.")
            return
        if result.status != DownloadStatus.COMPLETED:
            widgets.error(self.console, result.error or "La descarga fallo.")
            return
        widgets.success(self.console, result.message)
        if result.output_path:
            widgets.dim(self.console, f"Archivo: {result.output_path}")
            widgets.dim(self.console, f"Tamano: {widgets.format_bytes(result.bytes_written)}")
        if result.verified and result.media_info:
            info = result.media_info
            widgets.dim(
                self.console,
                f"Verificado con FFprobe: {info.resolution} · {info.video_codec} · "
                f"audio {[a.codec for a in info.audio_streams]}",
            )
        elif not self.tools.available:
            widgets.dim(self.console, "FFmpeg no disponible: no se pudo verificar con FFprobe.")
        elif not result.verified:
            widgets.warn(self.console, "El archivo se guardo, pero no se pudo verificar con FFprobe.")
        for subtitle in result.subtitle_files:
            widgets.dim(self.console, f"Subtitulo: {subtitle}")
        if result.info_file:
            widgets.dim(self.console, f"Ficha: {result.info_file}")

    def _record_history(
        self,
        analysis: MediaAnalysis,
        variant: MediaVariant,
        audio_language: str,
        subtitle_tracks: list[SubtitleTrack],
        result: DownloadResult,
    ) -> None:
        request = analysis.request
        media_info = result.media_info
        entry = HistoryEntry(
            title=analysis.title,
            content_type=analysis.content_type or request.kind,
            season=request.season,
            episode=request.episode,
            quality=variant.quality_name,
            resolution=media_info.resolution if media_info else variant.resolution_label,
            container=self.settings.output_format,
            audio_language=audio_language,
            subtitle_languages=[t.language or t.label for t in subtitle_tracks],
            size_bytes=result.bytes_written,
            status=result.status.value,
            verified=result.verified,
            path=str(result.output_path) if result.output_path else "",
            source=request.source_url or (analysis.playback.source_page if analysis.playback else ""),
        )
        self.history.add(entry)

    # -- Utilidades internas ----------------------------------------------
    def _client(self) -> VimeusClient | None:
        """Crea un cliente de Vimeus, avisando si faltan credenciales."""

        if not self.settings.is_authenticated():
            widgets.warn(
                self.console,
                "Faltan credenciales (API Key / View Key). Configuralas en la opcion 08.",
            )
            widgets.pause(self.console)
            return None
        configure_logging(
            enabled=self.settings.enable_logs,
            secrets=(self.settings.api_key, self.settings.view_key),
        )
        return VimeusClient(self.settings.api_key, self.settings.base_url)

    @contextmanager
    def _session(self):
        """Contexto que abre y cierra el cliente, o produce ``None`` sin credenciales."""

        client = self._client()
        if client is None:
            yield None
            return
        try:
            yield client
        finally:
            client.close()

    def _list(self, client: VimeusClient, endpoint: str, page: int) -> ListingPage:
        if endpoint == "movies":
            return client.list_movies(page=page)
        if endpoint == "series":
            return client.list_series(page=page)
        if endpoint == "animes":
            return client.list_animes(page=page)
        raise AnalysisError("Listado no soportado.")


# -- Funciones auxiliares --------------------------------------------------
def _normalize_key(value: str) -> str:
    """Normaliza una opcion numerica escrita por el usuario."""

    text = (value or "").strip().lower()
    if text.isdigit():
        return str(int(text))
    return text


def _safe_int(value: str | int | None, default):
    """Convierte a entero sin lanzar excepciones."""

    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_int_list(value: str) -> list[int]:
    """Extrae enteros separados por comas o espacios."""

    result: list[int] = []
    for chunk in (value or "").replace(";", ",").split(","):
        for token in chunk.split():
            number = _safe_int(token, None)
            if number is not None:
                result.append(number)
    return result


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la interfaz de ParMovies."""

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help", "help"):
        print(f"{APP_NAME} {__version__} - {APP_DESCRIPTION}")
        print("Uso: parmovies [URL_DE_VIMEUS]")
        print()
        print("Sin argumentos abre el menu interactivo.")
        print(f"Desarrolladores: {', '.join(DEVELOPERS)}")
        return 0
    if args and args[0] in ("-V", "--version", "version"):
        print(f"{APP_NAME} {__version__}")
        return 0

    initial = " ".join(args).strip() if args else None

    if sys.platform == "win32":
        try:  # habilita UTF-8 en consolas clasicas de Windows
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    console = create_console()
    app = ParMoviesApp(console=console)
    try:
        return app.run(initial_input=initial)
    finally:
        console.show_cursor(True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
