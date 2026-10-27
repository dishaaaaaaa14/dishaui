from __future__ import annotations

import pytest

from medha.render.geometry import Transform
from medha.render.scene import Board


def test_board_text_and_shapes() -> None:
    board = Board()
    text = board.add_text("Medha", at=(0.1, 0.1), size=0.1)
    axes = board.add_shape("axes", rect=(0.5, 0.2, 0.3, 0.3))
    assert text
    assert len(axes) >= 4
    mesh = board.build(Transform(800, 600))
    assert mesh
    assert mesh.vertex_count > 0


def test_board_clear() -> None:
    board = Board()
    board.add_polyline([(0.0, 0.0), (1.0, 1.0)])
    assert board.items
    board.clear()
    assert not board.items
    assert not board.build(Transform(100, 100))


def test_progress_hides_strokes() -> None:
    board = Board()
    item = board.add_polyline([(0.1, 0.1), (0.9, 0.9)])
    item.progress = 0.0
    assert not board.build(Transform(100, 100))
    item.progress = 1.0
    assert board.build(Transform(100, 100))


def test_unknown_shape_raises() -> None:
    board = Board()
    with pytest.raises(ValueError):
        board.add_shape("nope")
