"""Validated JSON cache for generated lessons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import config
from medha.core.schema import LessonScript


def cache_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class LessonCache:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory or config.LESSON_CACHE_DIR)

    def path_for(self, key: str) -> Path:
        if len(key) != 64 or any(char not in "0123456789abcdef" for char in key):
            raise ValueError("invalid lesson cache key")
        return self.directory / f"{key}.json"

    def load(self, key: str) -> LessonScript | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return LessonScript.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError):
            return None

    def save(self, key: str, lesson: LessonScript) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(lesson.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    def clear(self) -> int:
        if not self.directory.exists():
            return 0
        removed = 0
        for path in self.directory.glob("*.json"):
            path.unlink()
            removed += 1
        return removed
