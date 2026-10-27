"""Board palette. Colors are linear-ish sRGB floats in 0..1."""

from __future__ import annotations

from config import (
    CHALK_COLOR,
    DIAGRAM_COLOR,
    HIGHLIGHT_COLOR,
    MATH_COLOR,
)

RGBA = tuple[float, float, float, float]

PALETTE: dict[str, tuple[float, float, float]] = {
    "chalk": CHALK_COLOR,
    "math": MATH_COLOR,
    "diagram": DIAGRAM_COLOR,
    "yellow": HIGHLIGHT_COLOR,
    "red": (1.00, 0.45, 0.38),
    "blue": (0.55, 0.78, 1.00),
    "green": (0.58, 0.95, 0.68),
    "orange": (1.00, 0.68, 0.32),
    "white": (1.00, 1.00, 1.00),
}


def rgba(name: str, alpha: float = 1.0) -> RGBA:
    red, green, blue = PALETTE.get(name, PALETTE["chalk"])
    return red, green, blue, max(0.0, min(1.0, alpha))
