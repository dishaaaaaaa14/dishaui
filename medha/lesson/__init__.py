"""Offline grounded lesson generation with validated board actions."""

from .cache import LessonCache, cache_key
from .client import ChatClient, ChatMessage, OllamaClient
from .errors import GenerationError, OllamaError
from .generator import (
    LessonGenerator,
    estimate_duration_s,
    extract_json_object,
    make_lesson_id,
    parse_lesson_json,
    repair_with_drops,
    sanitize_latex,
    sanitize_payload,
    sanitize_text,
)
from .models import Difficulty, GenerationRequest, GenerationResult, SourceExcerpt
from .schema import llm_lesson_schema
from .store import list_lessons, load_lesson, save_lesson

__all__ = [
    "ChatClient",
    "ChatMessage",
    "Difficulty",
    "GenerationError",
    "GenerationRequest",
    "GenerationResult",
    "LessonCache",
    "LessonGenerator",
    "OllamaClient",
    "OllamaError",
    "SourceExcerpt",
    "cache_key",
    "estimate_duration_s",
    "extract_json_object",
    "list_lessons",
    "llm_lesson_schema",
    "load_lesson",
    "make_lesson_id",
    "parse_lesson_json",
    "repair_with_drops",
    "sanitize_latex",
    "sanitize_payload",
    "sanitize_text",
    "save_lesson",
]
