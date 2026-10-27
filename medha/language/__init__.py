"""Optional Kannada/Hindi translation for generated lessons."""

from __future__ import annotations

from .protect import MathProtector, ProtectedText
from .service import translate_lesson
from .translator import IndicTransTranslator, TranslationError, Translator, default_translator

__all__ = [
    "IndicTransTranslator",
    "MathProtector",
    "ProtectedText",
    "TranslationError",
    "Translator",
    "default_translator",
    "translate_lesson",
]
