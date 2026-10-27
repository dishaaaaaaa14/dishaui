"""Index PDF/PPTX material and retrieve cited chunks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config
from medha.ingest import IngestError

from .errors import RagError
from .service import RagService


def _service(args: argparse.Namespace) -> RagService:
    return RagService(use_reranker=not getattr(args, "no_rerank", False))


def _print_index(report: object) -> None:
    from .models import IndexReport

    assert isinstance(report, IndexReport)
    print(
        f"{report.doc_id[:12]}: indexed={report.indexed} "
        f"removed={report.removed} collection={report.collection_count}"
    )


def _print_query(result: object) -> None:
    from .models import QueryResult

    assert isinstance(result, QueryResult)
    print(
        f"{len(result.hits)} hit(s) from {result.candidate_count} candidate(s); "
        f"embedder={result.embedder} reranked={result.reranked}"
    )
    for rank, hit in enumerate(result.hits, start=1):
        score = hit.rerank_score if hit.rerank_score is not None else hit.vector_score
        print(f"{rank}. {hit.citation} ({score:.4f})")
        print(f"   {hit.text[:220].replace(chr(10), ' ')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-rag", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="ingest and index material")
    index.add_argument("--path", type=Path, nargs="+", required=True)
    index.add_argument("--ocr", action=argparse.BooleanOptionalAction, default=None)
    index.add_argument("--no-cache", action="store_true")
    index.add_argument("--json", action="store_true")

    query = subparsers.add_parser("query", help="retrieve cited chunks")
    query.add_argument("text")
    query.add_argument("--top-k", type=int, default=None)
    query.add_argument("--candidates", type=int, default=None)
    query.add_argument("--no-rerank", action="store_true")
    query.add_argument("--json", action="store_true")

    stats = subparsers.add_parser("stats", help="show collection size")
    stats.add_argument("--json", action="store_true")

    reset = subparsers.add_parser("reset", help="delete the retrieval collection")
    reset.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    config.ensure_dirs()

    try:
        if args.command == "reset":
            if not args.yes:
                print("refusing to reset without --yes", file=sys.stderr)
                return 2
            RagService().reset()
            print("collection reset")
            return 0

        service = _service(args)
        if args.command == "index":
            reports = [
                service.index_file(path, ocr=args.ocr, use_cache=not args.no_cache)
                for path in args.path
            ]
            if args.json:
                print(json.dumps([report.model_dump() for report in reports], indent=2))
            else:
                for path, report in zip(args.path, reports, strict=True):
                    print(f"{path}: ", end="")
                    _print_index(report)
            return 0

        if args.command == "query":
            result = service.query(
                args.text,
                top_k=args.top_k,
                candidates=args.candidates,
                rerank=not args.no_rerank,
            )
            if result.hits and not result.reranked and not args.no_rerank:
                print(
                    "warning: reranker unavailable; using vector ranking",
                    file=sys.stderr,
                )
            if args.json:
                print(result.model_dump_json(indent=2))
            else:
                _print_query(result)
            return 0

        if args.command == "stats":
            stats_result = service.stats()
            if args.json:
                print(stats_result.model_dump_json(indent=2))
            else:
                print(f"{stats_result.collection}: {stats_result.count} chunk(s)")
            return 0
    except (IngestError, RagError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
