from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medha.core.schema import LessonScript
from medha.eval import evaluate_corpus, evaluate_file, evaluate_lesson


def make_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "lesson_id": "eval-demo",
        "title": "Force and acceleration",
        "subject": "physics",
        "difficulty": "beginner",
        "steps": [
            {
                "id": "s1",
                "concept": "force and acceleration",
                "narration": "Force equals mass times acceleration. This is Newton's second law.",
                "board": [
                    {
                        "op": "write_text",
                        "id": "a1",
                        "text": "Newton's Second Law",
                        "region": "title",
                        "duration_ms": 800,
                        "start": {"sentence": 0, "char": 0},
                    },
                    {
                        "op": "write_math",
                        "id": "a2",
                        "latex": "F = m a",
                        "rect": {"x": 0.08, "y": 0.3, "w": 0.3, "h": 0.12},
                        "duration_ms": 900,
                        "start": {"sentence": 1, "char": 0},
                    },
                ],
            }
        ],
        "meta": {"prompt_version": "test"},
    }


def test_clean_lesson_scores_100() -> None:
    report = evaluate_lesson(LessonScript.model_validate(make_payload()))
    assert report.ok
    assert report.errors == 0
    assert report.warnings == 0
    assert report.score == 100
    assert report.steps == 1
    assert report.actions == 2
    assert report.timeline_ms > 0


def test_empty_board_and_invalid_latex_warn() -> None:
    payload = make_payload()
    payload["steps"][0]["board"] = [
        {
            "op": "write_math",
            "id": "a1",
            "latex": "\\frac{",
            "rect": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.2},
        }
    ]
    report = evaluate_lesson(LessonScript.model_validate(payload))
    assert report.ok
    assert any(issue.code == "math.fallback" for issue in report.issues)
    assert report.score < 100


def test_empty_step_is_a_warning() -> None:
    payload = make_payload()
    payload["steps"][0]["board"] = []
    report = evaluate_lesson(LessonScript.model_validate(payload))
    assert not report.ok
    codes = {issue.code for issue in report.issues}
    assert "step.empty_board" in codes
    assert "board.no_actions" in codes


def test_replacement_character_is_an_error() -> None:
    payload = make_payload()
    payload["steps"][0]["narration"] = "Force equals mass \ufffd acceleration. It is a law."
    report = evaluate_lesson(LessonScript.model_validate(payload))
    assert not report.ok
    assert any(issue.code == "text.replacement" for issue in report.issues)


def test_file_and_corpus_reports(tmp_path: Path) -> None:
    valid = tmp_path / "valid.json"
    invalid = tmp_path / "invalid.json"
    valid.write_text(json.dumps(make_payload()), encoding="utf-8")
    invalid.write_text('{"schema_version": "1.0.0"}', encoding="utf-8")

    report = evaluate_file(valid)
    assert report.ok
    bad = evaluate_file(invalid)
    assert not bad.ok
    assert bad.issues[0].code == "schema.invalid"

    reports = evaluate_corpus(tmp_path)
    assert len(reports) == 2
    assert sum(1 for item in reports if item.ok) == 1


def test_missing_file_is_reported(tmp_path: Path) -> None:
    report = evaluate_file(tmp_path / "missing.json")
    assert not report.ok
    assert report.errors == 1
    assert "cannot read" in report.issues[0].message
