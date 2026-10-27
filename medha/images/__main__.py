"""Extract teaching images and generate CPU VLM descriptions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config
from medha.ingest.docling_parser import IngestError

from .errors import ImageError
from .models import ImageReport, ImageStats
from .service import ImageService


def _print_report(report: ImageReport) -> None:
    print(
        f"{report.source_filename}: extracted={report.extracted} "
        f"described={report.described} replaced={report.replaced} "
        f"removed={report.removed} doc_id={report.doc_id[:12]}"
    )
    for image in report.images:
        location = (
            f"page {image.page_no}"
            if image.locator_kind == "page"
            else f"slide {image.page_no}"
        )
        print(f"  {image.image_id} {image.width}x{image.height} {location}")
        if image.description:
            print(f"    {image.description[:220]}")
    for warning in report.warnings:
        print(f"  warning: {warning}")


def _print_stats(stats: ImageStats) -> None:
    print(
        f"{stats.total} image(s), {stats.described} described, "
        f"{stats.documents} document(s), {stats.bytes / 1024:.1f} KiB"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-images", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="extract and describe images")
    extract.add_argument("--path", type=Path, nargs="+", required=True)
    extract.add_argument("--no-vlm", action="store_true")
    extract.add_argument("--no-cache", action="store_true")
    extract.add_argument("--json", action="store_true")

    describe = subparsers.add_parser("describe", help="describe extracted images")
    describe.add_argument("--doc-id", default=None)
    describe.add_argument("--all", action="store_true")
    describe.add_argument("--refresh", action="store_true")
    describe.add_argument("--json", action="store_true")

    stats = subparsers.add_parser("stats", help="show extracted image counts")
    stats.add_argument("--json", action="store_true")

    reset = subparsers.add_parser("reset", help="delete extracted images and manifest")
    reset.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    config.ensure_dirs()

    try:
        service = ImageService()
        if args.command == "extract":
            reports = [
                service.extract_file(
                    path,
                    describe=not args.no_vlm,
                    use_cache=not args.no_cache,
                )
                for path in args.path
            ]
            if args.json:
                print(json.dumps([report.model_dump() for report in reports], indent=2))
            else:
                for report in reports:
                    _print_report(report)
            return 0

        if args.command == "describe":
            if args.all and args.doc_id:
                print("choose --all or --doc-id, not both", file=sys.stderr)
                return 2
            reports = (
                service.describe_all(refresh=args.refresh)
                if args.all
                else [service.describe_document(args.doc_id, refresh=args.refresh)]
            )
            if args.json:
                print(json.dumps([report.model_dump() for report in reports], indent=2))
            else:
                for report in reports:
                    _print_report(report)
            return 0

        if args.command == "stats":
            result = service.stats()
            if args.json:
                print(result.model_dump_json(indent=2))
            else:
                _print_stats(result)
            return 0

        if args.command == "reset":
            if not args.yes:
                print("refusing to reset without --yes", file=sys.stderr)
                return 2
            removed = service.reset()
            print(f"removed {removed} image file(s)")
            return 0
    except (ImageError, IngestError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
