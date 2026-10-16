"""Pruebas de organizacion de archivos y utilidades de rutas."""

from __future__ import annotations

from pathlib import Path

from parmovies.analyzers.url_parser import parse_input
from parmovies.api.models import ContentRequest, MediaAnalysis, MediaVariant
from parmovies.utilities import paths, organizer
from parmovies.utilities.organizer import build_output_path, category_for, audio_tag


def _analysis(text: str, title: str, kind: str) -> MediaAnalysis:
    request = parse_input(text, ("vimeus.com",))
    return MediaAnalysis(request=request, title=title, content_type=kind)


def test_pelicula_ruta(tmp_path):
    analysis = _analysis("https://vimeus.com/e/movie?tmdb=1", "Pelicula Prueba", "movie")
    path = build_output_path(tmp_path, analysis, height=1080, year=2025, audio_language="es-419")
    assert path.parent == tmp_path / "Peliculas" / "Pelicula Prueba (2025)"
    assert path.name == "Pelicula Prueba (2025) [1080p] [ES-LAT].mkv"


def test_serie_ruta(tmp_path):
    analysis = _analysis("https://vimeus.com/e/serie?tmdb=2&se=1&ep=3", "Mi Serie", "serie")
    path = build_output_path(tmp_path, analysis, height=720, audio_language="")
    assert path.parent == tmp_path / "Series" / "Mi Serie" / "Temporada 01"
    assert path.name == "Mi Serie - S01E03 [720p].mkv"


def test_anime_ruta(tmp_path):
    analysis = _analysis("https://vimeus.com/e/anime?tmdb=3&se=2&ep=5", "Mi Anime", "anime")
    path = build_output_path(tmp_path, analysis, height=1080, container="mp4")
    assert path.parent == tmp_path / "Anime" / "Mi Anime" / "Temporada 02"
    assert path.suffix == ".mp4"


def test_sin_anio_no_agrega_parentesis(tmp_path):
    analysis = _analysis("https://vimeus.com/e/movie?tmdb=1", "Titulo", "movie")
    path = build_output_path(tmp_path, analysis, height=None, year=None)
    assert path.parent.name == "Titulo"


def test_categoria():
    assert category_for(_analysis("https://vimeus.com/e/movie?tmdb=1", "x", "movie")) == "Peliculas"
    assert category_for(_analysis("https://vimeus.com/e/serie?tmdb=1&se=1&ep=1", "x", "serie")) == "Series"


def test_audio_tag_solo_verificado():
    assert audio_tag("es-419") == "ES-LAT"
    assert audio_tag("es-ES") == "ES-ES"
    assert audio_tag("") == ""


def test_format_size():
    assert organizer.format_size(0) == "0 B"
    assert organizer.format_size(1536).endswith("KB")
    assert organizer.format_size(1024 ** 3).endswith("GB")


def test_sanitize_component_caracteres_invalidos():
    assert paths.sanitize_component('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_component_nombres_reservados():
    assert paths.sanitize_component("CON") == "_CON"
    assert paths.sanitize_component("NUL") == "_NUL"


def test_sanitize_component_largo():
    result = paths.sanitize_component("x" * 400, max_length=50)
    assert len(result) == 50


def test_sanitize_component_vacio():
    assert paths.sanitize_component("   ") == "sin_titulo"


def test_unique_path(tmp_path):
    file = tmp_path / "video.mkv"
    file.write_text("x")
    assert paths.unique_path(file).name == "video (2).mkv"
    (tmp_path / "video (2).mkv").write_text("x")
    assert paths.unique_path(file).name == "video (3).mkv"


def test_rutas_portables_relativas():
    root = paths.project_root()
    assert paths.default_downloads_dir() == root / "Descargas"
    assert paths.settings_file() == root / "config" / "config.json"
    assert paths.history_file() == root / "data" / "history.json"
