"""Export and check the published board-action schemas.

Examples:
    python tools/export_schema.py
    python tools/export_schema.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from medha.core.schema import export_schema, validate_lesson  # noqa: E402

DEFAULT_OUT = ROOT / "spec" / "board-action" / "v1"
EXAMPLES = DEFAULT_OUT / "examples"


def check_examples() -> int:
    failures = 0
    for path in sorted(EXAMPLES.glob("*.json")):
        try:
            lesson = validate_lesson(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            failures += 1
            print(f"FAIL {path.name}: {exc}")
        else:
            actions = sum(len(step.board) for step in lesson.steps)
            print(f"ok   {path.name}: {len(lesson.steps)} steps, {actions} actions")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export-schema", description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="validate example lessons")
    args = parser.parse_args(argv)

    action_path, lesson_path = export_schema(args.out)
    print(f"wrote {action_path}")
    print(f"wrote {lesson_path}")
    if args.check:
        return check_examples()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
