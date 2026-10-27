from __future__ import annotations

from medha.render.chalk import ChalkStroke
from medha.render.geometry import Transform
from medha.render.mesh import build_mesh, tessellate_stroke


def test_tessellate_stroke_emits_triangles() -> None:
    stroke = ChalkStroke(points=((10.0, 10.0), (50.0, 10.0)), width=4.0, color="chalk")
    vertices = tessellate_stroke(stroke, Transform(100, 100))
    assert len(vertices) % 6 == 0
    assert len(vertices) > 0
    alphas = vertices[5::6]
    assert all(0.0 <= alpha <= 1.0 for alpha in alphas)


def test_build_mesh_aggregates() -> None:
    strokes = [
        ChalkStroke(((10.0, 10.0), (20.0, 20.0)), 3.0, "math"),
        ChalkStroke(((30.0, 30.0), (40.0, 30.0)), 3.0, "diagram"),
    ]
    mesh = build_mesh(strokes, Transform(100, 100))
    assert mesh
    assert mesh.vertex_count > 0
    assert mesh.vertex_count % 3 == 0


def test_mesh_coordinates_are_ndc() -> None:
    stroke = ChalkStroke(((50.0, 50.0), (60.0, 50.0)), 2.0, "chalk")
    mesh = build_mesh([stroke], Transform(100, 100))
    xs = mesh.vertices[0::6]
    ys = mesh.vertices[1::6]
    assert all(-1.1 <= x <= 1.1 for x in xs)
    assert all(-1.1 <= y <= 1.1 for y in ys)


def test_short_stroke_is_skipped() -> None:
    assert tessellate_stroke(ChalkStroke(((1.0, 1.0),), 2.0, "chalk"), Transform(10, 10)) == []
