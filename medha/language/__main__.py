"""Translate an English lesson JSON to Hindi or Kannada."""

from __future__ import annotations

import argparse
from pathlib import Path

import config
from medha.lesson.store import load_lesson, save_lesson

from .service import translate_lesson
from .translator import TranslationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-language", description=__doc__)
    parser.add_argument("lesson", type=Path)
    parser.add_argument("--to", choices=["hi", "kn"], required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    config.ensure_dirs()
    lesson = load_lesson(args.lesson)
    try:
        translated = translate_lesson(lesson, args.to)
    except TranslationError as exc:
        print(f"Translation failed: {exc}")
        return 1
    output = args.out or args.lesson.with_name(
        f"{args.lesson.stem}-{args.to}.json"
    )
    path = save_lesson(translated, output)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
