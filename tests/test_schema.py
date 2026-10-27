from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from medha.core.schema import (
    LessonScript,
    WriteMathAction,
    export_schema,
    repair_lesson,
    split_sentences,
    validate_action,
    validate_lesson,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def load_example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_lesson_is_valid() -> None:
    lesson = validate_lesson(load_example())
    assert isinstance(lesson, LessonScript)
    assert len(lesson.steps) == 3
    actions = [action for step in lesson.steps for action in step.board]
    assert len(actions) == 12
    assert {action.op for action in actions} >= {"write_text", "write_math", "draw", "point"}


def test_duplicate_action_ids_rejected() -> None:
    payload = load_example()
    payload["steps"][0]["board"].append(copy.deepcopy(payload["steps"][0]["board"][0]))
    with pytest.raises(ValidationError, match="duplicate action id"):
        validate_lesson(payload)


def test_anchor_outside_narration_rejected() -> None:
    payload = load_example()
    payload["steps"][0]["board"][0]["start"] = {"sentence": 99, "char": 0}
    with pytest.raises(ValidationError, match="out of range"):
        validate_lesson(payload)


def test_dangling_target_rejected() -> None:
    payload = load_example()
    highlight = next(a for a in payload["steps"][1]["board"] if a["op"] == "highlight")
    highlight["target"] = "missing"
    with pytest.raises(ValidationError, match="unknown target"):
        validate_lesson(payload)


def test_rect_must_fit_board() -> None:
    with pytest.raises(ValidationError, match="fit inside"):
        validate_action(
            {
                "op": "write_math",
                "id": "a1",
                "latex": "x",
                "rect": {"x": 0.8, "y": 0.1, "w": 0.5, "h": 0.1},
            }
        )


def test_draw_geometry_is_checked() -> None:
    with pytest.raises(ValidationError, match="two points"):
        validate_action({"op": "draw", "id": "a1", "shape": "arrow", "points": []})
    with pytest.raises(ValidationError, match="needs a rect"):
        validate_action({"op": "draw", "id": "a2", "shape": "axes"})


def test_repair_legacy_actions() -> None:
    payload = {
        "lesson_id": "legacy",
        "title": "Legacy lesson",
        "steps": [
            {
                "id": "s1",
                "concept": "demo",
                "narration": "Hello there. This is a line.",
                "board": [
                    {
                        "type": "write_text",
                        "step_id": 1,
                        "content": "Hi",
                        "position": {"x": 0.1, "y": 0.1},
                        "duration": 1.2,
                    },
                    {
                        "type": "draw_line",
                        "step_id": 1,
                        "start": {"x": 0.1, "y": 0.2},
                        "end": {"x": 0.2, "y": 0.3},
                        "duration": 0.5,
                    },
                ],
            }
        ],
    }
    lesson, issues = repair_lesson(payload)
    first, second = lesson.steps[0].board
    assert first.op == "write_text"
    assert first.text == "Hi"  # type: ignore[union-attr]
    assert first.duration_ms == 1200
    assert first.rect is not None
    assert second.op == "draw"
    assert second.shape == "line"  # type: ignore[union-attr]
    assert second.duration_ms == 500
    assert not issues


def test_repair_clamps_coordinates() -> None:
    payload = load_example()
    payload["steps"][0]["board"][1]["rect"] = {"x": 0.9, "y": 0.9, "w": 0.8, "h": 0.8}
    lesson, _ = repair_lesson(payload)
    action = lesson.steps[0].board[1]
    assert isinstance(action, WriteMathAction)
    rect = action.rect
    assert rect is not None
    assert rect.x + rect.w <= 1.001
    assert rect.y + rect.h <= 1.001


def test_sentence_splitter() -> None:
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_export_schema(tmp_path: Path) -> None:
    action_path, lesson_path = export_schema(tmp_path)
    action_schema = json.loads(action_path.read_text(encoding="utf-8"))
    lesson_schema = json.loads(lesson_path.read_text(encoding="utf-8"))
    assert "schema" in action_schema
    assert "schema" in lesson_schema
    assert lesson_schema["version"] == "1.0.0"
    assert action_schema["schema"]["discriminator"]["propertyName"] == "op"
