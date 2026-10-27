"""Vector primitives for the board. All coordinates are normalized board units."""

from __future__ import annotations

import math

from .geometry import Point, clamp

RectTuple = tuple[float, float, float, float]


def _rect_points(rect: RectTuple) -> list[Point]:
    x, y, w, h = rect
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def _arrow_head(tip: Point, tail: Point, size: float = 0.025) -> list[list[Point]]:
    angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
    spread = math.pi / 7.0
    left = (tip[0] - size * math.cos(angle - spread), tip[1] - size * math.sin(angle - spread))
    right = (tip[0] - size * math.cos(angle + spread), tip[1] - size * math.sin(angle + spread))
    return [[tip, left], [tip, right]]


def line(start: Point, end: Point) -> list[list[Point]]:
    return [[start, end]]


def arrow(start: Point, end: Point, head: float = 0.025) -> list[list[Point]]:
    return [[start, end], *_arrow_head(end, start, head)]


def polyline(points: list[Point]) -> list[list[Point]]:
    return [list(points)] if len(points) > 1 else []


def rectangle(rect: RectTuple) -> list[list[Point]]:
    return [_rect_points(rect)]


def circle(center: Point, radius: float, segments: int = 48) -> list[list[Point]]:
    return [
        [
            (
                center[0] + math.cos(math.tau * i / segments) * radius,
                center[1] + math.sin(math.tau * i / segments) * radius,
            )
            for i in range(segments + 1)
        ]
    ]


def ellipse(rect: RectTuple, segments: int = 56) -> list[list[Point]]:
    x, y, w, h = rect
    cx, cy = x + w / 2.0, y + h / 2.0
    return [
        [
            (
                cx + math.cos(math.tau * i / segments) * w / 2.0,
                cy + math.sin(math.tau * i / segments) * h / 2.0,
            )
            for i in range(segments + 1)
        ]
    ]


def axes(rect: RectTuple, head: float = 0.022) -> list[list[Point]]:
    x, y, w, h = rect
    origin = (x, y + h)
    x_end = (x + w, y + h)
    y_end = (x, y)
    return [
        [origin, x_end],
        [origin, y_end],
        *_arrow_head(x_end, origin, head),
        *_arrow_head(y_end, origin, head),
    ]


def waveform(
    rect: RectTuple,
    cycles: float = 3.0,
    amplitude: float = 0.5,
    samples: int = 160,
) -> list[list[Point]]:
    x, y, w, h = rect
    cy = y + h / 2.0
    points: list[Point] = []
    for index in range(samples + 1):
        t = index / samples
        points.append((x + t * w, cy - math.sin(math.tau * cycles * t) * h * amplitude))
    return [points]


def spring(start: Point, end: Point, coils: int = 7, width: float = 0.04) -> list[list[Point]]:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return []
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    points: list[Point] = [start]
    for index in range(coils * 2 + 1):
        t = 0.1 + 0.8 * index / (coils * 2 + 1)
        side = 1.0 if index % 2 == 0 else -1.0
        points.append(
            (
                start[0] + ux * length * t + nx * width * side,
                start[1] + uy * length * t + ny * width * side,
            )
        )
    points.append(end)
    return [points]


def incline(rect: RectTuple) -> list[list[Point]]:
    x, y, w, h = rect
    return [[(x, y + h), (x + w, y), (x + w, y + h), (x, y + h)]]


def block(rect: RectTuple) -> list[list[Point]]:
    return rectangle(rect)


def resistor(rect: RectTuple) -> list[list[Point]]:
    x, y, w, h = rect
    cy = y + h / 2.0
    points: list[Point] = [(x, cy)]
    steps = 6
    for index in range(1, steps):
        px = x + w * index / steps
        points.append((px, cy + (h / 2.0 if index % 2 else -h / 2.0)))
    points.append((x + w, cy))
    return [points]


def battery(rect: RectTuple) -> list[list[Point]]:
    x, y, w, h = rect
    mid = x + w / 2.0
    return [
        [(mid - w * 0.12, y + h * 0.2), (mid - w * 0.12, y + h * 0.8)],
        [(mid + w * 0.12, y + h * 0.36), (mid + w * 0.12, y + h * 0.64)],
        [(x, y + h / 2.0), (mid - w * 0.12, y + h / 2.0)],
        [(mid + w * 0.12, y + h / 2.0), (x + w, y + h / 2.0)],
    ]


def grid(rect: RectTuple, cols: int = 6, rows: int = 4) -> list[list[Point]]:
    x, y, w, h = rect
    strokes: list[list[Point]] = []
    for index in range(cols + 1):
        px = x + w * index / cols
        strokes.append([(px, y), (px, y + h)])
    for index in range(rows + 1):
        py = y + h * index / rows
        strokes.append([(x, py), (x + w, py)])
    return strokes


def normalize_rect(rect: RectTuple) -> RectTuple:
    x, y, w, h = rect
    x = clamp(x, 0.0, 1.0)
    y = clamp(y, 0.0, 1.0)
    return x, y, clamp(w, 0.0, 1.0 - x), clamp(h, 0.0, 1.0 - y)
