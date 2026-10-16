"""Desofuscador del empaquetador JavaScript (Dean Edwards).

Los reproductores externos de la cadena de Vimeus entregan su configuracion
dentro de un bloque ``eval(function(p,a,c,k,e,d){...}(...))``. Para analizar la
configuracion real (fuentes HLS y subtitulos) hay que deshacer ese empaquetado.
Se implementa en Python para no depender de Node.js en el equipo del usuario.
"""

from __future__ import annotations

import re

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_EVAL_MARKER = "function(p,a,c,k,e,d)"


def _to_base(number: int, base: int) -> str:
    """Convierte un entero a una cadena en la base indicada."""

    if base < 2 or base > 36:
        base = 36
    if number < base:
        return _DIGITS[number]
    return _to_base(number // base, base) + _DIGITS[number % base]


def unpack(p: str, a: int, c: int, keywords: list[str]) -> str:
    """Deshace el empaquetado sustituyendo los tokens numericos por palabras."""

    result = p
    for index in range(c - 1, -1, -1):
        if index < len(keywords) and keywords[index]:
            token = _to_base(index, a)
            pattern = re.compile(r"\b" + re.escape(token) + r"\b")
            replacement = keywords[index]
            result = pattern.sub(lambda _m, rep=replacement: rep, result)
    return result


def _read_quoted(text: str, start: int) -> tuple[str, int]:
    """Lee una cadena entre comillas simples o dobles desde ``start``."""

    quote = text[start]
    index = start + 1
    buffer: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "\\":
            buffer.append(text[index + 1] if index + 1 < len(text) else "")
            index += 2
            continue
        if char == quote:
            return "".join(buffer), index + 1
        buffer.append(char)
        index += 1
    raise ValueError("Cadena sin cerrar en el programa empaquetado.")


def _split_arguments(text: str) -> list[str]:
    """Divide los argumentos de una llamada respetando comillas y profundidad."""

    arguments: list[str] = []
    depth = 0
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "'\"":
            value, index = _read_quoted(text, index)
            current.append("'" + value + "'")
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        if char == "," and depth == 0:
            arguments.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    tail = "".join(current).strip()
    if tail:
        arguments.append(tail)
    return arguments


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    """Devuelve el indice del cierre que empareja con ``open_char`` en ``start``."""

    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char in "'\"":
            _value, index = _read_quoted(text, index)
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError("No se encontro el cierre del bloque empaquetado.")


def unpack_program(html: str) -> str | None:
    """Localiza el bloque empaquetado en un HTML y devuelve su codigo desofuscado."""

    marker = html.find(_EVAL_MARKER)
    if marker == -1:
        return None

    body_open = html.find("{", marker)
    if body_open == -1:
        return None
    body_close = _find_matching(html, body_open, "{", "}")
    call_open = html.find("(", body_close)
    if call_open == -1:
        return None
    call_close = _find_matching(html, call_open, "(", ")")

    args_text = html[call_open + 1 : call_close]
    arguments = _split_arguments(args_text)
    if len(arguments) < 4:
        return None

    payload = arguments[0]
    if payload and payload[0] in "'\"":
        payload = payload[1:-1]
    try:
        base = int(arguments[1])
        count = int(arguments[2])
    except ValueError:
        return None

    keywords_raw = arguments[3]
    split_marker = ".split('|')"
    if split_marker in keywords_raw:
        keywords_raw = keywords_raw.split(split_marker)[0]
    if keywords_raw and keywords_raw[0] in "'\"":
        keywords_raw = keywords_raw[1:-1]
    keywords = keywords_raw.split("|")

    return unpack(payload, base, count, keywords)
