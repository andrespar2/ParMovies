"""Arte ASCII original de ParMovies.

Logotipo de bloques para el nombre PARMOVIES, mas un encabezado equilibrado.
Se degrada a un banner compacto en terminales estrechas.
"""

from __future__ import annotations

from rich.console import Console

from ..version import APP_NAME, APP_TAGLINE, __version__
from .theme import separator

# Fuente de bloques 5x5 propia (cada letra mide 5 columnas de ancho).
_GLYPHS: dict[str, list[str]] = {
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "A": ["████ ", "█   █", "█████", "█   █", "█   █"],
    "R": ["████ ", "█   █", "████ ", "█ █  ", "█  █ "],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "O": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "E": ["█████", "█    ", "███  ", "█    ", "█████"],
    "S": ["█████", "█    ", "████ ", "    █", "████ "],
}


def logo_lines(word: str = "PARMOVIES") -> list[str]:
    """Construye las lineas del logotipo para una palabra."""

    rows = ["", "", "", "", ""]
    for position, letter in enumerate(word.upper()):
        glyph = _GLYPHS.get(letter)
        if glyph is None:
            continue
        for index in range(5):
            rows[index] += glyph[index]
            if position != len(word) - 1:
                rows[index] += " "
    return rows


def render_logo(console: Console) -> None:
    """Imprime el logotipo adaptandose al ancho de la terminal."""

    if console.width >= 66:
        for line in logo_lines():
            console.print(f"[pm.title]  {line}[/pm.title]")
    else:
        console.print(f"[pm.title]  {APP_NAME.upper()}[/pm.title]")


def render_header(console: Console, *, subtitle: str = "") -> None:
    """Imprime el encabezado completo (logotipo, lema, version y separador)."""

    render_logo(console)
    console.print(
        f"[pm.grey]  {APP_TAGLINE}[/pm.grey]"
        f"[pm.faint]  ·  [/pm.faint][pm.dim]v{__version__}[/pm.dim]"
    )
    if subtitle:
        console.print(f"[pm.dim]  {subtitle}[/pm.dim]")
    separator(console, min(console.width, 62))
