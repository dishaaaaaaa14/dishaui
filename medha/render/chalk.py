"""Procedural chalk strokes.

A semantic polyline becomes a slightly wobbly, variable-width stroke plus one
or two faint ghost passes. Everything is deterministic from a seed so cached
frames and screenshots stay stable.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import config

from .geometry import Point, distance, resample_polyline


@dataclass(frozen=True)
class ChalkStroke:
    points: tuple[Point, ...]
    width: float
    color: str
    alpha: float = 1.0


def _normal(points: list[Point], index: int) -> Point:
    before = points[max(0, index - 1)]
    after = points[min(len(points) - 1, index + 1)]
    dx = after[0] - before[0]
    dy = after[1] - before[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return 1.0, 0.0
    return -dy / length, dx / length


def _wobble(
    points: list[Point],
    width: float,
    rng: random.Random,
    jitter: float,
) -> list[Point]:
    if jitter <= 0.0 or len(points) < 2:
        return points
    phase = rng.uniform(0.0, math.tau)
    frequency = rng.uniform(0.08, 0.18)
    amplitude = jitter * rng.uniform(0.55, 1.0)
    out: list[Point] = []
    for index, point in enumerate(points):
        nx, ny = _normal(points, index)
        ripple = math.sin(index * frequency + phase)
        grain = rng.uniform(-0.18, 0.18)
        offset = amplitude * (ripple + grain)
        out.append((point[0] + nx * offset, point[1] + ny * offset))
    return out


def make_chalk(
    points: list[Point],
    width: float,
    color: str = "chalk",
    seed: int = 0,
    jitter: float | None = None,
    passes: int = 2,
) -> list[ChalkStroke]:
    """Turn a pixel-space polyline into one or more chalk strokes."""
    if len(points) < 2 or width <= 0:
        return []

    rng = random.Random(seed)
    jitter_px = config.STROKE_JITTER * 1000.0 if jitter is None else jitter
    spacing = max(1.4, min(4.0, width * 0.8))
    sampled = resample_polyline(points, spacing)
    if len(sampled) < 2:
        return []
    if distance(sampled[0], sampled[-1]) < 1e-3 and len(sampled) < 4:
        return []

    strokes: list[ChalkStroke] = []
    for pass_index in range(max(1, passes)):
        offset = 0.0 if pass_index == 0 else 0.75
        alpha = 0.92 if pass_index == 0 else 0.22
        wobbled = _wobble(sampled, width, rng, jitter_px)
        if offset:
            wobbled = [
                (
                    x + _normal(wobbled, index)[0] * offset,
                    y + _normal(wobbled, index)[1] * offset,
                )
                for index, (x, y) in enumerate(wobbled)
            ]
        strokes.append(
            ChalkStroke(
                points=tuple(wobbled),
                width=max(0.6, width * (1.0 if pass_index == 0 else 0.7)),
                color=color,
                alpha=alpha,
            )
        )
    return strokes
