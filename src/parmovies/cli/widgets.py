"""Componentes reutilizables de la interfaz de terminal."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ..version import APP_NAME, __version__
from .theme import separator

BAR_FILLED = "█"
BAR_EMPTY = "░"


def header_bar(console: Console, subtitle: str = "") -> None:
    """Cabecera compacta de una seccion."""

    left = APP_NAME.upper()
    right = f"v{__version__}"
    padding = max(console.width - len(left) - len(right) - 4, 1)
    console.print(f"[pm.title]  {left}[/pm.title]{' ' * padding}[pm.dim]{right}[/pm.dim]")
    if subtitle:
        console.print(f"[pm.grey]  {subtitle}[/pm.grey]")
    separator(console, min(console.width, 62))


def render_menu(
    console: Console,
    items: list[tuple[str, str]],
    *,
    title: str = "",
    subtitle: str = "",
    note: str = "",
) -> None:
    """Muestra un menu alineado con claves numericas."""

    header_bar(console, subtitle)
    if title:
        console.print(f"  [pm.soft]{title}[/pm.soft]")
        console.print()
    for key, label in items:
        console.print(f"  [pm.menu.key][{key}][/pm.menu.key]  [pm.menu.item]{label}[/pm.menu.item]")
    console.print()
    if note:
        console.print(f"  [pm.dim]{note}[/pm.dim]")
        console.print()
    separator(console, min(console.width, 62))


def prompt_choice(console: Console, prompt: str = "Selecciona una opcion") -> str:
    """Solicita una opcion al usuario."""

    try:
        return console.input(f"  [pm.prompt]{prompt} > [/pm.prompt]").strip()
    except (EOFError, KeyboardInterrupt):
        return "00"


def prompt_text(console: Console, prompt: str, *, default: str = "") -> str:
    """Solicita un texto libre al usuario."""

    suffix = f" [pm.dim]({default})[/pm.dim]" if default else ""
    try:
        value = console.input(f"  [pm.prompt]{prompt}[/pm.prompt]{suffix} [pm.dim]>[/pm.dim] ")
    except (EOFError, KeyboardInterrupt):
        return default
    value = value.strip()
    return value or default


def prompt_si_no(console: Console, prompt: str, *, default: bool = False) -> bool:
    """Pregunta de si/no."""

    hint = "S/n" if default else "s/N"
    value = prompt_text(console, f"{prompt} [{hint}]", default="s" if default else "n").lower()
    return value in ("s", "si", "sí", "y", "yes")


def pause(console: Console, message: str = "Pulsa Enter para continuar") -> None:
    """Espera a que el usuario continue."""

    try:
        console.input(f"  [pm.dim]{message}...[/pm.dim]")
    except (EOFError, KeyboardInterrupt):
        pass


def info(console: Console, message: str) -> None:
    console.print(f"  [pm.soft]*[/pm.soft] [pm.text]{message}[/pm.text]")


def warn(console: Console, message: str) -> None:
    console.print(f"  [pm.warn]![/pm.warn] [pm.soft]{message}[/pm.soft]")


def error(console: Console, message: str) -> None:
    console.print(f"  [pm.error]x[/pm.error] [pm.soft]{message}[/pm.soft]")


def success(console: Console, message: str) -> None:
    console.print(f"  [pm.ok]+[/pm.ok] [pm.text]{message}[/pm.text]")


def dim(console: Console, message: str) -> None:
    console.print(f"  [pm.dim]{message}[/pm.dim]")


def render_bar(percent: float | None, width: int = 30) -> str:
    """Barra de progreso moderna; indeterminada cuando el porcentaje es None."""

    if percent is None:
        return f"[pm.dim][{' ' * width}][/pm.dim]"
    ratio = max(0.0, min(1.0, percent / 100.0))
    filled = int(round(ratio * width))
    bar = BAR_FILLED * filled + BAR_EMPTY * (width - filled)
    return f"[pm.text]{bar}[/pm.text]"


def format_bytes(size: int) -> str:
    """Formatea bytes en unidades legibles."""

    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def format_speed(bytes_per_second: float) -> str:
    if not bytes_per_second or bytes_per_second <= 0:
        return "0 B/s"
    return f"{format_bytes(int(bytes_per_second))}/s"


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "desconocida"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_table(*columns: str, title: str = "") -> Table:
    """Crea una tabla con el estilo AMOLED."""

    table = Table(
        title=title or None,
        show_header=True,
        header_style="pm.label",
        border_style="pm.rule",
        show_lines=False,
        pad_edge=False,
        expand=False,
    )
    for column in columns:
        table.add_column(column, style="pm.soft", overflow="fold")
    return table
