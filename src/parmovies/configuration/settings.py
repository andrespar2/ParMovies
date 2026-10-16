"""Configuracion centralizada y portable de ParMovies.

Precedencia de valores (de mayor a menor):

1. Variables de entorno (``PARMOVIES_*``).
2. Archivo de configuracion local (``config/config.json``, excluido de git).
3. Valores por defecto.

Las credenciales nunca se imprimen: use :func:`AppSettings.masked_api_key` y
:func:`AppSettings.masked_view_key` para mostrarlas de forma segura.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from ..security.redaction import mask_secret
from ..utilities import paths

VALID_SUBTITLE_MODES = ("spanish", "all", "manual", "none")
VALID_OUTPUT_FORMATS = ("mkv", "mp4")

DEFAULT_TRUSTED_DOMAINS = (
    "vimeus.com",
    "www.vimeus.com",
    "vimeos.net",
    "www.vimeos.net",
)

# Mapeo de campos a variables de entorno.
_ENV_PREFIX = "PARMOVIES_"


@dataclass
class AppSettings:
    """Configuracion completa de la aplicacion."""

    api_key: str = ""
    view_key: str = ""
    base_url: str = "https://vimeus.com"
    downloads_dir: str = ""
    preferred_quality: str = "best"
    preferred_audio_language: str = "es-419"
    subtitle_mode: str = "spanish"
    output_format: str = "mkv"
    download_all_audio: bool = False
    download_metadata: bool = True
    download_posters: bool = True
    retries: int = 3
    concurrent_downloads: int = 1
    speed_limit_kib: int = 0
    keep_temp_files: bool = False
    enable_logs: bool = True
    ffmpeg_path: str = ""
    trusted_domains: list[str] = field(default_factory=lambda: list(DEFAULT_TRUSTED_DOMAINS))

    # -- Rutas resueltas ---------------------------------------------------
    def resolved_downloads_dir(self) -> Path:
        """Carpeta de descargas efectiva (configurada o portable por defecto)."""

        if self.downloads_dir.strip():
            return Path(os.path.expandvars(os.path.expanduser(self.downloads_dir.strip())))
        return paths.default_downloads_dir()

    def resolved_ffmpeg_dir(self) -> Path | None:
        """Carpeta que contiene ffmpeg/ffprobe, si se ha configurado una ruta."""

        if not self.ffmpeg_path.strip():
            return None
        candidate = Path(os.path.expandvars(os.path.expanduser(self.ffmpeg_path.strip())))
        return candidate if candidate.is_dir() else candidate.parent

    # -- Estado ------------------------------------------------------------
    def is_authenticated(self) -> bool:
        """Indica si hay credenciales basicas definidas."""

        return bool(self.api_key.strip() and self.view_key.strip())

    def masked_api_key(self) -> str:
        return mask_secret(self.api_key)

    def masked_view_key(self) -> str:
        return mask_secret(self.view_key)

    # -- Serializacion -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        valid = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid}
        settings = cls(**filtered)
        settings.normalize()
        return settings

    def normalize(self) -> None:
        """Corrige valores fuera de rango sin lanzar excepciones."""

        self.retries = max(0, int(self.retries))
        self.concurrent_downloads = max(1, int(self.concurrent_downloads))
        self.speed_limit_kib = max(0, int(self.speed_limit_kib))
        if self.subtitle_mode not in VALID_SUBTITLE_MODES:
            self.subtitle_mode = "spanish"
        if self.output_format not in VALID_OUTPUT_FORMATS:
            self.output_format = "mkv"
        if not isinstance(self.trusted_domains, list) or not self.trusted_domains:
            self.trusted_domains = list(DEFAULT_TRUSTED_DOMAINS)

    # -- Carga y guardado --------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        """Carga la configuracion aplicando archivo + variables de entorno."""

        target = path or paths.settings_file()
        settings = cls()
        if target.is_file():
            try:
                raw = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    settings = cls.from_dict(raw)
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                # Configuracion corrupta: se usan los valores por defecto.
                settings = cls()
        settings._apply_env()
        settings.normalize()
        return settings

    def save(self, path: Path | None = None) -> Path:
        """Guarda la configuracion en disco (excluida de git)."""

        target = path or paths.settings_file()
        paths.ensure_dir(target.parent)
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        target.write_text(payload + "\n", encoding="utf-8")
        return target

    def _apply_env(self) -> None:
        """Aplica variables de entorno ``PARMOVIES_*`` sobre la configuracion."""

        for f in fields(self):
            env_name = _ENV_PREFIX + f.name.upper()
            raw = os.environ.get(env_name)
            if raw is None or raw == "":
                continue
            current = getattr(self, f.name)
            if isinstance(current, bool):
                setattr(self, f.name, raw.strip().lower() in {"1", "true", "yes", "si", "on"})
            elif isinstance(current, int):
                try:
                    setattr(self, f.name, int(raw))
                except ValueError:
                    continue
            elif isinstance(current, list):
                setattr(self, f.name, [item.strip() for item in raw.split(",") if item.strip()])
            else:
                setattr(self, f.name, raw)
