"""Pruebas de utilidades del menu y de las pantallas (sin E/S interactiva)."""

from __future__ import annotations

from parmovies.api.models import (
    ContentRequest,
    EmbedSource,
    MediaAnalysis,
    MediaVariant,
    PlaybackInfo,
)
from parmovies.cli import screens
from parmovies.cli.app import _normalize_key, _parse_int_list, _safe_int


# -- Utilidades del menu ---------------------------------------------------
def test_normalize_key():
    assert _normalize_key("01") == "1"
    assert _normalize_key(" 9 ") == "9"
    assert _normalize_key("00") == "0"
    assert _normalize_key("b") == "b"
    assert _normalize_key("") == ""


def test_safe_int():
    assert _safe_int("12", None) == 12
    assert _safe_int(" 7 ", 0) == 7
    assert _safe_int("abc", 5) == 5
    assert _safe_int(None, 3) == 3


def test_parse_int_list():
    assert _parse_int_list("1,3") == [1, 3]
    assert _parse_int_list("1 2; 4") == [1, 2, 4]
    assert _parse_int_list("") == []


# -- Pantallas -------------------------------------------------------------
def test_codec_name_traduce():
    assert screens.codec_name("avc1.64001f,mp4a.40.2") == "H.264 / AAC"
    assert screens.codec_name("") == "desconocido"


def test_video_codec_name_solo_video():
    variant = MediaVariant(codecs="avc1.640028,mp4a.40.2")
    assert screens.video_codec_name(variant) == "H.264"
    assert screens.video_codec_name(None) == "desconocido"


def test_estimate_size():
    variant = MediaVariant(bandwidth=1_000_000)
    assert screens.estimate_size(variant, 100) == 12_500_000
    assert screens.estimate_size(variant, None) is None
    assert screens.estimate_size(None, 100) is None


def test_best_variant_ignora_audio():
    analysis = MediaAnalysis(
        request=ContentRequest(kind="movie", endpoint="movie", tmdb_id=1),
        playback=PlaybackInfo(
            variants=[
                MediaVariant(url="a.m3u8", height=480, bandwidth=600_000),
                MediaVariant(url="b.m3u8", height=720, bandwidth=1_600_000),
                MediaVariant(url="audio.m3u8", is_audio_only=True, bandwidth=128_000),
            ]
        ),
    )
    best = screens.best_variant(analysis)
    assert best is not None
    assert best.height == 720


def test_audio_description_usa_embeds():
    analysis = MediaAnalysis(
        request=ContentRequest(kind="movie", endpoint="movie", tmdb_id=1),
        embeds=[EmbedSource(server="A", url="https://vimeos.net/x", lang="Latino - Ingl\u00e9s")],
    )
    assert screens.audio_description(analysis) == "Latino - Ingl\u00e9s"


def test_subtitle_description_vacia():
    analysis = MediaAnalysis(request=ContentRequest(kind="movie", endpoint="movie", tmdb_id=1))
    assert screens.subtitle_description(analysis) == "ninguno detectado"
