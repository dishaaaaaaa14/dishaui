"""Language metadata, math protection, and lesson translation semantics."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import config
from medha.core.schema import LanguageCode, LessonScript, split_sentences, validate_lesson
from medha.language import MathProtector, TranslationError, translate_lesson
from medha.lesson.store import load_lesson
from medha.studio.service import StudioOptions, open_lesson


class FakeTranslator:
    model_id = "fake-translator"

    def translate_batch(self, texts: list[str], target: LanguageCode) -> list[str]:
        return [f"{target.upper()} {text}" for text in texts]


class BrokenTranslator:
    model_id = "broken"

    def translate_batch(self, texts: list[str], target: LanguageCode) -> list[str]:
        raise TranslationError("model unavailable")


def _lesson() -> LessonScript:
    return load_lesson(config.LESSON_CONTENT_DIR / "newton.json")


def test_math_protection_restores_equations() -> None:
    protector = MathProtector()
    text = "Force is F = ma, and the unit is 4 N. Use $v = u + at$ here."
    protected = protector.protect(text)
    assert "F = ma" not in protected.protected
    assert "4 N" not in protected.protected
    assert "$v = u + at$" not in protected.protected
    assert protected.has_prose()
    assert protected.restore("बल " + protected.protected) == "बल " + text
    assert protected.restore("missing") == text


def test_translate_preserves_layout_ids_and_math() -> None:
    lesson = _lesson()
    translated = translate_lesson(lesson, "hi", FakeTranslator())

    assert translated.language == "hi"
    assert translated.lesson_id.endswith("-hi")
    assert translated.title.startswith("HI ")
    assert translated.meta.translated_from == "en"
    assert translated.meta.translation_model == "fake-translator"
    assert translated.meta.source_lesson_id == lesson.lesson_id
    assert len(translated.steps) == len(lesson.steps)

    for original_step, step in zip(lesson.steps, translated.steps, strict=True):
        assert step.id == original_step.id
        assert len(step.board) == len(original_step.board)
        assert len(split_sentences(step.narration)) == len(
            split_sentences(original_step.narration)
        )
        for original_action, action in zip(
            original_step.board, step.board, strict=True
        ):
            assert action.id == original_action.id
            assert action.duration_ms == original_action.duration_ms
            if action.start is not None:
                sentence = split_sentences(step.narration)[action.start.sentence]
                assert action.start.char <= len(sentence)
            if action.op == "write_math" and original_action.op == "write_math":
                assert action.latex == original_action.latex
            if action.op == "draw" and original_action.op == "draw":
                assert action.rect == original_action.rect
                assert action.points == original_action.points


def test_translate_same_language_is_a_noop() -> None:
    lesson = _lesson()
    assert translate_lesson(lesson, "en", BrokenTranslator()) is lesson
    hindi = lesson.model_copy(update={"language": "hi"})
    assert translate_lesson(hindi, "hi", BrokenTranslator()) is hindi


def test_non_english_source_cannot_be_retranslated() -> None:
    hindi = _lesson().model_copy(update={"language": "hi"})
    with pytest.raises(TranslationError, match="only English"):
        translate_lesson(hindi, "kn", FakeTranslator())


def test_translation_fallback_keeps_original_lesson(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.json"
    shutil.copyfile(config.LESSON_CONTENT_DIR / "newton.json", source)
    monkeypatch.setattr(config, "LESSON_CONTENT_DIR", tmp_path)

    def fail(_lesson: LessonScript, _target: str) -> LessonScript:
        raise TranslationError("IndicTrans2 is not installed")

    monkeypatch.setattr("medha.language.translate_lesson", fail)
    result = open_lesson(
        source,
        StudioOptions(
            topic="Newton",
            language="hi",
            tts=False,
        ),
    )
    assert result.lesson.language == "en"
    assert result.path == source
    assert any("translation unavailable" in warning for warning in result.warnings)


def test_language_field_defaults_and_validates() -> None:
    lesson = validate_lesson(
        {
            "lesson_id": "demo",
            "title": "Demo",
            "steps": [
                {
                    "id": "s1",
                    "concept": "one",
                    "narration": "One sentence.",
                }
            ],
        }
    )
    assert lesson.language == "en"
