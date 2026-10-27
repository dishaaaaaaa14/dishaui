"""Validated lesson files shared by the CLI, player, and Studio."""

from __future__ import annotations

import json
from pathlib import Path

import config
from medha.core.schema import LessonScript, validate_lesson


def save_lesson(
    lesson: LessonScript,
    path: Path | None = None,
    *,
    directory: Path | None = None,
) -> Path:
    target = (
        Path(path)
        if path is not None
        else Path(directory or config.LESSON_CONTENT_DIR) / f"{lesson.lesson_id}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(lesson.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def load_lesson(path: Path) -> LessonScript:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_lesson(payload)


def list_lessons(directory: Path | None = None) -> list[Path]:
    root = Path(directory or config.LESSON_CONTENT_DIR)
    if not root.exists():
        return []
    return sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
