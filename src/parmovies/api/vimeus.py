"""Cliente HTTP de la API de Vimeus.

Endpoints documentados:

* ``GET /api/listing/movies``
* ``GET /api/listing/series``
* ``GET /api/listing/animes``
* ``GET /api/listing/episodes``

La autenticacion se realiza mediante el encabezado ``X-API-Key``. La API esta
protegida por Cloudflare y rechaza (HTTP 403) las peticiones con el
``User-Agent`` por defecto de Python, por lo que se envia uno de navegador.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from ..utilities.logging_setup import get_logger
from .errors import (
    VimeusAPIError,
    VimeusAuthError,
    VimeusBadRequestError,
    VimeusNetworkError,
    VimeusNotFoundError,
)
from .models import ListingPage

DEFAULT_BASE_URL = "https://vimeus.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_log = get_logger("api")


class VimeusClient:
    """Cliente sincrono y reutilizable de la API de Vimeus."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 25.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    # -- Ciclo de vida -----------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VimeusClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Nivel bajo --------------------------------------------------------
    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as exc:  # pragma: no cover - depende de red
            _log.warning("Fallo de red consultando %s: %s", path, exc)
            raise VimeusNetworkError(
                "No se pudo conectar con Vimeus. Verifique su conexion a Internet."
            ) from exc

        status = response.status_code
        if status == 401:
            raise VimeusAuthError(
                "Autenticacion rechazada por Vimeus (401). Revise la API Key en Configuracion."
            )
        if status == 404:
            raise VimeusNotFoundError("El contenido solicitado no existe en Vimeus (404).")
        if status == 400:
            raise VimeusBadRequestError("La API rechazo la solicitud por parametros invalidos (400).")
        if status == 403:
            raise VimeusAPIError(
                "Vimeus bloqueo la solicitud (403). Puede deberse a un filtro de seguridad.",
                status_code=status,
            )
        if status >= 400:
            raise VimeusAPIError(
                f"Vimeus respondio con el codigo HTTP {status}.", status_code=status
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise VimeusAPIError("Vimeus devolvio una respuesta que no es JSON valido.") from exc

        if not isinstance(payload, dict):
            raise VimeusAPIError("Vimeus devolvio una estructura inesperada.")
        return payload

    # -- Validacion de credenciales ---------------------------------------
    def validate_credentials(self) -> bool:
        """Comprueba las credenciales con una solicitud real."""

        if not self.api_key:
            raise VimeusAuthError("No hay una API Key configurada.")
        page = self.list_movies(page=1)
        return bool(page.items) or page.total_pages >= 1

    # -- Listados ----------------------------------------------------------
    def _listing(self, endpoint: str, params: dict[str, Any], page: int) -> ListingPage:
        query = {"page": page, **params}
        payload = self._request(f"/api/listing/{endpoint}", query)
        page_result = ListingPage.from_api(payload, requested_page=page)
        _log.info(
            "Listado %s pagina %s: %s elementos de %s",
            endpoint,
            page,
            len(page_result.items),
            page_result.total_pages,
        )
        return page_result

    def list_movies(self, page: int = 1) -> ListingPage:
        return self._listing("movies", {}, page)

    def list_series(self, page: int = 1) -> ListingPage:
        return self._listing("series", {}, page)

    def list_animes(self, page: int = 1) -> ListingPage:
        return self._listing("animes", {}, page)

    def list_episodes(self, tmdb_id: int, season: int = 1, page: int = 1) -> ListingPage:
        return self._listing("episodes", {"tmdb_id": tmdb_id, "season": season}, page)

    # -- HTML --------------------------------------------------------------
    def fetch_html(self, url: str, *, referer: str | None = None) -> str:
        """Descarga una pagina HTML (embed o reproductor) respetando el origen."""

        headers: dict[str, str] = {"Accept": "text/html,application/xhtml+xml"}
        if referer:
            headers["Referer"] = referer
        try:
            response = self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise VimeusNetworkError(f"No se pudo obtener {url}: {exc}") from exc
        if response.status_code >= 400:
            raise VimeusAPIError(
                f"El origen respondio con el codigo HTTP {response.status_code}.",
                status_code=response.status_code,
            )
        return response.text
