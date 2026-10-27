from __future__ import annotations

from pathlib import Path

from medha.lesson import list_lessons, load_lesson, save_lesson
from medha.studio.service import StudioOptions, open_lesson

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "spec" / "board-action" / "v1" / "examples" / "newton.json"


def test_options_request_uses_material() -> None:
    options = StudioOptions(
        topic="Force",
        subject="physics",
        difficulty="beginner",
        steps=3,
        materials=(ROOT / "sample.pdf",),
        use_rag=False,
    )
    request = options.request()
    assert request.use_rag
    assert request.steps == 3
    assert request.subject == "physics"


def test_lesson_files_round_trip(tmp_path: Path) -> None:
    lesson = load_lesson(EXAMPLE)
    path = save_lesson(lesson, tmp_path / "lesson.json")
    assert path.is_file()
    assert load_lesson(path) == lesson
    assert list_lessons(tmp_path) == [path]


def test_open_lesson_prepares_playback_without_tts() -> None:
    result = open_lesson(EXAMPLE, StudioOptions(topic="Newton", tts=False))
    assert result.lesson.lesson_id == "newton2-demo"
    assert result.path == EXAMPLE
    assert result.playback.duration_ms > 0
    assert result.playback.prepared.track is None
    assert result.report.ok
    assert result.tts_error is None
    assert not result.playback.playing
