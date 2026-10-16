"""Registro de eventos de ParMovies.

Los registros se escriben en ``logs/parmovies.log`` y nunca incluyen
credenciales: los mensajes pasan por la capa de redaccion de seguridad.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..security.redaction import redact_text
from ..utilities import paths

_LOGGER_NAME = "parmovies"
_configured = False


class _RedactingFilter(logging.Filter):
    """Filtro que elimina credenciales de los mensajes registrados."""

    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._secrets = secrets

    def set_secrets(self, secrets: tuple[str, ...]) -> None:
        self._secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            record.msg = redact_text(message, self._secrets)
            record.args = ()
        except Exception:  # pragma: no cover - nunca debe romper el registro
            return True
        return True


_filter = _RedactingFilter()


def configure_logging(enabled: bool = True, secrets: tuple[str, ...] = ()) -> logging.Logger:
    """Configura el registrador raiz de ParMovies."""

    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _filter.set_secrets(tuple(s for s in secrets if s))

    if not enabled:
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        _configured = True
        return logger

    if not _configured:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

        log_file = paths.ensure_dir(paths.logs_dir()) / "parmovies.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        file_handler.addFilter(_filter)
        logger.addHandler(file_handler)
        _configured = True

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Devuelve un registrador hijo de ParMovies."""

    if name:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)


def update_secrets(secrets: tuple[str, ...]) -> None:
    """Actualiza los secretos que deben redactarse en los registros."""

    _filter.set_secrets(tuple(s for s in secrets if s))


def log_path() -> Path:
    return paths.logs_dir() / "parmovies.log"
