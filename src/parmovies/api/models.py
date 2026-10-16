"""Modelos de datos de ParMovies.

Todas las estructuras son tolerantes a campos ausentes: la API puede omitir
claves o devolver tipos ligeramente distintos segun el contenido.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"


def _as_int(value: object) -> int | None:
    """Convierte un valor a entero de forma segura."""

    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def tmdb_image_url(path: str | None) -> str:
    """Resuelve una ruta relativa de imagen de TMDb a URL absoluta."""

    if not path:
        return ""
    path = str(path).strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{TMDB_IMAGE_BASE}{path}"


@dataclass
class ListingItem:
    """Elemento de un listado de la API de Vimeus."""

    title: str = ""
    content_type: str = ""
    tmdb_id: int | None = None
    imdb_id: str = ""
    poster: str = ""
    backdrop: str = ""
    quality: str = ""
    embed_url: str = ""
    download_url: str = ""
    season: int | None = None
    episode: int | None = None
    show_title: str = ""
    parent_type: str = ""
    synced_at: str = ""
    total_seasons: int | None = None
    total_episodes: int | None = None

    @classmethod
    def from_api(cls, payload: dict) -> "ListingItem":
        return cls(
            title=_as_str(payload.get("title")),
            content_type=_as_str(payload.get("content_type") or payload.get("parent_type")),
            tmdb_id=_as_int(payload.get("tmdb_id")),
            imdb_id=_as_str(payload.get("imdb_id")),
            poster=tmdb_image_url(payload.get("poster")),
            backdrop=tmdb_image_url(payload.get("backdrop")),
            quality=_as_str(payload.get("quality")),
            embed_url=_as_str(payload.get("embed_url")),
            download_url=_as_str(payload.get("download_url")),
            season=_as_int(payload.get("season")),
            episode=_as_int(payload.get("episode")),
            show_title=_as_str(payload.get("show_title")),
            parent_type=_as_str(payload.get("parent_type")),
            synced_at=_as_str(payload.get("synced_at")),
            total_seasons=_as_int(payload.get("total_seasons")),
            total_episodes=_as_int(payload.get("total_episodes")),
        )

    @property
    def display_title(self) -> str:
        """Titulo legible incluyendo temporada/episodio cuando aplique."""

        base = self.title or self.show_title
        if self.season is not None and self.episode is not None:
            return f"{base} - S{self.season:02d}E{self.episode:02d}"
        return base


@dataclass
class ListingPage:
    """Pagina de resultados devuelta por la API."""

    items: list[ListingItem] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1
    total_results: int | None = None
    per_page: int | None = None
    has_next: bool = False
    has_prev: bool = False

    @classmethod
    def from_api(cls, payload: dict, requested_page: int = 1) -> "ListingPage":
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            data = {}
        raw_items = data.get("result")
        if not isinstance(raw_items, list):
            raw_items = []
        items = [
            ListingItem.from_api(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        total_pages = _as_int(data.get("pages") or data.get("total_pages")) or 1
        current_page = _as_int(data.get("current_page")) or requested_page
        return cls(
            items=items,
            current_page=current_page,
            total_pages=max(total_pages, 1),
            total_results=_as_int(data.get("total_results")),
            per_page=_as_int(data.get("per_page")) or len(items) or None,
            has_next=bool(data.get("has_next")) or current_page < total_pages,
            has_prev=bool(data.get("has_prev")) or current_page > 1,
        )


@dataclass
class EmbedSource:
    """Servidor de reproduccion asociado a un contenido."""

    server: str = ""
    url: str = ""
    quality: str = ""
    lang: str = ""
    resolution: str = ""
    size: str = ""
    subtitle: bool = False
    format: str = ""
    sala_id: int | None = None

    @classmethod
    def from_api(cls, payload: dict) -> "EmbedSource":
        return cls(
            server=_as_str(payload.get("server")),
            url=_as_str(payload.get("url")),
            quality=_as_str(payload.get("quality")),
            lang=_as_str(payload.get("lang")),
            resolution=_as_str(payload.get("resolution")),
            size=_as_str(payload.get("size")),
            subtitle=bool(payload.get("subtitle")),
            format=_as_str(payload.get("format")),
            sala_id=_as_int(payload.get("sala_id")),
        )


@dataclass
class MediaVariant:
    """Variante de calidad de un manifiesto HLS/DASH."""

    url: str = ""
    width: int | None = None
    height: int | None = None
    bandwidth: int | None = None
    codecs: str = ""
    frame_rate: str = ""
    is_audio_only: bool = False

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        if self.height:
            return f"{self.height}p"
        return "desconocida"

    @property
    def quality_name(self) -> str:
        """Etiqueta corta de calidad (2160p, 1080p, ...)."""

        if self.height:
            return f"{self.height}p"
        return "desconocida"


@dataclass
class SubtitleTrack:
    """Pista de subtitulos disponible."""

    url: str = ""
    label: str = ""
    language: str = ""
    kind: str = "captions"
    is_default: bool = False

    @property
    def language_label(self) -> str:
        return self.language or self.label or "desconocido"


@dataclass
class PlaybackInfo:
    """Informacion de reproduccion/descarga resuelta para un contenido."""

    variants: list[MediaVariant] = field(default_factory=list)
    subtitles: list[SubtitleTrack] = field(default_factory=list)
    poster: str = ""
    duration_seconds: float | None = None
    headers: dict[str, str] = field(default_factory=dict)
    source_page: str = ""

    @property
    def has_media(self) -> bool:
        return any(not v.is_audio_only for v in self.variants)


@dataclass
class ContentRequest:
    """Peticion de contenido derivada de una URL de Vimeus."""

    kind: str = "movie"  # movie | serie | anime | episode | unknown
    endpoint: str = ""  # segmento de ruta original (movie/serie/anime/episode)
    tmdb_id: int | None = None
    imdb_id: str = ""
    season: int | None = None
    episode: int | None = None
    view_key: str = ""
    source_url: str = ""
    origin: str = "url"  # url | iframe

    @property
    def is_episode(self) -> bool:
        """Indica si la peticion corresponde a un episodio concreto."""

        return self.episode is not None or self.kind == "episode"

    def describe_kind(self) -> str:
        if self.kind in ("serie", "anime") and self.is_episode:
            base = "Serie" if self.kind == "serie" else "Anime"
            if self.season is not None and self.episode is not None:
                return f"{base} (Temporada {self.season}, Episodio {self.episode})"
            return f"{base} (Episodio)"
        return {
            "movie": "Pelicula",
            "serie": "Serie",
            "anime": "Anime",
            "episode": "Episodio",
        }.get(self.kind, "Desconocido")


@dataclass
class MediaAnalysis:
    """Resultado completo del analisis de un enlace."""

    request: ContentRequest
    title: str = ""
    content_type: str = ""
    poster: str = ""
    backdrop: str = ""
    embeds: list[EmbedSource] = field(default_factory=list)
    playback: PlaybackInfo | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_downloadable(self) -> bool:
        return self.playback is not None and self.playback.has_media

    @property
    def best_height(self) -> int:
        if not self.playback:
            return 0
        return max((v.height or 0 for v in self.playback.variants), default=0)
