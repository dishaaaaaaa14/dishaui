"""Persistent library indexing, filtering, settings, and checkpoint history."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import config
from medha.core.schema import LessonScript
from medha.lesson.store import load_lesson
from medha.library import __main__ as library_cli
from medha.library.db import LibraryDatabase
from medha.library.models import LibraryFilter
from medha.library.repository import LessonLibrary


def _fixture(tmp_path: Path) -> tuple[Path, LessonScript]:
    source = config.LESSON_CONTENT_DIR / "newton.json"
    target = tmp_path / "newton.json"
    shutil.copyfile(source, target)
    return target, load_lesson(target)


def test_index_filter_favorite_and_stats(tmp_path: Path) -> None:
    path, lesson = _fixture(tmp_path)
    library = LessonLibrary(LibraryDatabase(tmp_path / "library.db"))

    indexed = library.upsert_lesson(lesson, path, score=88, duration_ms=12345)
    assert indexed.lesson_id == lesson.lesson_id
    assert indexed.path == str(path.resolve())
    assert indexed.steps == len(lesson.steps)
    assert indexed.actions == sum(len(step.board) for step in lesson.steps)
    assert indexed.duration_ms == 12345
    assert indexed.score == 88
    assert indexed.language == "en"
    assert not indexed.favorite

    assert library.get(lesson.lesson_id) == indexed
    assert library.find_by_path(path) == indexed
    assert library.set_favorite(lesson.lesson_id, True)
    assert [row.lesson_id for row in library.list_lessons()] == [lesson.lesson_id]
    assert [row.lesson_id for row in library.list_lessons(LibraryFilter(favorite=True))] == [
        lesson.lesson_id
    ]
    assert library.list_lessons(LibraryFilter(query="nothing-here")) == []
    assert library.list_lessons(LibraryFilter(subject="physics"))

    refreshed = library.upsert_lesson(lesson, path)
    assert refreshed.favorite
    assert refreshed.score == 88
    stats = library.statistics()
    assert stats.lessons == 1
    assert stats.favorites == 1
    assert stats.average_score == 88


def test_index_directory_reports_invalid_files(tmp_path: Path) -> None:
    path, _lesson = _fixture(tmp_path)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    library = LessonLibrary(LibraryDatabase(tmp_path / "library.db"))

    report = library.index_directory(tmp_path)

    assert report.indexed == 1
    assert report.skipped == 1
    assert any("broken.json" in error for error in report.errors)
    assert library.find_by_path(path) is not None


def test_checkpoint_attempts_and_delete(tmp_path: Path) -> None:
    path, lesson = _fixture(tmp_path)
    library = LessonLibrary(LibraryDatabase(tmp_path / "library.db"))
    library.upsert_lesson(lesson, path)

    first = library.record_checkpoint(
        lesson.lesson_id,
        "step-1",
        "What is the second law?",
        "F = ma",
        correct=True,
    )
    second = library.record_checkpoint(
        lesson.lesson_id,
        "step-1",
        "What is the second law?",
        "F = mv",
        correct=False,
    )
    assert first.id < second.id
    assert library.checkpoint_attempts(lesson.lesson_id) == [first, second]
    summary = library.checkpoint_summary(lesson.lesson_id)
    assert summary.attempts == 2
    assert summary.correct == 1
    assert summary.incorrect == 1
    assert summary.accuracy == 0.5
    assert library.statistics().checkpoint_attempts == 2

    assert library.delete_lesson(lesson.lesson_id, delete_file=True)
    assert not path.exists()
    assert library.get(lesson.lesson_id) is None
    assert library.checkpoint_summary(lesson.lesson_id).attempts == 0


def test_settings_round_trip(tmp_path: Path) -> None:
    library = LessonLibrary(LibraryDatabase(tmp_path / "library.db"))
    library.set_setting("tts", False)
    library.set_settings({"speed": 0.9, "tags": ["demo", "physics"]})

    assert library.get_setting("tts") is False
    assert library.get_settings() == {"tts": False, "speed": 0.9, "tags": ["demo", "physics"]}
    assert library.get_setting("missing", "fallback") == "fallback"


def test_library_cli_index_and_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lesson_dir = tmp_path / "lessons"
    lesson_dir.mkdir()
    shutil.copyfile(config.LESSON_CONTENT_DIR / "newton.json", lesson_dir / "newton.json")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cli.db")

    assert library_cli.main(["index", "--dir", str(lesson_dir)]) == 0
    capsys.readouterr()
    assert library_cli.main(["stats", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lessons"] == 1
