"""Contracts for library records, filters, and checkpoint history."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LibraryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LibraryLesson(LibraryModel):
    lesson_id: str
    path: str
    title: str
    subject: str = "general"
    difficulty: str = "beginner"
    language: str = "en"
    steps: int = 0
    actions: int = 0
    duration_ms: int = 0
    score: int = 0
    favorite: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class LibraryFilter(LibraryModel):
    query: str | None = None
    subject: str | None = None
    language: str | None = None
    favorite: bool | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class CheckpointAttempt(LibraryModel):
    id: int
    lesson_id: str
    step_id: str
    question: str
    answer: str
    correct: bool
    created_at: str


class CheckpointSummary(LibraryModel):
    lesson_id: str
    attempts: int = 0
    correct: int = 0
    incorrect: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.attempts if self.attempts else 0.0


class LibraryStats(LibraryModel):
    lessons: int = 0
    favorites: int = 0
    total_duration_ms: int = 0
    average_score: float = 0.0
    checkpoint_attempts: int = 0


class IndexReport(LibraryModel):
    indexed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
