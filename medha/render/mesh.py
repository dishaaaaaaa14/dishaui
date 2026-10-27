"""Triangle mesh generation for thick chalk polylines.

The mesh is built in pixel space (so stroke width is in pixels) and converted to
NDC vertices as it is emitted. Vertex layout: x, y, r, g, b, a.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .chalk import ChalkStroke
from .color import RGBA, rgba
from .geometry import Point, Transform, distance

FLOATS_PER_VERTEX = 6


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[float, ...] = ()

    @property
    def vertex_count(self) -> int:
        return len(self.vertices) // FLOATS_PER_VERTEX

    def __bool__(self) -> bool:
        return bool(self.vertices)


def _dedupe(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for point in points:
        if not out or distance(out[-1], point) > 1e-4:
            out.append(point)
    return out


def _tangents(points: list[Point]) -> list[Point]:
    tangents: list[Point] = []
    for index in range(len(points)):
        before = points[max(0, index - 1)]
        after = points[min(len(points) - 1, index + 1)]
        dx = after[0] - before[0]
        dy = after[1] - before[1]
        length = math.hypot(dx, dy)
        tangents.append((dx / length, dy / length) if length > 1e-9 else (1.0, 0.0))
    return tangents


def _offsets(points: list[Point], half_width: float) -> tuple[list[Point], list[Point]]:
    tangents = _tangents(points)
    left: list[Point] = []
    right: list[Point] = []
    for index, (point, tangent) in enumerate(zip(points, tangents, strict=False)):
        nx, ny = -tangent[1], tangent[0]
        scale = 1.0
        if 0 < index < len(points) - 1:
            pnx, pny = -tangents[index - 1][1], tangents[index - 1][0]
            miter_x, miter_y = pnx + nx, pny + ny
            miter_len = math.hypot(miter_x, miter_y)
            if miter_len > 1e-9:
                miter_x /= miter_len
                miter_y /= miter_len
                cos_half = max(0.35, miter_x * nx + miter_y * ny)
                scale = min(2.0, 1.0 / cos_half)
                nx, ny = miter_x, miter_y
        left.append((point[0] + nx * half_width * scale, point[1] + ny * half_width * scale))
        right.append((point[0] - nx * half_width * scale, point[1] - ny * half_width * scale))
    return left, right


def _append_vertex(
    out: list[float],
    transform: Transform,
    point: Point,
    color: RGBA,
) -> None:
    nx, ny = transform.to_ndc(point)
    out.extend((nx, ny, color[0], color[1], color[2], color[3]))


def _append_triangle(
    out: list[float],
    transform: Transform,
    a: Point,
    b: Point,
    c: Point,
    color: RGBA,
) -> None:
    _append_vertex(out, transform, a, color)
    _append_vertex(out, transform, b, color)
    _append_vertex(out, transform, c, color)


def _append_disc(
    out: list[float],
    transform: Transform,
    center: Point,
    radius: float,
    color: RGBA,
    segments: int = 10,
) -> None:
    for index in range(segments):
        angle_a = math.tau * index / segments
        angle_b = math.tau * (index + 1) / segments
        a = (center[0] + math.cos(angle_a) * radius, center[1] + math.sin(angle_a) * radius)
        b = (center[0] + math.cos(angle_b) * radius, center[1] + math.sin(angle_b) * radius)
        _append_triangle(out, transform, center, a, b, color)


def tessellate_stroke(
    stroke: ChalkStroke,
    transform: Transform,
    alpha_scale: float = 1.0,
) -> list[float]:
    points = _dedupe(list(stroke.points))
    if len(points) < 2:
        return []
    color = rgba(stroke.color, stroke.alpha * alpha_scale)
    half = stroke.width / 2.0
    left, right = _offsets(points, half)
    out: list[float] = []
    for index in range(len(points) - 1):
        _append_triangle(out, transform, left[index], left[index + 1], right[index + 1], color)
        _append_triangle(out, transform, left[index], right[index + 1], right[index], color)
    _append_disc(out, transform, points[0], half, color)
    _append_disc(out, transform, points[-1], half, color)
    return out


def build_mesh(strokes: list[ChalkStroke], transform: Transform, alpha_scale: float = 1.0) -> Mesh:
    vertices: list[float] = []
    for stroke in strokes:
        vertices.extend(tessellate_stroke(stroke, transform, alpha_scale))
    return Mesh(tuple(vertices))
