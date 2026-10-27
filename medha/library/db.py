"""SQLite storage for the lesson library."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import config

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS medha_schema (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    steps INTEGER NOT NULL DEFAULT 0,
    actions INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    favorite INTEGER NOT NULL DEFAULT 0,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lessons_updated ON lessons(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lessons_subject ON lessons(subject);
CREATE INDEX IF NOT EXISTS idx_lessons_language ON lessons(language);
CREATE INDEX IF NOT EXISTS idx_lessons_favorite ON lessons(favorite DESC);

CREATE TABLE IF NOT EXISTS checkpoint_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL REFERENCES lessons(lesson_id) ON DELETE CASCADE,
    step_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    correct INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_lesson ON checkpoint_attempts(lesson_id);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT,
    chunks INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class LibraryError(RuntimeError):
    pass


class LibraryDatabase:
    """Small SQLite wrapper; every operation uses its own connection."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else config.DB_PATH

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        try:
            with self.connect() as connection:
                connection.executescript(_SCHEMA)
                connection.execute(
                    "INSERT INTO medha_schema(key, value) VALUES('version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(SCHEMA_VERSION),),
                )
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot initialize library database: {exc}") from exc

    def schema_version(self) -> int:
        try:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT value FROM medha_schema WHERE key = 'version'"
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryError(f"cannot read library schema: {exc}") from exc
        if row is None:
            return 0
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return 0
