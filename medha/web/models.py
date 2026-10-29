"""Pydantic contracts for the web API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WebModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(WebModel):
    topic: str = Field(min_length=1, max_length=200)
    subject: str = "general"
    difficulty: str = "beginner"
    audience: str = "high-school students"
    steps: int = Field(default=5, ge=1, le=8)
    language: str = "en"
    tts: bool = False
    use_rag: bool = False
    use_rerank: bool = False
    use_cache: bool = True


class OpenRequest(WebModel):
    path: str | None = None
    lesson_id: str | None = None
    language: str = "en"
    tts: bool = False


class JobStatus(WebModel):
    session_id: str
    state: str = "queued"
    progress: list[str] = Field(default_factory=list)
    error: str | None = None
    title: str | None = None
    subject: str | None = None
    language: str | None = None
    steps: int = 0
    actions: int = 0
    duration_ms: int = 0
    score: int = 0
    warnings: list[str] = Field(default_factory=list)
    tts_error: str | None = None
    lesson_id: str | None = None
    path: str | None = None


class StrokeOut(WebModel):
    points: list[list[float]]
    color: str
    width: float
    alpha: float
    progress: float


class FrameOut(WebModel):
    t: int
    strokes: list[StrokeOut]


class CheckpointOut(WebModel):
    step_id: str
    at_ms: int
    question: str
    expected: str
    hints: list[str]


class LessonSummary(WebModel):
    lesson_id: str
    path: str
    title: str
    subject: str
    difficulty: str
    language: str
    steps: int
    actions: int
    duration_ms: int
    score: int
    favorite: bool
    created_at: str
    updated_at: str


class LibraryListOut(WebModel):
    lessons: list[LessonSummary]
