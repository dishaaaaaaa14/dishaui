from __future__ import annotations

import json
from pathlib import Path

from medha.core.schema import LessonScript, validate_lesson
from medha.render.timeline import build_timeline, estimate_sentence_ms

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def load_lesson() -> LessonScript:
    return validate_lesson(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_timeline_follows_action_order() -> None:
    lesson = load_lesson()
    timeline = build_timeline(lesson)
    ordered = [action.id for step in lesson.steps for action in step.board]
    starts = [timeline.actions[action_id].start_ms for action_id in ordered]
    assert starts == sorted(starts)
    assert timeline.total_ms > 0
    assert timeline.actions["a1"].start_ms == 0


def test_timeline_uses_supplied_sentence_durations() -> None:
    lesson = load_lesson()
    timeline = build_timeline(lesson, sentence_ms=[[1000] * 2] * len(lesson.steps), step_gap_ms=0)
    assert timeline.actions["a1"].start_ms == 0
    assert timeline.actions["a1"].end_ms == 900
    assert timeline.actions["a3"].start_ms == 1000
    assert timeline.step_start_ms[1] >= 1000


def test_timeline_falls_back_for_short_sentence_lists() -> None:
    lesson = load_lesson()
    timeline = build_timeline(lesson, sentence_ms=[[700]])
    assert timeline.actions["a1"].start_ms == 0
    assert timeline.total_ms > 700


def test_estimate_has_a_minimum_duration() -> None:
    assert estimate_sentence_ms("Hi.") >= 600
