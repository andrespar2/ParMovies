"""Pruebas de la resolucion completa de medios con un cliente simulado."""

from __future__ import annotations

import pytest

from parmovies.analyzers.resolver import MediaResolver, build_embed_url
from parmovies.analyzers.url_parser import parse_input
from parmovies.api.errors import SourceNotSupportedError
from parmovies.api.models import ContentRequest
from parmovies.media.formats import pick_variant

TRUSTED = ("vimeus.com", "vimeos.net")

EMBED_HTML = """
<html><head><title>Pelicula</title></head><body>
<script type="text/json" id="data">
{"backdrop":"/b.jpg","embeds":[{"format":null,"lang":"Latino - Ingl\u00e9s","quality":"Dual 1080p",
"resolution":null,"sala_id":6,"server":"LaMovie","size":null,"subtitle":0,
"url":"https://vimeos.net/embed-abc.html"}],"episode":0,"poster":"/p.jpg","season":0,
"title":"Pelicula Prueba","tmdb_id":264420,"type":"movie"}
</script>
</body></html>
"""

PLAYER_HTML = """
<html><body><script>
var jws={skin:{name:"x"},sources:[{file:"https://cdn.example/master.m3u8?t=1"}],
autostart:false,image:"https://cdn.example/poster.jpg",duration:"5918.14",
tracks:[{file:"https://cdn.example/spa.vtt",label:"Spanish",kind:"captions","default":true},
{file:"/srt/empty.srt",label:"Upload captions",kind:"captions"}]};
window.playerInstance=jwplayer("vplayer").setup(jws);
</script></body></html>
"""

MASTER_M3U8 = """#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=662698,RESOLUTION=888x480,CODECS="avc1.64001f,mp4a.40.2"
https://cdn.example/n/index.m3u8?t=1
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1672984,RESOLUTION=1336x720,CODECS="avc1.640028,mp4a.40.2"
https://cdn.example/h/index.m3u8?t=1
"""


class FakeClient:
    """Cliente de Vimeus simulado que responde por coincidencia de URL."""

    def __init__(
        self,
        html_map: dict[str, str] | None = None,
        text_map: dict[str, str] | None = None,
    ) -> None:
        self.html_map = html_map or {}
        self.text_map = text_map or {}
        self.calls: list[str] = []

    def _lookup(self, mapping: dict[str, str], url: str) -> str:
        if url in mapping:
            return mapping[url]
        for key, value in mapping.items():
            if key in url:
                return value
        raise AssertionError(f"URL no simulada: {url}")

    def fetch_html(self, url: str, *, referer: str | None = None) -> str:
        self.calls.append(url)
        return self._lookup(self.html_map, url)

    def fetch_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        self.calls.append(url)
        return self._lookup(self.text_map, url)


def make_client() -> FakeClient:
    return FakeClient(
        html_map={
            "/e/movie": EMBED_HTML,
            "embed-abc.html": PLAYER_HTML,
        },
        text_map={"master.m3u8": MASTER_M3U8},
    )


def test_build_embed_url():
    request = ContentRequest(kind="movie", endpoint="movie", tmdb_id=264420)
    url = build_embed_url(request, "https://vimeus.com", "clave")
    assert url.startswith("https://vimeus.com/e/movie?")
    assert "tmdb=264420" in url
    assert "view_key=clave" in url


def test_build_embed_url_episodio():
    request = ContentRequest(kind="serie", endpoint="serie", tmdb_id=1399, season=1, episode=2)
    url = build_embed_url(request, "https://vimeus.com")
    assert "/e/serie?" in url
    assert "se=1" in url
    assert "ep=2" in url


def test_resolve_end_to_end():
    request = parse_input("https://vimeus.com/e/movie?tmdb=264420&view_key=k", TRUSTED)
    client = make_client()
    resolver = MediaResolver(
        client,
        base_url="https://vimeus.com",
        trusted_domains=TRUSTED,
        default_view_key="k",
    )
    analysis = resolver.resolve(request)

    assert analysis.title == "Pelicula Prueba"
    assert analysis.content_type == "movie"
    assert analysis.is_downloadable
    assert analysis.playback is not None
    assert analysis.playback.duration_seconds == 5918.14
    assert len(analysis.playback.headers.get("Referer", "")) > 0

    heights = sorted(v.height for v in analysis.playback.variants if v.height)
    assert heights == [480, 720]

    best = pick_variant(analysis.playback.variants, "best")
    assert best is not None
    assert best.height == 720

    languages = [t.language for t in analysis.playback.subtitles]
    assert "es" in languages
    # El marcador "empty" se descarta y no se trata como subtitulo real.
    assert all("empty" not in t.url for t in analysis.playback.subtitles)


def test_resolve_sin_embeds_lanza_error():
    html = '<script type="text/json" id="data">{"title":"x","embeds":[]}</script>'
    client = FakeClient(html_map={"/e/movie": html})
    resolver = MediaResolver(client, base_url="https://vimeus.com", trusted_domains=TRUSTED)
    request = ContentRequest(kind="movie", endpoint="movie", tmdb_id=1)
    with pytest.raises(SourceNotSupportedError):
        resolver.resolve(request)


def test_resolve_pagina_invalida_lanza_error():
    client = FakeClient(html_map={"/e/movie": "<html>sin datos</html>"})
    resolver = MediaResolver(client, base_url="https://vimeus.com", trusted_domains=TRUSTED)
    request = ContentRequest(kind="movie", endpoint="movie", tmdb_id=1)
    with pytest.raises(Exception):
        resolver.resolve(request)
