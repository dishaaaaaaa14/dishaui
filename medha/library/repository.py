"""Lesson library queries and indexing."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from medha.core.schema import LessonScript
from medha.lesson.store import list_lessons, load_lesson
from medha.render.timeline import build_timeline

from .db import LibraryDatabase, LibraryError
from .models import (
    CheckpointAttempt,
    CheckpointSummary,
    IndexReport,
    LibraryFilter,
    LibraryLesson,
    LibraryStats,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _decode_tags(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _row_to_lesson(row: sqlite3.Row) -> LibraryLesson:
    return LibraryLesson(
        lesson_id=str(row["lesson_id"]),
        path=str(row["path"]),
        title=str(row["title"]),
        subject=str(row["subject"]),
        difficulty=str(row["difficulty"]),
        language=str(row["language"]),
        steps=int(row["steps"]),
        actions=int(row["actions"]),
        duration_ms=int(row["duration_ms"]),
        score=int(row["score"]),
        favorite=bool(row["favorite"]),
        tags=_decode_tags(row["tags"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class LessonLibrary:
    def __init__(self, database: LibraryDatabase | None = None) -> None:
        self.database = database or LibraryDatabase()
        self.database.initialize()

    def upsert_lesson(
        self,
        lesson: LessonScript,
        path: Path,
        *,
        score: int | None = None,
        duration_ms: int | None = None,
        tags: list[str] | None = None,
    ) -> LibraryLesson:
        target = str(Path(path).resolve())
        now = _now()
        steps = len(lesson.steps)
        actions = sum(len(step.board) for step in lesson.steps)
        duration = (
            max(0, int(duration_ms))
            if duration_ms is not None
            else build_timeline(lesson).total_ms
        )
        language = str(getattr(lesson, "language", None) or "en")
        try:
            with self.database.connect() as connection:
                existing = connection.execute(
                    "SELECT favorite, created_at, score FROM lessons WHERE lesson_id = ?",
                    (lesson.lesson_id,),
                ).fetchone()
                favorite = bool(existing["favorite"]) if existing is not None else False
                created_at = str(existing["created_at"]) if existing is not None else now
                score_value = (
                    int(score)
                    if score is not None
                    else int(existing["score"]) if existing is not None else 0
                )
                connection.execute(
                    "DELETE FROM lessons WHERE path = ? AND lesson_id <> ?",
                    (target, lesson.lesson_id),
                )
                connection.execute(
                    """
                    INSERT INTO lessons(
                        lesson_id, path, title, subject, difficulty, language,
                        steps, actions, duration_ms, score, favorite, tags,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(lesson_id) DO UPDATE SET
                        path = excluded.path,
                        title = excluded.title,
                        subject = excluded.subject,
                        difficulty = excluded.difficulty,
                        language = excluded.language,
                        steps = excluded.steps,
                        actions = excluded.actions,
                        duration_ms = excluded.duration_ms,
                        score = excluded.score,
                        favorite = excluded.favorite,
                        tags = excluded.tags,
                        updated_at = excluded.updated_at
                    """,
                    (
                        lesson.lesson_id,
                        target,
                        lesson.title,
                        lesson.subject,
                        lesson.difficulty,
                        language,
                        steps,
                        actions,
                        duration,
                        max(0, min(100, score_value)),
                        int(favorite),
                        json.dumps(sorted(set(tags or [])), ensure_ascii=False),
                        created_at,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM lessons WHERE lesson_id = ?", (lesson.lesson_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot save lesson index: {exc}") from exc
        if row is None:
            raise LibraryError("lesson index row disappeared after write")
        return _row_to_lesson(row)

    def index_file(self, path: Path) -> LibraryLesson:
        lesson = load_lesson(path)
        return self.upsert_lesson(lesson, path)

    def index_directory(self, directory: Path | None = None) -> IndexReport:
        report = IndexReport()
        for path in list_lessons(directory):
            try:
                self.index_file(path)
            except Exception as exc:
                report.skipped += 1
                report.errors.append(f"{path.name}: {exc}")
            else:
                report.indexed += 1
        return report

    def get(self, lesson_id: str) -> LibraryLesson | None:
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read lesson index: {exc}") from exc
        return _row_to_lesson(row) if row is not None else None

    def find_by_path(self, path: Path) -> LibraryLesson | None:
        target = str(Path(path).resolve())
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM lessons WHERE path = ?", (target,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read lesson index: {exc}") from exc
        return _row_to_lesson(row) if row is not None else None

    def list_lessons(self, filters: LibraryFilter | None = None) -> list[LibraryLesson]:
        query = filters or LibraryFilter()
        clauses: list[str] = []
        parameters: list[object] = []
        if query.query:
            clauses.append("(title LIKE ? OR lesson_id LIKE ? OR path LIKE ?)")
            pattern = f"%{query.query}%"
            parameters.extend([pattern, pattern, pattern])
        if query.subject:
            clauses.append("subject = ?")
            parameters.append(query.subject)
        if query.language:
            clauses.append("language = ?")
            parameters.append(query.language)
        if query.favorite is not None:
            clauses.append("favorite = ?")
            parameters.append(int(query.favorite))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.extend([query.limit, query.offset])
        statement = (
            "SELECT * FROM lessons"
            + where
            + " ORDER BY favorite DESC, updated_at DESC, title ASC LIMIT ? OFFSET ?"
        )
        try:
            with self.database.connect() as connection:
                rows = connection.execute(statement, parameters).fetchall()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot list lessons: {exc}") from exc
        return [_row_to_lesson(row) for row in rows]

    def set_favorite(self, lesson_id: str, favorite: bool) -> bool:
        try:
            with self.database.connect() as connection:
                result = connection.execute(
                    "UPDATE lessons SET favorite = ?, updated_at = ? WHERE lesson_id = ?",
                    (int(favorite), _now(), lesson_id),
                )
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot update favorite: {exc}") from exc
        return result.rowcount > 0

    def delete_lesson(self, lesson_id: str, *, delete_file: bool = False) -> bool:
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT path FROM lessons WHERE lesson_id = ?", (lesson_id,)
                ).fetchone()
                if row is None:
                    return False
                connection.execute("DELETE FROM lessons WHERE lesson_id = ?", (lesson_id,))
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot delete lesson: {exc}") from exc
        if delete_file:
            Path(str(row["path"])).unlink(missing_ok=True)
        return True

    def record_checkpoint(
        self,
        lesson_id: str,
        step_id: str,
        question: str,
        answer: str,
        *,
        correct: bool,
    ) -> CheckpointAttempt:
        now = _now()
        try:
            with self.database.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO checkpoint_attempts(
                        lesson_id, step_id, question, answer, correct, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (lesson_id, step_id, question, answer, int(correct), now),
                )
                attempt_id = int(cursor.lastrowid or 0)
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot record checkpoint attempt: {exc}") from exc
        return CheckpointAttempt(
            id=attempt_id,
            lesson_id=lesson_id,
            step_id=step_id,
            question=question,
            answer=answer,
            correct=correct,
            created_at=now,
        )

    def checkpoint_attempts(self, lesson_id: str) -> list[CheckpointAttempt]:
        try:
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM checkpoint_attempts WHERE lesson_id = ? "
                    "ORDER BY id ASC",
                    (lesson_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read checkpoint attempts: {exc}") from exc
        return [
            CheckpointAttempt(
                id=int(row["id"]),
                lesson_id=str(row["lesson_id"]),
                step_id=str(row["step_id"]),
                question=str(row["question"]),
                answer=str(row["answer"]),
                correct=bool(row["correct"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def checkpoint_summary(self, lesson_id: str) -> CheckpointSummary:
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT COUNT(*) AS attempts, COALESCE(SUM(correct), 0) AS correct "
                    "FROM checkpoint_attempts WHERE lesson_id = ?",
                    (lesson_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot summarize checkpoints: {exc}") from exc
        attempts = int(row["attempts"]) if row is not None else 0
        correct = int(row["correct"]) if row is not None else 0
        return CheckpointSummary(
            lesson_id=lesson_id,
            attempts=attempts,
            correct=correct,
            incorrect=attempts - correct,
        )

    def statistics(self) -> LibraryStats:
        try:
            with self.database.connect() as connection:
                lesson_row = connection.execute(
                    "SELECT COUNT(*) AS total, COALESCE(SUM(favorite), 0) AS favorites, "
                    "COALESCE(SUM(duration_ms), 0) AS duration "
                    "FROM lessons"
                ).fetchone()
                score_row = connection.execute(
                    "SELECT COALESCE(AVG(score), 0) AS average FROM lessons"
                ).fetchone()
                attempt_row = connection.execute(
                    "SELECT COUNT(*) AS attempts FROM checkpoint_attempts"
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read library statistics: {exc}") from exc
        return LibraryStats(
            lessons=int(lesson_row["total"]) if lesson_row is not None else 0,
            favorites=int(lesson_row["favorites"]) if lesson_row is not None else 0,
            total_duration_ms=(
                int(lesson_row["duration"]) if lesson_row is not None else 0
            ),
            average_score=float(score_row["average"]) if score_row is not None else 0.0,
            checkpoint_attempts=(
                int(attempt_row["attempts"]) if attempt_row is not None else 0
            ),
        )

    def set_setting(self, key: str, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        try:
            with self.database.connect() as connection:
                connection.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, payload),
                )
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot save setting {key!r}: {exc}") from exc

    def set_settings(self, values: dict[str, object]) -> None:
        if not values:
            return
        try:
            with self.database.connect() as connection:
                for key, value in values.items():
                    connection.execute(
                        "INSERT INTO settings(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, json.dumps(value, ensure_ascii=False)),
                    )
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot save settings: {exc}") from exc

    def get_setting(self, key: str, default: object = None) -> object | None:
        try:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read setting {key!r}: {exc}") from exc
        if row is None:
            return default
        try:
            return json.loads(str(row["value"]))
        except json.JSONDecodeError:
            return default

    def get_settings(self) -> dict[str, object]:
        try:
            with self.database.connect() as connection:
                rows = connection.execute("SELECT key, value FROM settings").fetchall()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read settings: {exc}") from exc
        values: dict[str, object] = {}
        for row in rows:
            try:
                values[str(row["key"])] = json.loads(str(row["value"]))
            except json.JSONDecodeError:
                continue
        return values

    def record_material(self, path: Path, *, sha256: str, chunks: int) -> None:
        try:
            with self.database.connect() as connection:
                connection.execute(
                    "INSERT INTO materials(path, sha256, chunks, indexed_at) "
                    "VALUES(?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET "
                    "sha256 = excluded.sha256, chunks = excluded.chunks, "
                    "indexed_at = excluded.indexed_at",
                    (str(Path(path).resolve()), sha256, max(0, int(chunks)), _now()),
                )
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot record material: {exc}") from exc
