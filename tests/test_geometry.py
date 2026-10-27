from __future__ import annotations

import pytest

from medha.render.geometry import (
    Transform,
    chaikin,
    ease_in_out,
    ease_out_cubic,
    partial_polyline,
    polyline_length,
    resample_polyline,
)


def test_transform_round_trip() -> None:
    transform = Transform(100, 50)
    assert transform.to_px((0.0, 0.0)) == (0.0, 0.0)
    assert transform.to_px((0.5, 0.5)) == (50.0, 25.0)
    assert transform.to_ndc((0.0, 0.0)) == (-1.0, 1.0)
    assert transform.to_ndc((100.0, 50.0)) == (1.0, -1.0)


def test_polyline_length() -> None:
    assert polyline_length([(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]) == pytest.approx(7.0)


def test_resample_preserves_endpoints() -> None:
    points = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    sampled = resample_polyline(points, 1.0)
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]
    assert len(sampled) >= 7


def test_partial_polyline() -> None:
    points = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    half = partial_polyline(points, 0.5)
    assert half[-1] == pytest.approx((3.0, 0.5))
    assert partial_polyline(points, 0.0) == []
    assert partial_polyline(points, 1.0) == points


def test_chaikin_keeps_endpoints() -> None:
    points = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
    smoothed = chaikin(points, 2)
    assert smoothed[0] == points[0]
    assert smoothed[-1] == points[-1]
    assert len(smoothed) > len(points)


def test_easing_bounds() -> None:
    for ease in (ease_out_cubic, ease_in_out):
        assert ease(0.0) == pytest.approx(0.0)
        assert ease(1.0) == pytest.approx(1.0)
        assert 0.0 <= ease(0.5) <= 1.0
