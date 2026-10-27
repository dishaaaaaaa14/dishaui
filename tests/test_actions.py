from __future__ import annotations

import json
from pathlib import Path

from medha.core.schema import LessonScript, validate_lesson
from medha.render.actions import build_visuals, mathtext_segments, render_frame
from medha.render.scene import Board
from medha.render.timeline import build_timeline

ROOT = Path(__file__).resolve().parents[1]
LESSON = ROOT / "content" / "lessons" / "newton.json"


def load_lesson() -> LessonScript:
    return validate_lesson(json.loads(LESSON.read_text(encoding="utf-8")))


def visible_count(board: Board) -> int:
    return sum(1 for item in board.items if item.progress > 0.0)


def test_content_lesson_builds_every_action() -> None:
    lesson = load_lesson()
    visuals = build_visuals(lesson)
    action_ids = {action.id for step in lesson.steps for action in step.board}
    assert set(visuals) == action_ids
    assert len(visuals) == 20
    assert visuals["a1"].op == "write_text"
    assert visuals["a9"].op == "clear"
    assert visuals["a14"].op == "highlight"


def test_render_starts_empty_then_shows_title() -> None:
    lesson = load_lesson()
    visuals = build_visuals(lesson)
    timeline = build_timeline(lesson)
    board = Board()
    render_frame(board, visuals, timeline, 0)
    assert visible_count(board) == 0
    render_frame(board, visuals, timeline, 1200)
    assert visible_count(board) > 0


def test_clear_hides_earlier_actions() -> None:
    payload = {
        "schema_version": "1.0.0",
        "lesson_id": "clear-demo",
        "title": "Clear demo",
        "subject": "general",
        "steps": [
            {
                "id": "s1",
                "concept": "clearing",
                "narration": "Write this. Then clear it.",
                "board": [
                    {
                        "op": "write_text",
                        "id": "a1",
                        "text": "Old",
                        "region": "title",
                        "duration_ms": 200,
                        "start": {"sentence": 0, "char": 0},
                    },
                    {
                        "op": "clear",
                        "id": "a2",
                        "duration_ms": 100,
                        "start": {"sentence": 1, "char": 0},
                    },
                ],
            }
        ],
    }
    lesson = validate_lesson(payload)
    visuals = build_visuals(lesson)
    timeline = build_timeline(lesson)
    board = Board()
    clear_at = timeline.actions["a2"].start_ms

    render_frame(board, visuals, timeline, clear_at - 1)
    assert visible_count(board) > 0
    render_frame(board, visuals, timeline, clear_at + 1)
    assert visible_count(board) == 0


def test_mathtext_flattens_a_fraction_to_segments() -> None:
    segments = mathtext_segments(r"a = \frac{F}{m}")
    assert len(segments) > 5
    assert all(len(segment) >= 2 for segment in segments)


def test_final_frame_contains_later_step() -> None:
    lesson = load_lesson()
    visuals = build_visuals(lesson)
    timeline = build_timeline(lesson)
    board = Board()
    render_frame(board, visuals, timeline, timeline.total_ms)
    assert visible_count(board) > 5
    assert any(item.color == "diagram" for item in board.items)
