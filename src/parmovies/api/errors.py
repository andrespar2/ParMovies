"""Excepciones especificas de la integracion con Vimeus."""

from __future__ import annotations


class VimeusError(Exception):
    """Error base de la integracion con Vimeus."""


class VimeusAuthError(VimeusError):
    """Credenciales ausentes o invalidas (HTTP 401)."""


class VimeusNotFoundError(VimeusError):
    """Contenido no encontrado (HTTP 404)."""


class VimeusBadRequestError(VimeusError):
    """Parametros invalidos (HTTP 400)."""


class VimeusAPIError(VimeusError):
    """Respuesta de error generica de la API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class VimeusNetworkError(VimeusError):
    """Fallo de red o de conexion."""


class SourceNotSupportedError(VimeusError):
    """La fuente no ofrece un medio descargable compatible."""
