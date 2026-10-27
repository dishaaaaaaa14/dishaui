"""Pure 2D geometry used by the board renderer.

Board coordinates are normalized: (0,0) top-left, (1,1) bottom-right.
Pixel coordinates are y-down. NDC coordinates are y-up.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

Point = tuple[float, float]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_point(a: Point, b: Point, t: float) -> Point:
    return lerp(a[0], b[0], t), lerp(a[1], b[1], t)


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def ease_out_cubic(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def polyline_length(points: list[Point]) -> float:
    return sum(distance(a, b) for a, b in itertools.pairwise(points))


def resample_polyline(points: list[Point], spacing: float) -> list[Point]:
    """Resample a polyline at a roughly constant arc-length spacing."""
    if not points:
        return []
    if len(points) == 1 or spacing <= 1e-9:
        return list(points)

    out = [points[0]]
    carry = 0.0
    for start, end in itertools.pairwise(points):
        segment = distance(start, end)
        if segment <= 1e-9:
            continue
        travelled = spacing - carry
        while travelled <= segment:
            out.append(lerp_point(start, end, travelled / segment))
            travelled += spacing
        carry = segment - (travelled - spacing)
    if distance(out[-1], points[-1]) > 1e-6:
        out.append(points[-1])
    return out


def partial_polyline(points: list[Point], fraction: float) -> list[Point]:
    """Return the first `fraction` of a polyline by arc length."""
    if not points:
        return []
    fraction = clamp(fraction, 0.0, 1.0)
    if fraction <= 0.0:
        return []
    if fraction >= 1.0:
        return list(points)

    target = polyline_length(points) * fraction
    out = [points[0]]
    travelled = 0.0
    for start, end in itertools.pairwise(points):
        segment = distance(start, end)
        if travelled + segment >= target:
            t = 0.0 if segment <= 1e-9 else (target - travelled) / segment
            out.append(lerp_point(start, end, t))
            return out
        out.append(end)
        travelled += segment
    return out


def chaikin(points: list[Point], iterations: int = 1) -> list[Point]:
    """Corner-cutting smoothing. Endpoints are preserved."""
    if len(points) < 3 or iterations <= 0:
        return list(points)
    result = list(points)
    for _ in range(iterations):
        smoothed = [result[0]]
        for a, b in itertools.pairwise(result):
            smoothed.append(lerp_point(a, b, 0.25))
            smoothed.append(lerp_point(a, b, 0.75))
        smoothed.append(result[-1])
        result = smoothed
    return result


def bounds(points: list[Point]) -> tuple[float, float, float, float]:
    if not points:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True)
class Transform:
    width: int
    height: int

    def to_px(self, point: Point) -> Point:
        return point[0] * self.width, point[1] * self.height

    def to_ndc(self, point: Point) -> Point:
        return 2.0 * point[0] / self.width - 1.0, 1.0 - 2.0 * point[1] / self.height

    def norm_to_ndc(self, point: Point) -> Point:
        return self.to_ndc(self.to_px(point))

    def px_length(self, normalized: float) -> float:
        return normalized * min(self.width, self.height)
