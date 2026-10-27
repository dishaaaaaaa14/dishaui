"""Studio jobs that are independent of Qt and safe to run in a worker thread."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import config
from medha.core.schema import LanguageCode, LessonScript
from medha.eval import LessonReport, evaluate_lesson
from medha.lesson import (
    GenerationRequest,
    GenerationResult,
    LessonGenerator,
    load_lesson,
    save_lesson,
)
from medha.render.playback import LessonPlayback, prepare_playback

Progress = Callable[[str], None]


@dataclass(frozen=True)
class StudioOptions:
    topic: str
    subject: str = "general"
    difficulty: str = "beginner"
    audience: str = config.LESSON_DEFAULT_AUDIENCE
    steps: int = config.LESSON_DEFAULT_STEPS
    style_id: str = "default"
    rag_query: str | None = None
    use_rag: bool = True
    use_rerank: bool = True
    use_cache: bool = True
    materials: tuple[Path, ...] = field(default_factory=tuple)
    ocr: bool | None = None
    tts: bool = True
    voice: str = config.KOKORO_VOICE
    speed: float = config.KOKORO_SPEED

    def request(self) -> GenerationRequest:
        return GenerationRequest(
            topic=self.topic,
            subject=self.subject,  # type: ignore[arg-type]
            difficulty=self.difficulty,  # type: ignore[arg-type]
            audience=self.audience,
            steps=self.steps,
            style_id=self.style_id,
            rag_query=self.rag_query or None,
            use_rag=self.use_rag or bool(self.materials),
            use_rerank=self.use_rerank,
        )


@dataclass
class StudioResult:
    lesson: LessonScript
    playback: LessonPlayback
    report: LessonReport
    path: Path | None = None
    generation: GenerationResult | None = None
    warnings: list[str] = field(default_factory=list)
    tts_error: str | None = None


def _lesson_path(lesson: LessonScript) -> Path:
    suffix = "" if lesson.language == "en" else f"-{lesson.language}"
    return config.LESSON_CONTENT_DIR / f"{lesson.lesson_id}{suffix}.json"


def _translate(
    lesson: LessonScript,
    language: LanguageCode,
    progress: Progress,
    warnings: list[str],
) -> LessonScript:
    if language == "en" or lesson.language == language:
        return lesson
    progress(f"Translating lesson to {config.LANGUAGE_NAMES[language]}...")
    try:
        from medha.language import translate_lesson

        return translate_lesson(lesson, language)
    except Exception as exc:
        warnings.append(
            f"{config.LANGUAGE_NAMES[language]} translation unavailable; "
            f"keeping {config.LANGUAGE_NAMES.get(lesson.language, lesson.language)}: {exc}"
        )
        return lesson


def _prepare(
    lesson: LessonScript,
    options: StudioOptions,
    progress: Progress,
    warnings: list[str],
) -> tuple[LessonPlayback, str | None]:
    progress("Preparing speech and timeline...")
    tts_error = None
    try:
        prepared = prepare_playback(
            lesson,
            use_tts=options.tts,
            voice=options.voice,
            speed=options.speed,
        )
    except Exception as exc:
        tts_error = str(exc)
        warnings.append(f"TTS unavailable; using silent timing: {exc}")
        prepared = prepare_playback(lesson, use_tts=False)
    return LessonPlayback(prepared), tts_error


def generate_lesson(options: StudioOptions, progress: Progress | None = None) -> StudioResult:
    notify = progress or (lambda _message: None)
    config.ensure_dirs()
    retriever = None
    if options.materials:
        from medha.rag import RagService

        notify("Loading retrieval models...")
        retriever = RagService()
        for path in options.materials:
            notify(f"Indexing {path.name}...")
            index_report = retriever.index_file(path, ocr=options.ocr)
            notify(f"Indexed {path.name}: {index_report.indexed} chunk(s)")

    notify("Generating lesson...")
    generator = LessonGenerator(retriever=retriever)
    result = generator.generate(options.request(), use_cache=options.use_cache)

    warnings = list(result.warnings)
    lesson = _translate(result.lesson, options.language, notify, warnings)
    path = save_lesson(lesson, _lesson_path(lesson))
    notify("Checking lesson quality...")
    report = evaluate_lesson(lesson, path=path)
    playback, tts_error = _prepare(lesson, options, notify, warnings)
    if playback.prepared.track is not None:
        report = evaluate_lesson(
            lesson,
            path=path,
            speech_track=playback.prepared.track,
        )
    notify("Ready")
    return StudioResult(
        lesson=lesson,
        playback=playback,
        report=report,
        path=path,
        generation=result,
        warnings=warnings,
        tts_error=tts_error,
    )


def open_lesson(
    path: Path,
    options: StudioOptions,
    progress: Progress | None = None,
) -> StudioResult:
    notify = progress or (lambda _message: None)
    notify("Loading lesson...")
    lesson = load_lesson(path)
    warnings: list[str] = []
    translated = _translate(lesson, options.language, notify, warnings)
    if translated is not lesson:
        lesson = translated
        path = save_lesson(lesson, _lesson_path(lesson))
    notify("Checking lesson quality...")
    report = evaluate_lesson(lesson, path=path)
    playback, tts_error = _prepare(lesson, options, notify, warnings)
    if playback.prepared.track is not None:
        report = evaluate_lesson(
            lesson,
            path=path,
            speech_track=playback.prepared.track,
        )
    notify("Ready")
    return StudioResult(
        lesson=lesson,
        playback=playback,
        report=report,
        path=path,
        warnings=warnings,
        tts_error=tts_error,
    )
