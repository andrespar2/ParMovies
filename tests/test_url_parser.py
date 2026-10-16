"""Pruebas del analizador de enlaces y entradas."""

from __future__ import annotations

import pytest

from parmovies.analyzers.errors import AnalysisError
from parmovies.analyzers.url_parser import parse_input

DOMAINS = ("vimeus.com", "vimeos.net")


def test_url_pelicula_tmdb():
    req = parse_input("https://vimeus.com/e/movie?tmdb=99861&view_key=CLAVE", DOMAINS)
    assert req.kind == "movie"
    assert req.tmdb_id == 99861
    assert req.view_key == "CLAVE"
    assert req.season is None and req.episode is None


def test_url_pelicula_imdb():
    req = parse_input("https://vimeus.com/e/movie?imdb=tt0109830&view_key=CLAVE", DOMAINS)
    assert req.imdb_id == "tt0109830"
    assert req.tmdb_id is None


def test_url_serie_con_episodio():
    req = parse_input("https://vimeus.com/e/serie?tmdb=1399&se=1&ep=3&view_key=CLAVE", DOMAINS)
    assert req.kind == "serie"
    assert req.season == 1
    assert req.episode == 3
    assert req.is_episode


def test_url_anime():
    req = parse_input("https://vimeus.com/e/anime?tmdb=1063&se=2&ep=5", DOMAINS)
    assert req.kind == "anime"
    assert req.season == 2 and req.episode == 5


def test_parametros_en_distinto_orden_y_extra():
    url = "https://vimeus.com/e/serie?ref=abc&ep=2&view_key=K&tmdb=1399&extra=1&se=1"
    req = parse_input(url, DOMAINS)
    assert req.tmdb_id == 1399
    assert req.season == 1 and req.episode == 2


def test_extrae_src_de_iframe():
    html = (
        '<iframe src="https://vimeus.com/e/movie?tmdb=99861&view_key=K" '
        'width="100%" height="100%" frameborder="0" allowfullscreen '
        'referrerpolicy="origin"></iframe>'
    )
    req = parse_input(html, DOMAINS)
    assert req.origin == "iframe"
    assert req.tmdb_id == 99861
    assert req.kind == "movie"


def test_dominio_no_autorizado():
    with pytest.raises(AnalysisError, match="no esta autorizado"):
        parse_input("https://evil.example.com/e/movie?tmdb=1&view_key=K", DOMAINS)


def test_protocolo_invalido():
    with pytest.raises(AnalysisError, match="http o https"):
        parse_input("file:///C:/windows/system32/calc.exe", DOMAINS)


def test_destino_local_rechazado():
    with pytest.raises(AnalysisError):
        parse_input("http://127.0.0.1/e/movie?tmdb=1", DOMAINS)
    with pytest.raises(AnalysisError):
        parse_input("http://localhost/e/movie?tmdb=1", DOMAINS)


def test_sin_identificador():
    with pytest.raises(AnalysisError, match="tmdb ni imdb"):
        parse_input("https://vimeus.com/e/movie?view_key=K", DOMAINS)


def test_parametro_no_numerico():
    with pytest.raises(AnalysisError, match="numero entero"):
        parse_input("https://vimeus.com/e/movie?tmdb=abc", DOMAINS)


def test_episodio_incompleto():
    with pytest.raises(AnalysisError, match="temporada"):
        parse_input("https://vimeus.com/e/serie?tmdb=1399&se=1", DOMAINS)


def test_imdb_invalido():
    with pytest.raises(AnalysisError, match="IMDb"):
        parse_input("https://vimeus.com/e/movie?imdb=12345", DOMAINS)


def test_ruta_desconocida():
    with pytest.raises(AnalysisError, match="tipo de contenido"):
        parse_input("https://vimeus.com/otra/ruta?tmdb=1", DOMAINS)


def test_entrada_vacia():
    with pytest.raises(AnalysisError, match="ningun enlace"):
        parse_input("   ", DOMAINS)


def test_enlace_d_catalogo_se_convierte():
    req = parse_input("https://vimeus.com/d/series?tmdb=1399&se=1&ep=1&view_key=K", DOMAINS)
    assert req.kind == "serie"
    assert req.episode == 1
