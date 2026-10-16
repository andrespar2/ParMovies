"""Tema visual Black Modern AMOLED para la interfaz de ParMovies.

Paleta sobria: blanco para el texto principal, grises para el secundario y
separadores discretos. No se usan colores saturados.
"""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

WHITE = "#ffffff"
SOFT = "#d0d0d0"
GREY = "#8a8a8a"
DIM = "#5f5f5f"
FAINT = "#3a3a3a"
ALERT = "#c9a227"

PARMOVIES_THEME = Theme(
    {
        "pm.title": f"bold {WHITE}",
        "pm.text": WHITE,
        "pm.soft": SOFT,
        "pm.grey": GREY,
        "pm.dim": DIM,
        "pm.faint": FAINT,
        "pm.accent": f"bold {WHITE}",
        "pm.rule": FAINT,
        "pm.label": GREY,
        "pm.value": WHITE,
        "pm.ok": f"bold {WHITE}",
        "pm.warn": ALERT,
        "pm.error": f"bold {SOFT}",
        "pm.selected": f"black on {SOFT}",
        "pm.menu.key": f"bold {WHITE}",
        "pm.menu.item": SOFT,
        "pm.prompt": f"bold {WHITE}",
    }
)


def create_console() -> Console:
    """Crea la consola Rich con el tema AMOLED."""

    return Console(
        theme=PARMOVIES_THEME,
        highlight=False,
        soft_wrap=False,
        emoji=False,
        legacy_windows=False,
    )


def separator(console: Console, width: int | None = None) -> None:
    """Imprime un separador horizontal discreto."""

    total = width or min(console.width, 72)
    console.print(f"[pm.rule]{'-' * total}[/pm.rule]")


def label_value(console: Console, label: str, value: str, *, label_width: int = 14) -> None:
    """Imprime una linea ``Etiqueta:   Valor`` alineada."""

    console.print(f"[pm.label]{label:<{label_width}}[/pm.label] [pm.value]{value}[/pm.value]")
