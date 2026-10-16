"""Resolucion de rutas portables para ParMovies.

Todas las rutas se resuelven de forma relativa a la ubicacion de la aplicacion
(carpeta del ejecutable cuando esta empaquetada, o raiz del proyecto en
desarrollo) para que el programa sea portable y funcione desde una unidad USB.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Caracteres invalidos en nombres de archivo de Windows.
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Nombres reservados por Windows (comparacion sin extension, sin distinguir mayusculas).
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def is_frozen() -> bool:
    """Indica si la aplicacion corre empaquetada (PyInstaller)."""

    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Raiz de la aplicacion (carpeta del ejecutable o raiz del proyecto)."""

    if is_frozen():
        return Path(sys.executable).resolve().parent
    # src/parmovies/utilities/paths.py -> parents[3] == raiz del repositorio
    return Path(__file__).resolve().parents[3]


def bin_dir() -> Path:
    """Carpeta de binarios de terceros (ffmpeg, ffprobe)."""

    return project_root() / "bin"


def config_dir() -> Path:
    """Carpeta de configuracion local."""

    return project_root() / "config"


def logs_dir() -> Path:
    """Carpeta de registros."""

    return project_root() / "logs"


def default_downloads_dir() -> Path:
    """Carpeta de descargas por defecto (portable)."""

    return project_root() / "Descargas"


def settings_file() -> Path:
    """Ruta del archivo de configuracion local (excluido de git)."""

    return config_dir() / "config.json"


def history_file() -> Path:
    """Ruta del archivo de historial de descargas."""

    return project_root() / "data" / "history.json"


def ensure_dir(path: Path) -> Path:
    """Crea la carpeta indicada (y sus padres) si no existe."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_component(name: str, *, max_length: int = 120, fallback: str = "sin_titulo") -> str:
    """Convierte un texto arbitrario en un componente de ruta seguro en Windows."""

    cleaned = _INVALID_CHARS.sub("", str(name))
    cleaned = cleaned.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Windows no admite puntos o espacios al final de un componente.
    cleaned = cleaned.rstrip(". ")
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")
    return cleaned


def safe_filename(name: str, *, max_length: int = 180, fallback: str = "archivo") -> str:
    """Convierte un texto arbitrario en un nombre de archivo seguro en Windows."""

    sanitized = sanitize_component(name, max_length=max_length, fallback=fallback)
    # Evitar rutas excesivamente largas y nombres ocultos.
    if sanitized.startswith("."):
        sanitized = sanitized.lstrip(".") or fallback
    return sanitized


def unique_path(path: Path) -> Path:
    """Devuelve una ruta libre anadiendo un sufijo numerico si ya existe."""

    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    index = 2
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1
