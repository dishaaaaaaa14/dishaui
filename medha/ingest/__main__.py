"""Ingest PDF/PPTX files and emit normalized, cited JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config
from medha.ingest.docling_parser import IngestError
from medha.ingest.service import ingest_file


def _target(out: Path, source: Path, multiple: bool) -> Path:
    if multiple or out.suffix.lower() != ".json":
        return out / f"{source.stem}.ingest.json"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-ingest", description=__doc__)
    parser.add_argument("--path", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--ocr", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--overlap", type=int, default=None)
    args = parser.parse_args(argv)

    config.ensure_dirs()
    results = []
    failures = 0
    for source in args.path:
        try:
            result = ingest_file(
                source,
                ocr=args.ocr,
                use_cache=not args.no_cache,
                max_tokens=args.max_tokens,
                overlap=args.overlap,
            )
        except (IngestError, OSError, ValueError) as exc:
            print(f"{source}: {exc}", file=sys.stderr)
            failures += 1
            continue
        results.append(result)
        if args.out is not None:
            target = _target(args.out, source, len(args.path) > 1)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps([result.model_dump(mode="json") for result in results], indent=2))
    else:
        for result in results:
            document = result.document
            print(
                f"{document.source.filename}: {document.page_count} "
                f"{document.locator_kind}(s), {len(document.blocks)} blocks, "
                f"{len(result.chunks)} chunks, "
                f"tokenizer={result.chunking.tokenizer}, "
                f"max_tokens={result.chunking.max_tokens}"
            )
            for warning in document.warnings:
                print(f"  warning: {warning}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
