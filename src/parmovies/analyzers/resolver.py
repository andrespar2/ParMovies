"""Resolucion completa de un enlace de Vimeus hasta sus medios descargables.

Cadena de resolucion (verificada):

1. ``GET /e/<tipo>?tmdb=...&view_key=...`` -> pagina de embed con un bloque
   JSON que lista los servidores (``embeds``).
2. Cada embed apunta a un reproductor externo (por ejemplo ``vimeos.net``).
3. El reproductor externo declara sus fuentes en un bloque JavaScript
   empaquetado que contiene un manifiesto HLS (``master.m3u8``) y pistas de
   subtitulos (VTT).

No se descifra DRM ni se eluden controles de acceso: solo se interpretan los
manifiestos y enlaces que el propio origen entrega.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..api.errors import SourceNotSupportedError
from ..api.models import (
    ContentRequest,
    EmbedSource,
    MediaAnalysis,
    MediaVariant,
    PlaybackInfo,
    SubtitleTrack,
    tmdb_image_url,
)
from ..api.vimeus import VimeusClient
from ..media.hls import parse_master
from ..utilities.logging_setup import get_logger
from .embed_parser import parse_embed_page
from .errors import AnalysisError
from .player_parser import parse_player_config
from .url_parser import is_domain_trusted

_log = get_logger("resolver")

# Segmento de ruta del endpoint de embed segun el tipo de contenido.
_ENDPOINT_SEGMENT = {
    "movie": "movie",
    "serie": "serie",
    "anime": "anime",
    "episode": "serie",
    "unknown": "movie",
}

SUBTITLE_PLACEHOLDER = "empty"


def build_embed_url(request: ContentRequest, base_url: str, default_view_key: str = "") -> str:
    """Construye la URL de embed a partir de la peticion de contenido."""

    segment = _ENDPOINT_SEGMENT.get(request.endpoint or request.kind, "movie")
    params: list[tuple[str, str]] = []
    if request.tmdb_id is not None:
        params.append(("tmdb", str(request.tmdb_id)))
    elif request.imdb_id:
        params.append(("imdb", request.imdb_id))
    else:
        raise AnalysisError("La peticion no contiene un identificador tmdb ni imdb.")

    if request.season is not None:
        params.append(("se", str(request.season)))
    if request.episode is not None:
        params.append(("ep", str(request.episode)))

    view_key = request.view_key or default_view_key
    if view_key:
        params.append(("view_key", view_key))

    return f"{base_url.rstrip('/')}/e/{segment}?{urlencode(params)}"


class MediaResolver:
    """Resuelve enlaces de Vimeus hasta el manifiesto HLS y los subtitulos."""

    def __init__(
        self,
        client: VimeusClient,
        *,
        base_url: str = "https://vimeus.com",
        trusted_domains: list[str] | tuple[str, ...] = ("vimeus.com", "vimeos.net"),
        default_view_key: str = "",
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.trusted_domains = tuple(trusted_domains)
        self.default_view_key = default_view_key

    # -- API publica -------------------------------------------------------
    def resolve(self, request: ContentRequest) -> MediaAnalysis:
        """Analiza un contenido y devuelve los medios accesibles."""

        embed_url = build_embed_url(request, self.base_url, self.default_view_key)
        _log.info("Consultando pagina de embed: %s", embed_url)

        html = self.client.fetch_html(embed_url, referer=self.base_url + "/")
        data = parse_embed_page(html)
        if data is None:
            raise AnalysisError(
                "La pagina de embed no contiene la informacion esperada. "
                "Verifique que el enlace sea correcto y que la View Key sea valida."
            )

        analysis = MediaAnalysis(
            request=request,
            title=data.title or request.imdb_id or str(request.tmdb_id or ""),
            content_type=data.content_type or request.kind,
            poster=data.poster,
            backdrop=data.backdrop,
            embeds=[e for e in data.embeds if e.url],
        )
        if not analysis.embeds:
            raise SourceNotSupportedError(
                "El contenido no tiene servidores de reproduccion asociados."
            )

        if data.poster:
            pass  # la caratula ya quedo asignada
        analysis.playback = self._resolve_embeds(analysis.embeds, embed_url)

        if analysis.playback is None:
            raise SourceNotSupportedError(
                "No se encontro un manifiesto multimedia descargable en los servidores disponibles."
            )
        return analysis

    # -- Interno -----------------------------------------------------------
    def _resolve_embeds(
        self, embeds: list[EmbedSource], embed_page_url: str
    ) -> PlaybackInfo | None:
        best: PlaybackInfo | None = None
        best_height = -1

        for embed in embeds:
            if not is_domain_trusted(_host_of(embed.url), self.trusted_domains):
                _log.warning("Se omite un embed de un dominio no autorizado.")
                continue
            try:
                playback = self._resolve_single_embed(embed, embed_page_url)
            except (AnalysisError, SourceNotSupportedError) as exc:
                _log.warning("No se pudo resolver el embed '%s': %s", embed.server, exc)
                continue
            except Exception as exc:  # pragma: no cover - robustez ante sorpresas
                _log.warning("Error inesperado resolviendo el embed '%s': %s", embed.server, exc)
                continue

            if playback is None or not playback.has_media:
                continue
            height = max((v.height or 0 for v in playback.variants), default=0)
            if height > best_height:
                best_height = height
                best = playback

        return best

    def _resolve_single_embed(
        self, embed: EmbedSource, embed_page_url: str
    ) -> PlaybackInfo | None:
        player_html = self.client.fetch_html(embed.url, referer=embed_page_url)
        config = parse_player_config(player_html)
        if config is None:
            return None

        playback = PlaybackInfo(
            poster=config.image,
            duration_seconds=config.duration_seconds,
            source_page=embed.url,
            headers={"Referer": embed.url},
        )

        for source in config.sources:
            self._classify_source(source.url, playback)

        for track in config.tracks:
            url = str(track.get("file") or "")
            label = str(track.get("label") or "")
            if SUBTITLE_PLACEHOLDER in url.lower() or SUBTITLE_PLACEHOLDER in label.lower():
                continue
            if not url:
                continue
            playback.subtitles.append(
                SubtitleTrack(
                    url=url,
                    label=label,
                    language=_guess_language(label),
                    kind=str(track.get("kind") or "captions"),
                    is_default=bool(track.get("default")),
                )
            )

        return playback

    def _classify_source(self, url: str, playback: PlaybackInfo) -> None:
        lowered = url.lower()
        if ".m3u8" in lowered:
            try:
                text = self.client.fetch_text(url, headers={"Referer": playback.source_page})
            except Exception as exc:  # pragma: no cover - red
                _log.warning("No se pudo leer el manifiesto HLS: %s", exc)
                return
            master = parse_master(text, base_url=url)
            for variant in master.variants:
                if variant.width is None and variant.height is None:
                    variant.url = url
                playback.variants.append(variant)
            for subtitle in master.subtitle_renditions:
                playback.subtitles.append(subtitle)
        elif any(ext in lowered for ext in (".mp4", ".m4v", ".webm", ".mkv")):
            playback.variants.append(MediaVariant(url=url))


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).hostname or ""


def _guess_language(label: str) -> str:
    """Infiere un codigo de idioma a partir del nombre de una pista."""

    text = (label or "").strip().lower()
    if not text:
        return ""
    if "latino" in text or "latam" in text or "es-419" in text or "latin" in text:
        return "es-419"
    if "espa" in text or "castellano" in text or "spain" in text or text in ("es", "es-es"):
        return "es-ES"
    if text in ("spanish", "español", "espanol"):
        return "es"
    if text in ("english", "ingles", "inglés", "en"):
        return "en"
    if "ingl" in text or text == "en-us":
        return "en"
    return text
