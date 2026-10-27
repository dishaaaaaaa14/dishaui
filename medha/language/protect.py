"""Protect equations, units, and LaTeX spans while translating prose."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MATH_PATTERNS = (
    r"\$\$.+?\$\$",
    r"\$[^$\n]+\$",
    r"\\\(.+?\\\)",
    r"\\\[.+?\\\]",
    r"\\[A-Za-z]+(?:\{[^{}]*\})*",
    r"\b\d+(?:\.\d+)?\s*(?:m/s\^2|m/s|km/h|kg|mg|km|cm|mm|N|J|W|V|A|Hz|Pa|mol|K)\b",
    r"\b[A-Za-z]\s*=\s*[^,.;\n]+",
)
_MATH_RE = re.compile("|".join(f"(?:{pattern})" for pattern in _MATH_PATTERNS), re.DOTALL)
_MARKER_RE = re.compile(r"\[\[\s*M(\d+)\s*\]\]")
_MARKER_STRIP_RE = re.compile(r"\[\[\s*M\d+\s*\]\]")


@dataclass(frozen=True)
class ProtectedText:
    original: str
    protected: str
    values: tuple[str, ...]

    def restore(self, translated: str) -> str:
        if not self.values:
            return translated
        found: set[int] = set()

        def replace(match: re.Match[str]) -> str:
            index = int(match.group(1))
            if index >= len(self.values):
                return match.group(0)
            found.add(index)
            return self.values[index]

        restored = _MARKER_RE.sub(replace, translated)
        if found != set(range(len(self.values))):
            return self.original
        return restored

    def has_prose(self) -> bool:
        stripped = _MARKER_STRIP_RE.sub("", self.protected)
        return bool(re.search(r"[A-Za-z]", stripped))


class MathProtector:
    def __init__(self) -> None:
        self._counter = 0

    def protect(self, text: str) -> ProtectedText:
        values: list[str] = []
        parts: list[str] = []
        cursor = 0
        for match in _MATH_RE.finditer(text):
            parts.append(text[cursor : match.start()])
            values.append(match.group(0))
            parts.append(f"[[M{self._counter}]]")
            self._counter += 1
            cursor = match.end()
        parts.append(text[cursor:])
        return ProtectedText(
            original=text,
            protected="".join(parts),
            values=tuple(values),
        )
