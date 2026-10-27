from __future__ import annotations

import pytest

from medha.render import shapes


def test_line_and_arrow() -> None:
    assert shapes.line((0.0, 0.0), (1.0, 0.0)) == [[(0.0, 0.0), (1.0, 0.0)]]
    assert len(shapes.arrow((0.0, 0.0), (1.0, 0.0))) == 3


def test_axes_has_two_axes_and_heads() -> None:
    strokes = shapes.axes((0.1, 0.1, 0.8, 0.8))
    assert len(strokes) == 6


def test_circle_and_ellipse_are_closed() -> None:
    circle = shapes.circle((0.5, 0.5), 0.1)[0]
    assert circle[0] == circle[-1]
    ellipse = shapes.ellipse((0.2, 0.2, 0.4, 0.2))[0]
    assert ellipse[0] == pytest.approx(ellipse[-1])


def test_grid_and_waveform() -> None:
    assert len(shapes.grid((0.0, 0.0, 1.0, 1.0), cols=3, rows=2)) == 7
    wave = shapes.waveform((0.0, 0.0, 1.0, 1.0), samples=20)[0]
    assert len(wave) == 21


def test_normalize_rect_clamps() -> None:
    assert shapes.normalize_rect((0.9, 0.95, 0.5, 0.5)) == pytest.approx((0.9, 0.95, 0.1, 0.05))
