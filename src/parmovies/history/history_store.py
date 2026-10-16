"""Historial persistente de descargas (JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..security.redaction import redact_url
from ..utilities import paths
from ..utilities.logging_setup import get_logger

_log = get_logger("history")


@dataclass
class HistoryEntry:
    """Entrada del historial de descargas."""

    title: str = ""
    content_type: str = ""
    season: int | None = None
    episode: int | None = None
    quality: str = ""
    resolution: str = ""
    container: str = ""
    audio_language: str = ""
    subtitle_languages: list[str] = field(default_factory=list)
    size_bytes: int = 0
    status: str = ""
    verified: bool = False
    path: str = ""
    source: str = ""
    downloaded_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})


class HistoryStore:
    """Almacen sencillo y persistente del historial."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.history_file()
        self._entries: list[HistoryEntry] = []
        self.load()

    def load(self) -> None:
        self._entries = []
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _log.warning("El historial esta corrupto o no se puede leer; se reinicia.")
            return
        if isinstance(raw, list):
            self._entries = [
                HistoryEntry.from_dict(item) for item in raw if isinstance(item, dict)
            ]

    def save(self) -> None:
        try:
            paths.ensure_dir(self.path.parent)
            payload = [asdict(entry) for entry in self._entries]
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            _log.warning("No se pudo guardar el historial: %s", exc)

    def add(self, entry: HistoryEntry) -> None:
        if not entry.downloaded_at:
            entry.downloaded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        entry.source = redact_url(entry.source)
        self._entries.append(entry)
        self.save()

    @property
    def entries(self) -> list[HistoryEntry]:
        """Entradas ordenadas de la mas reciente a la mas antigua."""

        return list(reversed(self._entries))

    def clear(self) -> None:
        self._entries = []
        self.save()

    def count(self) -> int:
        return len(self._entries)
