"""Evaluate lesson quality and render/timing regressions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import evaluate_corpus, evaluate_file
from .models import LessonReport


def _print_corpus(reports: list[LessonReport]) -> None:
    if not reports:
        print("no lessons found")
        return
    total = len(reports)
    failed = sum(1 for report in reports if not report.ok)
    warnings = sum(report.warnings for report in reports)
    print(f"{total} lesson(s): {total - failed} ok, {failed} failed, {warnings} warning(s)")
    for report in reports:
        label = report.lesson_id or report.path or "<lesson>"
        print(f"  {report.score:3d}  {label}  ({report.errors} error, {report.warnings} warning)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-eval", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    lesson = subparsers.add_parser("lesson", help="evaluate one lesson JSON")
    lesson.add_argument("path", type=Path)
    lesson.add_argument("--json", action="store_true")
    lesson.add_argument("--strict", action="store_true", help="fail on warnings")
    lesson.add_argument("--no-render", action="store_true")
    lesson.add_argument("--tts", action="store_true", help="include a real speech check")
    lesson.add_argument("--voice", default=None)
    lesson.add_argument("--speed", type=float, default=None)

    corpus = subparsers.add_parser("corpus", help="evaluate every .json in a directory")
    corpus.add_argument("directory", type=Path, nargs="?", default=None)
    corpus.add_argument("--json", action="store_true")
    corpus.add_argument("--strict", action="store_true")
    corpus.add_argument("--no-render", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "lesson":
            track = None
            if args.tts:
                from medha.lesson.store import load_lesson
                from medha.tts.speech import synthesize_lesson

                kwargs = {}
                if args.voice:
                    kwargs["voice"] = args.voice
                if args.speed:
                    kwargs["speed"] = args.speed
                track = synthesize_lesson(load_lesson(args.path), **kwargs)
            report = evaluate_file(
                args.path,
                speech_track=track,
                render_smoke=not args.no_render,
            )
            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(report.format_text())
            failed = not report.ok or (args.strict and report.warnings > 0)
            return 1 if failed else 0

        reports = evaluate_corpus(
            args.directory,
            render_smoke=not args.no_render,
        )
        if args.json:
            print(json.dumps([report.model_dump() for report in reports], indent=2))
        else:
            _print_corpus(reports)
        failed = any(
            not report.ok or (args.strict and report.warnings > 0)
            for report in reports
        )
        return 1 if failed else 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
