"""Lesson generation errors."""

from __future__ import annotations


class GenerationError(RuntimeError):
    """A lesson could not be generated or validated."""


class OllamaError(GenerationError):
    """The local Ollama service failed."""
