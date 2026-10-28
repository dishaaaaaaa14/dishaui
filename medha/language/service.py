"""Translate a complete English lesson without disturbing layout or timing."""

from __future__ import annotations

from typing import Any

import config
from medha.core.schema import LanguageCode, LessonScript, split_sentences

from .protect import MathProtector, ProtectedText
from .translator import TranslationError, Translator, default_translator


def _clip(value: str, limit: int, fallback: str) -> str:
    text = value.strip()
    if not text:
        return fallback
    return text[:limit]


def _single_sentence(text: str, target: LanguageCode, fallback: str) -> str:
    parts = split_sentences(text)
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0]
    body = " ".join(part.rstrip(".!?।") for part in parts)
    return body + ("।" if target == "hi" else ".")


def _collect_strings(lesson: LessonScript) -> list[str]:
    values: list[str] = [lesson.title]
    if lesson.target_concept:
        values.append(lesson.target_concept)
    for step in lesson.steps:
        values.append(step.concept)
        values.extend(split_sentences(step.narration))
        for action in step.board:
            op = action.op
            if op == "write_text":
                values.append(action.text)  # type: ignore[union-attr]
            elif op == "bullet_list":
                values.extend(action.items)  # type: ignore[union-attr]
            elif op in {"draw", "point"} and action.label:  # type: ignore[union-attr]
                values.append(action.label)  # type: ignore[union-attr]
            elif op == "image" and action.caption:  # type: ignore[union-attr]
                values.append(action.caption)  # type: ignore[union-attr]
        if step.checkpoint is not None:
            values.extend(
                [
                    step.checkpoint.question,
                    step.checkpoint.expected,
                    *step.checkpoint.hints,
                ]
            )
    return [value for value in dict.fromkeys(values) if value.strip()]


def _translate_map(
    lesson: LessonScript,
    target: LanguageCode,
    translator: Translator,
) -> tuple[dict[str, str], str]:
    protector = MathProtector()
    protected: dict[str, ProtectedText] = {
        text: protector.protect(text) for text in _collect_strings(lesson)
    }
    pending = [
        (text, item)
        for text, item in protected.items()
        if item.has_prose()
    ]
    mapping: dict[str, str] = {text: text for text in protected}
    if pending:
        outputs = translator.translate_batch(
            [item.protected for _text, item in pending], target
        )
        if len(outputs) != len(pending):
            raise TranslationError("translator returned the wrong number of strings")
        for (text, item), output in zip(pending, outputs, strict=True):
            restored = item.restore(output).strip()
            mapping[text] = restored or text
    return mapping, str(getattr(translator, "model_id", "unknown"))


def _map_anchor(
    payload: dict[str, Any],
    original_sentences: list[str],
    translated_sentences: list[str],
) -> None:
    anchor = payload.get("start")
    if not isinstance(anchor, dict):
        return
    sentence = int(anchor.get("sentence", 0))
    if sentence < 0 or sentence >= len(translated_sentences):
        return
    source_length = max(1, len(original_sentences[sentence]))
    translated_length = len(translated_sentences[sentence])
    source_char = max(0, int(anchor.get("char", 0)))
    char = min(translated_length, round(source_char / source_length * translated_length))
    payload["start"] = {"sentence": sentence, "char": char}


def translate_lesson(
    lesson: LessonScript,
    target: LanguageCode,
    translator: Translator | None = None,
) -> LessonScript:
    if target not in config.LANGUAGE_NAMES:
        raise TranslationError(f"unsupported language: {target}")
    if target == lesson.language:
        return lesson
    if lesson.language != "en":
        if target == "en":
            return lesson
        raise TranslationError(
            f"only English lessons can be translated, not {lesson.language}"
        )
    if target == "en":
        return lesson

    engine = translator or default_translator()
    mapping, model_id = _translate_map(lesson, target, engine)

    def tr(text: str) -> str:
        return mapping.get(text, text)

    payload = lesson.model_dump(mode="python")
    payload["language"] = target
    payload["lesson_id"] = (
        f"{lesson.lesson_id[: 63 - len(target)]}-{target}"
    )
    payload["title"] = _clip(tr(lesson.title), 200, lesson.title)
    if lesson.target_concept:
        payload["target_concept"] = _clip(
            tr(lesson.target_concept), 120, lesson.target_concept
        )
    meta = payload.setdefault("meta", {})
    meta["translated_from"] = lesson.language
    meta["translation_model"] = model_id
    meta["source_lesson_id"] = lesson.lesson_id

    step_payloads = payload["steps"]
    for step, step_payload in zip(lesson.steps, step_payloads, strict=True):
        step_payload["concept"] = _clip(tr(step.concept), 120, step.concept)
        original_sentences = split_sentences(step.narration)
        translated_sentences = [
            _single_sentence(tr(sentence), target, sentence)
            for sentence in original_sentences
        ]
        narration = " ".join(translated_sentences)[:4000].strip()
        step_payload["narration"] = narration or step.narration

        checkpoint = step_payload.get("checkpoint")
        if checkpoint is not None and step.checkpoint is not None:
            checkpoint["question"] = _clip(
                tr(step.checkpoint.question), 500, step.checkpoint.question
            )
            checkpoint["expected"] = _clip(
                tr(step.checkpoint.expected), 500, step.checkpoint.expected
            )
            checkpoint["hints"] = [
                _clip(tr(hint), 500, hint) for hint in step.checkpoint.hints
            ]

        for action, action_payload in zip(
            step.board, step_payload["board"], strict=True
        ):
            op = action_payload["op"]
            if op == "write_text":
                action_payload["text"] = _clip(
                    tr(action.text), 2000, action.text  # type: ignore[union-attr]
                )
            elif op == "bullet_list":
                action_payload["items"] = [
                    tr(item) for item in action.items  # type: ignore[union-attr]
                ]
            elif op in {"draw", "point"} and action.label:  # type: ignore[union-attr]
                action_payload["label"] = _clip(
                    tr(action.label), 120, action.label  # type: ignore[union-attr]
                )
            elif op == "image" and action.caption:  # type: ignore[union-attr]
                action_payload["caption"] = _clip(
                    tr(action.caption), 160, action.caption  # type: ignore[union-attr]
                )
            _map_anchor(action_payload, original_sentences, translated_sentences)

    return LessonScript.model_validate(payload)
