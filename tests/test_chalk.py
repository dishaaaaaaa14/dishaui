from __future__ import annotations

from medha.render.chalk import make_chalk


def test_chalk_is_deterministic() -> None:
    points = [(0.0, 0.0), (100.0, 0.0)]
    first = make_chalk(points, width=4.0, seed=7)
    second = make_chalk(points, width=4.0, seed=7)
    assert first == second


def test_chalk_has_main_and_ghost_passes() -> None:
    strokes = make_chalk([(0.0, 0.0), (100.0, 0.0)], width=4.0, seed=1)
    assert len(strokes) == 2
    assert strokes[0].alpha > strokes[1].alpha
    assert len(strokes[0].points) > 2


def test_chalk_can_disable_ghost() -> None:
    strokes = make_chalk([(0.0, 0.0), (100.0, 0.0)], width=4.0, passes=1)
    assert len(strokes) == 1


def test_degenerate_chalk_is_empty() -> None:
    assert make_chalk([], width=3.0) == []
    assert make_chalk([(0.0, 0.0)], width=3.0) == []
    assert make_chalk([(0.0, 0.0), (100.0, 0.0)], width=0.0) == []
