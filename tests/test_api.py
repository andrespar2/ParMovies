"""Pruebas del cliente HTTP de la API de Vimeus con transporte simulado."""

from __future__ import annotations

import httpx
import pytest

from parmovies.api.errors import (
    VimeusAuthError,
    VimeusBadRequestError,
    VimeusNotFoundError,
)
from parmovies.api.vimeus import VimeusClient


def make_client(handler: httpx.MockTransport) -> VimeusClient:
    """Crea un cliente real cuyo transporte HTTP es simulado."""

    client = VimeusClient("ak_prueba", "https://vimeus.com")
    client._client = httpx.Client(
        transport=handler,
        base_url="https://vimeus.com",
        headers={"X-API-Key": "ak_prueba"},
    )
    return client


def test_list_movies_parsea_paginacion():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-API-Key") == "ak_prueba"
        assert request.url.path == "/api/listing/movies"
        assert request.url.params.get("page") == "2"
        return httpx.Response(
            200,
            json={
                "data": {
                    "result": [
                        {"title": "Pelicula", "tmdb_id": 264420, "quality": "FULL HD"},
                        {"title": "Otra", "tmdb_id": "776305"},
                    ],
                    "pages": 5,
                    "current_page": 2,
                    "total_results": 500,
                }
            },
        )

    with make_client(httpx.MockTransport(handler)) as client:
        page = client.list_movies(page=2)

    assert len(page.items) == 2
    assert page.items[0].title == "Pelicula"
    assert page.items[0].tmdb_id == 264420
    assert page.items[1].tmdb_id == 776305
    assert page.total_pages == 5
    assert page.current_page == 2
    assert page.total_results == 500
    assert page.has_next is True
    assert page.has_prev is True


def test_list_episodes_envia_parametros():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"data": {"result": [], "pages": 1}})

    with make_client(httpx.MockTransport(handler)) as client:
        page = client.list_episodes(1399, season=3, page=1)

    assert captured.get("tmdb_id") == "1399"
    assert captured.get("season") == "3"
    assert captured.get("page") == "1"
    assert page.items == []


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, VimeusAuthError),
        (404, VimeusNotFoundError),
        (400, VimeusBadRequestError),
    ],
)
def test_errores_http(status, error):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={})

    with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(error):
            client.list_movies(page=1)


def test_validate_credentials_sin_api_key():
    client = VimeusClient("", "https://vimeus.com")
    with pytest.raises(VimeusAuthError):
        client.validate_credentials()
    client.close()


def test_fetch_text_propaga_codigo_de_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with make_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(Exception):
            client.fetch_text("https://vimeus.com/x")
