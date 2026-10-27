"""Checkpoint timing, one-shot delivery, seeking, and answer matching."""

from __future__ import annotations

import config
from medha.core.schema import LessonScript
from medha.lesson.store import load_lesson
from medha.render.playback import LessonPlayback, prepare_playback
from medha.render.timeline import build_timeline
from medha.studio.app import _answer_matches


def _lesson() -> LessonScript:
    return load_lesson(config.LESSON_CONTENT_DIR / "newton.json")


def test_timeline_contains_final_checkpoint() -> None:
    lesson = _lesson()
    timeline = build_timeline(lesson)

    assert len(timeline.checkpoints) == 1
    checkpoint = timeline.checkpoints[0]
    last = lesson.steps[-1]
    assert last.checkpoint is not None
    assert checkpoint.step_id == last.id
    assert checkpoint.question == last.checkpoint.question
    assert 0 < checkpoint.at_ms <= timeline.total_ms


def test_playback_delivers_checkpoint_once_and_resets_on_seek() -> None:
    lesson = _lesson()
    playback = LessonPlayback(prepare_playback(lesson, use_tts=False), play_audio=False)
    checkpoint = playback.timeline.checkpoints[0]

    assert playback.take_checkpoint(checkpoint.at_ms - 1) is None
    assert playback.take_checkpoint(checkpoint.at_ms) is checkpoint
    assert playback.take_checkpoint(checkpoint.at_ms + 5000) is None

    playback.seek(checkpoint.at_ms - 1)
    assert playback.take_checkpoint(checkpoint.at_ms) is checkpoint

    playback.seek(checkpoint.at_ms + 5000)
    assert playback.take_checkpoint(checkpoint.at_ms + 6000) is None


def test_answer_matching_accepts_core_clause_and_equations() -> None:
    expected = "It halves, because a = F / m."
    assert _answer_matches("It halves", expected)
    assert _answer_matches("it halves!", expected)
    assert not _answer_matches("It doubles", expected)
    assert _answer_matches("F = ma", "F = ma")
    assert _answer_matches("4 N", "4 N")
    assert not _answer_matches("", expected)
