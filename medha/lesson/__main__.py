"""Generate a grounded lesson script with the local Ollama model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import get_args

import config
from medha.core.schema import Subject
from medha.ingest import IngestError

from .errors import GenerationError
from .generator import LessonGenerator
from .models import Difficulty, GenerationRequest, GenerationResult
from .store import save_lesson


def _print_result(result: GenerationResult, saved: Path | None) -> None:
    lesson = result.lesson
    actions = sum(len(step.board) for step in lesson.steps)
    print(f"{lesson.lesson_id}: {lesson.title}")
    print(
        f"  subject={lesson.subject} difficulty={lesson.difficulty} "
        f"steps={len(lesson.steps)} actions={actions}"
    )
    print(
        f"  model={lesson.meta.model} cached={result.cached} "
        f"retrieved={result.retrieved} elapsed={result.elapsed_s:.2f}s"
    )
    if lesson.meta.sources:
        print("  sources=" + " | ".join(lesson.meta.sources[:5]))
    if saved is not None:
        print(f"  saved={saved}")
    for warning in result.warnings:
        print(f"  warning: {warning}")


def _write(path: Path, result: GenerationResult) -> None:
    save_lesson(result.lesson, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-lesson", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate and validate a lesson")
    generate.add_argument("--topic", required=True)
    generate.add_argument("--subject", choices=get_args(Subject), default="general")
    generate.add_argument("--difficulty", choices=get_args(Difficulty), default="beginner")
    generate.add_argument("--audience", default=config.LESSON_DEFAULT_AUDIENCE)
    generate.add_argument("--steps", type=int, default=config.LESSON_DEFAULT_STEPS)
    generate.add_argument("--style", dest="style_id", default="default")
    generate.add_argument("--rag-query", default=None)
    generate.add_argument("--material", type=Path, nargs="+", default=None)
    generate.add_argument("--ocr", action=argparse.BooleanOptionalAction, default=None)
    generate.add_argument("--no-rag", action="store_true")
    generate.add_argument("--no-rerank", action="store_true")
    generate.add_argument("--no-cache", action="store_true")
    generate.add_argument("--model", default=None)
    generate.add_argument("--out", type=Path, default=None)
    generate.add_argument("--no-save", action="store_true")
    generate.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.material and args.no_rag:
        print("--material cannot be combined with --no-rag", file=sys.stderr)
        return 2

    config.ensure_dirs()
    try:
        retriever = None
        if args.material:
            from medha.rag import RagService

            retriever = RagService()
            for path in args.material:
                report = retriever.index_file(path, ocr=args.ocr)
                if not args.json:
                    print(
                        f"indexed {path}: {report.indexed} chunk(s), "
                        f"collection={report.collection_count}",
                        file=sys.stderr,
                    )

        request = GenerationRequest(
            topic=args.topic,
            subject=args.subject,
            difficulty=args.difficulty,
            audience=args.audience,
            steps=args.steps,
            style_id=args.style_id,
            rag_query=args.rag_query,
            use_rag=not args.no_rag,
            use_rerank=not args.no_rerank,
        )
        generator = LessonGenerator(retriever=retriever)
        if args.model:
            from .client import OllamaClient

            generator = LessonGenerator(
                client=OllamaClient(model=args.model),
                retriever=retriever,
            )
        result = generator.generate(request, use_cache=not args.no_cache)

        saved: Path | None = None
        if not args.no_save:
            saved = args.out or (
                config.LESSON_CONTENT_DIR / f"{result.lesson.lesson_id}.json"
            )
            _write(saved, result)
        if args.json:
            print(result.model_dump_json(indent=2))
            if saved is not None:
                print(f"saved {saved}", file=sys.stderr)
        else:
            _print_result(result, saved)
        return 0
    except (GenerationError, IngestError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
